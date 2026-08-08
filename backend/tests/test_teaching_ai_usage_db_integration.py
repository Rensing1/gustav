"""PostgreSQL integration tests for the combined course AI usage read model.

Why:
    Course totals combine submission and dialog telemetry. This test exercises
    the production tables, foreign keys, RLS role and SQL aggregation together,
    without reading prompts, learner answers or provider payloads.
"""

from __future__ import annotations

from datetime import datetime, timezone
import os
import uuid

import pytest

from backend.teaching import repo_ai_usage_queries
from backend.tests.utils.db import require_db_or_skip as _require_db_or_skip

pytest.importorskip("psycopg")
import psycopg  # type: ignore  # noqa: E402


pytestmark = pytest.mark.db_write


def _limited_dsn() -> str:
    host = os.getenv("TEST_DB_HOST", "127.0.0.1")
    port = os.getenv("TEST_DB_PORT", "54322")
    user = os.getenv("APP_DB_USER", "gustav_app")
    password = os.getenv("APP_DB_PASSWORD", "CHANGE_ME_DEV")
    return os.getenv("RLS_TEST_DSN") or os.getenv("DATABASE_URL") or f"postgresql://{user}:{password}@{host}:{port}/postgres"


def _service_dsn() -> str:
    host = os.getenv("TEST_DB_HOST", "127.0.0.1")
    port = os.getenv("TEST_DB_PORT", "54322")
    return (
        os.getenv("SERVICE_ROLE_DSN")
        or os.getenv("RLS_TEST_SERVICE_DSN")
        or f"postgresql://postgres:postgres@{host}:{port}/postgres"
    )


def _create_task(cur, *, owner_sub: str, title: str) -> tuple[str, str]:
    cur.execute("insert into public.units (title, author_id) values (%s, %s) returning id", (title, owner_sub))
    unit_id = str(cur.fetchone()[0])
    cur.execute(
        "insert into public.unit_sections (unit_id, title, position) values (%s::uuid, %s, 1) returning id",
        (unit_id, f"{title} Abschnitt"),
    )
    section_id = str(cur.fetchone()[0])
    cur.execute(
        """
        insert into public.unit_tasks (unit_id, section_id, instruction_md, criteria, position)
        values (%s::uuid, %s::uuid, 'Untersuche das Beispiel.', array['Begründung'], 1)
        returning id
        """,
        (unit_id, section_id),
    )
    return unit_id, str(cur.fetchone()[0])


def _usage_rows(*, course_id: str, owner_sub: str, **filters):
    return repo_ai_usage_queries.list_ai_usage_events_for_owner(
        dsn=_limited_dsn(),
        psycopg_module=psycopg,
        course_id=course_id,
        owner_sub=owner_sub,
        **filters,
    )


@pytest.mark.anyio
async def test_combined_usage_is_owner_scoped_filterable_and_deleted_with_its_source() -> None:
    """Aggregate both pipelines and preserve their source deletion lifecycle."""

    _require_db_or_skip()
    owner_sub = f"teacher-usage-{uuid.uuid4().hex}"
    other_owner_sub = f"teacher-usage-{uuid.uuid4().hex}"
    student_sub = f"student-usage-{uuid.uuid4().hex}"
    other_student_sub = f"student-usage-{uuid.uuid4().hex}"
    course_ids: list[str] = []

    with psycopg.connect(_service_dsn()) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into public.courses (title, subject, grade_level, school_year_start, teacher_id)
                values ('Tokenkurs', 'Testfach', '10', 2026, %s)
                returning id
                """,
                (owner_sub,),
            )
            course_id = str(cur.fetchone()[0])
            course_ids.append(course_id)
            cur.execute(
                """
                insert into public.courses (title, subject, grade_level, school_year_start, teacher_id)
                values ('Fremdkurs', 'Testfach', '10', 2026, %s)
                returning id
                """,
                (other_owner_sub,),
            )
            other_course_id = str(cur.fetchone()[0])
            course_ids.append(other_course_id)

            unit_id, task_id = _create_task(cur, owner_sub=owner_sub, title="Token Einheit A")
            second_unit_id, second_task_id = _create_task(cur, owner_sub=owner_sub, title="Token Einheit B")
            cur.execute(
                "insert into public.course_modules (course_id, unit_id, position) values (%s::uuid, %s::uuid, 1)",
                (course_id, unit_id),
            )
            cur.execute(
                "insert into public.course_modules (course_id, unit_id, position) values (%s::uuid, %s::uuid, 2)",
                (course_id, second_unit_id),
            )

            cur.execute(
                """
                insert into public.learning_submissions (
                  course_id, task_id, section_id, student_sub, kind, text_body, attempt_nr, analysis_status, created_at
                ) values (
                  %s::uuid, %s::uuid,
                  (select section_id from public.unit_tasks where id = %s::uuid),
                  %s, 'text', 'Technische Testantwort', 1, 'completed', %s
                )
                returning id
                """,
                (course_id, task_id, task_id, student_sub, datetime(2026, 3, 29, 10, tzinfo=timezone.utc)),
            )
            submission_id = str(cur.fetchone()[0])
            cur.execute(
                """
                insert into public.learning_submissions (
                  course_id, task_id, section_id, student_sub, kind, text_body, attempt_nr, analysis_status, created_at
                ) values (
                  %s::uuid, %s::uuid,
                  (select section_id from public.unit_tasks where id = %s::uuid),
                  %s, 'text', 'Zweite technische Testantwort', 1, 'completed', %s
                )
                returning id
                """,
                (
                    course_id,
                    second_task_id,
                    second_task_id,
                    other_student_sub,
                    datetime(2026, 3, 30, 10, tzinfo=timezone.utc),
                ),
            )
            second_submission_id = str(cur.fetchone()[0])

            cur.execute(
                """
                insert into public.ai_usage_events (
                  event_key, occurred_at, submission_id, course_id, unit_id, task_id, student_sub,
                  model, stage, modality, call_kind, usage_known, input_tokens, output_tokens, total_tokens
                ) values
                  (%s::uuid, '2026-03-29 10:00:00+00', %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s,
                   'model-submission', 'feedback', 'text', 'primary', true, 30, 10, 40),
                  (%s::uuid, '2026-03-30 10:00:00+00', %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s,
                   'model-analysis', 'analysis', 'text', 'primary', true, 5, 2, 7)
                """,
                (
                    str(uuid.uuid4()), submission_id, course_id, unit_id, task_id, student_sub,
                    str(uuid.uuid4()), second_submission_id, course_id, second_unit_id, second_task_id, other_student_sub,
                ),
            )

            cur.execute(
                """
                insert into public.learning_dialog_sessions (course_id, task_id, student_sub)
                values (%s::uuid, %s::uuid, %s)
                returning id
                """,
                (course_id, task_id, student_sub),
            )
            session_id = str(cur.fetchone()[0])
            cur.execute(
                """
                insert into public.dialog_ai_usage_events (
                  event_key, occurred_at, session_id, course_id, unit_id, task_id, actor_sub,
                  actor_role, stage, model, usage_known, input_tokens, output_tokens, total_tokens,
                  unknown_reason
                ) values
                  (%s::uuid, '2026-03-29 10:05:00+00', %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s,
                   'student', 'initial_starters', 'model-dialog', true, 100, 20, 120, null),
                  (%s::uuid, '2026-03-29 10:10:00+00', %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s,
                   'student', 'reply', 'model-dialog', false, null, null, null, 'missing_provider_usage'),
                  (%s::uuid, '2026-03-29 10:15:00+00', null, null, %s::uuid, %s::uuid, %s,
                   'teacher', 'preview', 'model-preview', true, 999, 999, 1998, null)
                """,
                (
                    str(uuid.uuid4()), session_id, course_id, unit_id, task_id, student_sub,
                    str(uuid.uuid4()), session_id, course_id, unit_id, task_id, student_sub,
                    str(uuid.uuid4()), unit_id, task_id, owner_sub,
                ),
            )
        conn.commit()

    try:
        rows = _usage_rows(course_id=course_id, owner_sub=owner_sub)
        assert len(rows) == 4
        assert sum(int(row["input_tokens"]) for row in rows) == 135
        assert sum(int(row["output_tokens"]) for row in rows) == 32
        assert sum(int(row["total_tokens"]) for row in rows) == 167
        assert sum(int(row["unknown_events"]) for row in rows) == 1
        assert {row["call_kind"] for row in rows if str(row["model"]).startswith("model-dialog")} == {"dialog_generation"}
        assert "model-preview" not in {row["model"] for row in rows}

        first_unit_rows = _usage_rows(course_id=course_id, owner_sub=owner_sub, unit_id=unit_id)
        assert len(first_unit_rows) == 3
        student_rows = _usage_rows(course_id=course_id, owner_sub=owner_sub, student_sub=student_sub)
        assert len(student_rows) == 3
        day_rows = _usage_rows(
            course_id=course_id,
            owner_sub=owner_sub,
            from_at=datetime(2026, 3, 29, tzinfo=timezone.utc),
            to_at=datetime(2026, 3, 30, tzinfo=timezone.utc),
        )
        assert len(day_rows) == 3
        assert _usage_rows(course_id=course_id, owner_sub=other_owner_sub) == []

        with psycopg.connect(_service_dsn()) as conn:  # type: ignore[arg-type]
            with conn.cursor() as cur:
                cur.execute("delete from public.learning_submissions where id = %s::uuid", (submission_id,))
                cur.execute("delete from public.learning_dialog_sessions where id = %s::uuid", (session_id,))
            conn.commit()

        remaining = _usage_rows(course_id=course_id, owner_sub=owner_sub)
        assert len(remaining) == 1
        assert remaining[0]["model"] == "model-analysis"
    finally:
        with psycopg.connect(_service_dsn()) as conn:  # type: ignore[arg-type]
            with conn.cursor() as cur:
                cur.execute("delete from public.courses where id = any(%s::uuid[])", (course_ids,))
                cur.execute("delete from public.units where author_id = %s", (owner_sub,))
            conn.commit()


@pytest.mark.anyio
async def test_combined_usage_tables_have_course_time_indexes_and_cascade_sources() -> None:
    """Confirm the existing schema supports this read model without a migration."""

    _require_db_or_skip()
    with psycopg.connect(_service_dsn()) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute(
                """
                select tablename, indexdef
                  from pg_indexes
                 where schemaname = 'public'
                   and tablename in ('ai_usage_events', 'dialog_ai_usage_events')
                """
            )
            index_sql = "\n".join(f"{table} {definition}" for table, definition in cur.fetchall()).lower()
            assert "ai_usage_events" in index_sql and "(course_id, occurred_at desc)" in index_sql
            assert "dialog_ai_usage_events" in index_sql and "(course_id, occurred_at desc)" in index_sql

            cur.execute(
                """
                select conrelid::regclass::text, confrelid::regclass::text, confdeltype
                  from pg_constraint
                 where contype = 'f'
                   and conrelid in (
                     'public.ai_usage_events'::regclass,
                     'public.dialog_ai_usage_events'::regclass
                   )
                """
            )
            foreign_keys = {(table, source, delete_action) for table, source, delete_action in cur.fetchall()}
            assert ("ai_usage_events", "learning_submissions", "c") in foreign_keys
            assert ("dialog_ai_usage_events", "learning_dialog_sessions", "c") in foreign_keys
