from __future__ import annotations

import os
import uuid
from typing import Iterable

import pytest
from click.testing import CliRunner

from backend.tests.utils import db as db_utils

psycopg = None
try:  # pragma: no cover - optional dependency at runtime
    import psycopg  # type: ignore
except Exception:  # pragma: no cover
    psycopg = None  # type: ignore


def _execute_statements(conn: psycopg.Connection, statements: Iterable[str]) -> None:
    with conn.cursor() as cur:  # type: ignore[attr-defined]
        for statement in statements:
            cur.execute(statement)


def _fetch_all(conn: psycopg.Connection, sql: str, *params) -> list[tuple]:
    with conn.cursor() as cur:  # type: ignore[attr-defined]
        cur.execute(sql, params or None)
        return list(cur.fetchall())


def _prepare_tables(conn: psycopg.Connection) -> None:
    statements = [
        "create schema if not exists staging",
        # staging tables
        """
        create table if not exists staging.submissions (
            id uuid primary key,
            task_id uuid not null,
            student_sub text not null,
            kind text not null,
            text_body text null,
            storage_key text null,
            mime_type text null,
            size_bytes int null,
            sha256 text null,
            created_at timestamptz not null
        )
        """,
        # minimal supporting staging to keep CLI phases happy
        "create table if not exists staging.users (id uuid, sub text)",
        "create table if not exists staging.courses (id uuid, title text, creator_id uuid)",
        "create table if not exists staging.course_students (course_id uuid, student_id uuid, created_at timestamptz)",
        "create table if not exists staging.learning_units (id uuid, title text, description text, creator_id uuid)",
        "create table if not exists staging.course_unit_assignments (course_id uuid, unit_id uuid, position int)",
        "create table if not exists staging.unit_sections (id uuid, unit_id uuid, title text, order_in_unit int)",
        "create table if not exists staging.section_releases (course_id uuid, unit_id uuid, section_id uuid, visible boolean, released_at timestamptz)",
        "drop table if exists staging.materials_json",
        """
        create table if not exists staging.materials_json (
            id uuid,
            section_id uuid,
            kind text,
            title text,
            body_md text,
            storage_key text,
            mime_type text,
            size_bytes bigint,
            sha256 text,
            position int,
            created_at timestamptz,
            legacy_url text
        )
        """,
        "create table if not exists staging.tasks_base (id uuid, instruction_md text, assessment_criteria jsonb, hints_md text)",
        "create table if not exists staging.tasks_regular (id uuid, section_id uuid, order_in_section int, max_attempts int, created_at timestamptz)",
        # target tables
        """
        create table if not exists public.courses (
            id uuid primary key,
            title text not null,
            teacher_id text not null
        )
        """,
        """
        create table if not exists public.course_memberships (
            course_id uuid not null,
            student_id text not null,
            joined_at timestamptz not null default now()
        )
        """,
        """
        create table if not exists public.units (
            id uuid primary key,
            title text not null,
            summary text null,
            author_id text not null
        )
        """,
        """
        create table if not exists public.unit_sections (
            id uuid primary key,
            unit_id uuid not null references public.units(id) on delete cascade,
            title text not null,
            position int not null
        )
        """,
        """
        create table if not exists public.course_modules (
            id uuid primary key default gen_random_uuid(),
            course_id uuid not null references public.courses(id) on delete cascade,
            unit_id uuid not null references public.units(id) on delete cascade,
            position int not null,
            unique (course_id, unit_id)
        )
        """,
        """
        create table if not exists public.module_section_releases (
            course_module_id uuid not null references public.course_modules(id) on delete cascade,
            section_id uuid not null references public.unit_sections(id) on delete cascade,
            visible boolean not null default true,
            released_at timestamptz null,
            released_by text not null default 'system',
            constraint module_section_releases_pkey primary key (course_module_id, section_id)
        )
        """,
        """
        create table if not exists public.unit_tasks (
            id uuid primary key,
            unit_id uuid not null references public.units(id) on delete cascade,
            section_id uuid not null references public.unit_sections(id) on delete cascade,
            instruction_md text not null,
            criteria text[] not null default '{}',
            hints_md text null,
            due_at timestamptz null,
            max_attempts int null,
            position int not null,
            created_at timestamptz not null default now()
        )
        """,
        # learning_submissions from migrations
        """
        create table if not exists public.learning_submissions (
          id uuid primary key default gen_random_uuid(),
          course_id uuid not null,
          task_id uuid not null,
          student_sub text not null,
          kind text not null,
          text_body text null,
          storage_key text null,
          mime_type text null,
          size_bytes integer null,
          sha256 text null,
          attempt_nr integer not null,
          analysis_status text not null default 'pending',
          analysis_json jsonb null,
          feedback_md text null,
          error_code text null,
          idempotency_key text null,
          created_at timestamptz not null default now(),
          completed_at timestamptz null,
          unique (course_id, task_id, student_sub, attempt_nr)
        )
        """,
        # cleanup
        "truncate table staging.submissions",
        "truncate table public.learning_submissions",
        "truncate table public.module_section_releases, public.course_modules cascade",
        "truncate table public.course_memberships, public.courses cascade",
        "truncate table public.unit_tasks, public.unit_sections, public.units cascade",
    ]
    _execute_statements(conn, statements)


def _seed_world(conn: psycopg.Connection) -> tuple[uuid.UUID, dict[str, uuid.UUID]]:
    # Prepare a single course with one unit and two sections; one task on section A
    course_id = uuid.uuid4()
    unit_id = uuid.uuid4()
    section_a = uuid.uuid4()
    section_b = uuid.uuid4()
    task_id = uuid.uuid4()
    student_sub = "student-1"
    with conn.cursor() as cur:  # type: ignore[attr-defined]
        cur.execute("insert into public.courses (id, title, teacher_id) values (%s, %s, %s)", (course_id, "Kurs", "teacher-sub"))
        cur.execute("insert into public.course_memberships (course_id, student_id) values (%s, %s)", (course_id, student_sub))
        cur.execute("insert into public.units (id, title, summary, author_id) values (%s, %s, %s, %s)", (unit_id, "Einheit", None, "teacher-sub"))
        cur.execute("insert into public.unit_sections (id, unit_id, title, position) values (%s, %s, %s, %s)", (section_a, unit_id, "A", 1))
        cur.execute("insert into public.unit_sections (id, unit_id, title, position) values (%s, %s, %s, %s)", (section_b, unit_id, "B", 2))
        cur.execute("insert into public.course_modules (course_id, unit_id, position) values (%s, %s, %s)", (course_id, unit_id, 1))
        # release section A only
        cur.execute("select id from public.course_modules where course_id = %s and unit_id = %s", (course_id, unit_id))
        cm_id = cur.fetchone()[0]
        cur.execute("insert into public.module_section_releases (course_module_id, section_id, visible, released_at, released_by) values (%s, %s, true, now(), %s)", (cm_id, section_a, "teacher-sub"))
        # task on section A
        cur.execute("insert into public.unit_tasks (id, unit_id, section_id, instruction_md, position) values (%s, %s, %s, %s, %s)", (task_id, unit_id, section_a, "Aufgabe", 1))
    return course_id, {"unit": unit_id, "section_a": section_a, "section_b": section_b, "task": task_id, "student": student_sub}


def _seed_submissions(conn: psycopg.Connection, ids: dict[str, uuid.UUID | str]) -> None:
    task_id = ids["task"]
    student = ids["student"]
    # Two text submissions for same task (attempt nr 1 and 2)
    with conn.cursor() as cur:  # type: ignore[attr-defined]
        cur.execute(
            "insert into staging.submissions (id, task_id, student_sub, kind, text_body, created_at) values (%s, %s, %s, %s, %s, now() - interval '10 minutes')",
            (uuid.uuid4(), task_id, student, "text", "erste"),
        )
        cur.execute(
            "insert into staging.submissions (id, task_id, student_sub, kind, text_body, created_at) values (%s, %s, %s, %s, %s, now() - interval '5 minutes')",
            (uuid.uuid4(), task_id, student, "text", "zweite"),
        )
        # One image submission with minimal valid metadata
        cur.execute(
            "insert into staging.submissions (id, task_id, student_sub, kind, storage_key, mime_type, size_bytes, sha256, created_at) values (%s, %s, %s, %s, %s, %s, %s, %s, now())",
            (
                uuid.uuid4(),
                task_id,
                student,
                "image",
                "submissions/img1.jpg",
                "image/jpeg",
                1234,
                "a" * 64,
            ),
        )


@pytest.mark.skipif(psycopg is None, reason="psycopg required for migration CLI integration test")
def test_submissions_import_attempts_and_course_resolution() -> None:
    from backend.tools import legacy_migration

    db_utils.require_db_or_skip()
    dsn = os.getenv("SERVICE_ROLE_DSN") or os.getenv("RLS_TEST_SERVICE_DSN")
    if not dsn:
        pytest.skip("SERVICE_ROLE_DSN required for migration CLI test")

    with psycopg.connect(dsn, autocommit=True) as conn:  # type: ignore[arg-type]
        _prepare_tables(conn)
        course_id, ids = _seed_world(conn)
        _seed_submissions(conn, ids)

    runner = CliRunner()
    result = runner.invoke(
        legacy_migration.cli,
        ["--db-dsn", dsn, "--source", "test-submissions"],
    )
    assert result.exit_code == 0, result.output

    with psycopg.connect(dsn, autocommit=True) as conn:  # type: ignore[arg-type]
        rows = _fetch_all(
            conn,
            "select course_id::uuid, task_id::uuid, student_sub, kind, attempt_nr from public.learning_submissions order by attempt_nr",
        )
        # two text + one image imported
        assert len(rows) == 3
        assert rows[0][0] == course_id
        # attempts 1..3, ordered by created_at
        assert [r[4] for r in rows] == [1, 2, 3]

        audits = _fetch_all(
            conn,
            "select entity, status from public.import_audit_mappings",
        )
        assert any(a[0] == "legacy_submission" and a[1] == "ok" for a in audits)
