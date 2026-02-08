from __future__ import annotations

import os
import uuid

import pytest

from backend.tests.utils.db import require_db_or_skip as _require_db_or_skip


psycopg = None
try:  # pragma: no cover - optional dependency at runtime
    import psycopg  # type: ignore
except Exception:  # pragma: no cover
    psycopg = None  # type: ignore


def _service_dsn() -> str | None:
    return os.getenv("SERVICE_ROLE_DSN") or os.getenv("RLS_TEST_SERVICE_DSN")


@pytest.mark.skipif(psycopg is None, reason="psycopg required for legacy import regression test")
def test_import_legacy_backup_transfers_submissions_with_section_id() -> None:
    """Regression: legacy submission transfer must populate learning_submissions.section_id.

    Why:
        We denormalize section_id onto learning_submissions for modular unit
        progress aggregation. The import pipeline must therefore insert
        section_id for every transferred submission row, otherwise the
        NOT NULL constraint fails and imports abort.
    """
    _require_db_or_skip()
    dsn = _service_dsn()
    if not dsn:
        pytest.skip("SERVICE_ROLE_DSN (or RLS_TEST_SERVICE_DSN) required for legacy import integration test")

    # Import the transfer function from the script under test.
    from scripts.import_legacy_backup import transfer_submissions  # type: ignore

    legacy_schema = f"legacy_raw_test_{uuid.uuid4().hex[:8]}"
    teacher_sub = "teacher-import"
    student_sub = "student-import"
    legacy_student_id = uuid.uuid4()

    course_id = uuid.uuid4()
    unit_id = uuid.uuid4()
    section_id = uuid.uuid4()
    task_id = uuid.uuid4()
    submission_id = uuid.uuid4()

    with psycopg.connect(dsn, autocommit=True) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:  # type: ignore[attr-defined]
            # Minimal mapping: legacy UUID -> current subject string.
            cur.execute(
                """
                create table if not exists public.legacy_user_map (
                  legacy_id uuid primary key,
                  sub text unique
                )
                """
            )
            cur.execute(
                """
                insert into public.legacy_user_map (legacy_id, sub)
                values (%s, %s)
                on conflict (legacy_id) do update set sub = excluded.sub
                """,
                (legacy_student_id, student_sub),
            )

            # Minimal world: course, membership, unit, section, module, task.
            cur.execute(
                "insert into public.courses (id, title, teacher_id) values (%s, %s, %s)",
                (course_id, "Kurs Legacy Import", teacher_sub),
            )
            cur.execute(
                "insert into public.course_memberships (course_id, student_id) values (%s, %s)",
                (course_id, student_sub),
            )
            cur.execute(
                "insert into public.units (id, title, summary, author_id) values (%s, %s, %s, %s)",
                (unit_id, "Unit Legacy Import", None, teacher_sub),
            )
            cur.execute(
                "insert into public.unit_sections (id, unit_id, title, position) values (%s, %s, %s, %s)",
                (section_id, unit_id, "Section 1", 1),
            )
            cur.execute(
                "insert into public.course_modules (course_id, unit_id, position) values (%s, %s, %s)",
                (course_id, unit_id, 1),
            )
            cur.execute(
                "insert into public.unit_tasks (id, unit_id, section_id, instruction_md, position) values (%s, %s, %s, %s, %s)",
                (task_id, unit_id, section_id, "Aufgabe", 1),
            )

            # Legacy schema + submission row.
            cur.execute(f"create schema {legacy_schema}")
            cur.execute(
                f"""
                create table {legacy_schema}.submission (
                  id uuid primary key,
                  student_id uuid,
                  task_id uuid,
                  submitted_at timestamptz,
                  submission_data jsonb,
                  attempt_number integer,
                  ai_feedback text,
                  teacher_override_feedback text,
                  feed_back_text text,
                  feed_forward_text text,
                  feedback_status text,
                  feedback_generated_at timestamptz,
                  ai_insights jsonb,
                  created_at timestamptz,
                  updated_at timestamptz
                )
                """
            )
            cur.execute(
                f"""
                insert into {legacy_schema}.submission (
                  id, student_id, task_id, submitted_at, submission_data, attempt_number,
                  ai_feedback, teacher_override_feedback, feed_back_text, feed_forward_text,
                  feedback_status, feedback_generated_at, ai_insights, created_at, updated_at
                )
                values (
                  %s, %s, %s, now(), %s::jsonb, 1,
                  null, null, null, null,
                  'pending', null, null, now(), now()
                )
                """,
                (submission_id, legacy_student_id, task_id, '{"type":"text","text":"Hi"}'),
            )

    # Act: run the transfer phase.
    result = transfer_submissions(dsn, legacy_schema, dry_run=False)
    assert result.status in ("success", "partial")

    try:
        with psycopg.connect(dsn) as conn:  # type: ignore[arg-type]
            with conn.cursor() as cur:  # type: ignore[attr-defined]
                cur.execute(
                    "select section_id::text from public.learning_submissions where id=%s::uuid",
                    (submission_id,),
                )
                row = cur.fetchone()
                assert row is not None, "Transferred submission not found"
                assert row[0] == str(section_id), "section_id must be populated during transfer"
    finally:
        # Cleanup: keep DB reasonably tidy for repeated runs.
        with psycopg.connect(dsn, autocommit=True) as conn:  # type: ignore[arg-type]
            with conn.cursor() as cur:  # type: ignore[attr-defined]
                cur.execute("delete from public.learning_submissions where id=%s::uuid", (submission_id,))
                cur.execute("delete from public.unit_tasks where id=%s::uuid", (task_id,))
                cur.execute("delete from public.course_modules where course_id=%s::uuid and unit_id=%s::uuid", (course_id, unit_id))
                cur.execute("delete from public.unit_sections where id=%s::uuid", (section_id,))
                cur.execute("delete from public.units where id=%s::uuid", (unit_id,))
                cur.execute("delete from public.course_memberships where course_id=%s::uuid and student_id=%s", (course_id, student_sub))
                cur.execute("delete from public.courses where id=%s::uuid", (course_id,))
                cur.execute("delete from public.legacy_user_map where legacy_id=%s::uuid", (legacy_student_id,))
                cur.execute(f"drop schema if exists {legacy_schema} cascade")

