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
        """
        create table if not exists staging.courses (
            id uuid primary key,
            title text not null,
            creator_id uuid not null
        )
        """,
        """
        create table if not exists staging.course_unit_assignments (
            course_id uuid not null,
            unit_id uuid not null,
            position integer null
        )
        """,
        """
        create table if not exists staging.section_releases (
            course_id uuid not null,
            unit_id uuid not null,
            section_id uuid not null,
            visible boolean not null default true,
            released_at timestamptz null
        )
        """,
        """
        create table if not exists staging.course_students (
            course_id uuid not null,
            student_id uuid not null,
            created_at timestamptz not null default now()
        )
        """,
        """
        create table if not exists public.courses (
            id uuid primary key,
            title text not null,
            teacher_id text not null,
            created_at timestamptz not null default now()
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
        create table if not exists public.legacy_user_map (
            legacy_id uuid primary key,
            sub text unique
        )
        """,
        """
        create table if not exists public.import_audit_runs (
            id uuid primary key default gen_random_uuid(),
            source text not null,
            started_at_utc timestamptz not null default now(),
            ended_at_utc timestamptz null,
            notes text null
        )
        """,
        """
        create table if not exists public.import_audit_mappings (
            run_id uuid not null references public.import_audit_runs(id) on delete cascade,
            entity text not null,
            legacy_id text not null,
            target_table text not null,
            target_id text null,
            status text not null check (status in ('ok','skip','conflict','error')),
            reason text null,
            created_at_utc timestamptz not null default now()
        )
        """,
        "truncate table staging.courses",
        "truncate table staging.course_students",
        "create table if not exists staging.learning_units (id uuid, title text, description text, creator_id uuid)",
        "create table if not exists staging.unit_sections (id uuid, unit_id uuid, title text, order_in_unit int)",
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
        "truncate table staging.learning_units",
        "truncate table staging.unit_sections",
        "truncate table staging.materials_json",
        "truncate table staging.tasks_base",
        "truncate table staging.tasks_regular",
        "truncate table staging.course_unit_assignments",
        "truncate table staging.section_releases",
        # Truncate memberships and courses together due to FK
        "truncate table public.course_memberships, public.courses cascade",
        "truncate table public.legacy_user_map",
        # Truncate audit tables together due to FK
        "truncate table public.import_audit_mappings, public.import_audit_runs cascade",
    ]
    _execute_statements(conn, statements)


def _seed_identity(conn: psycopg.Connection) -> tuple[uuid.UUID, str]:
    legacy_teacher = uuid.uuid4()
    teacher_sub = "teacher-sub"
    with conn.cursor() as cur:  # type: ignore[attr-defined]
        cur.execute(
            "insert into public.legacy_user_map (legacy_id, sub) values (%s, %s)",
            (legacy_teacher, teacher_sub),
        )
    return legacy_teacher, teacher_sub


def _seed_students(conn: psycopg.Connection) -> list[tuple[uuid.UUID, str]]:
    rows = [
        (uuid.uuid4(), "student-sub-1"),
        (uuid.uuid4(), "student-sub-2"),
    ]
    with conn.cursor() as cur:  # type: ignore[attr-defined]
        cur.executemany(
            "insert into public.legacy_user_map (legacy_id, sub) values (%s, %s)",
            rows,
        )
    return rows


def _seed_courses(conn: psycopg.Connection, teacher_id: uuid.UUID) -> list[tuple[uuid.UUID, str]]:
    courses = [
        (uuid.uuid4(), "Math 8b"),
        (uuid.uuid4(), "Physik Leistungskurs"),
    ]
    with conn.cursor() as cur:  # type: ignore[attr-defined]
        cur.executemany(
            "insert into staging.courses (id, title, creator_id) values (%s, %s, %s)",
            [(course_id, title, teacher_id) for course_id, title in courses],
        )
    return courses


def _seed_memberships(conn: psycopg.Connection, courses, students) -> None:
    items = []
    for idx, (course_id, _) in enumerate(courses):
        student = students[idx % len(students)]
        items.append((course_id, student[0]))
    with conn.cursor() as cur:  # type: ignore[attr-defined]
        cur.executemany(
            "insert into staging.course_students (course_id, student_id) values (%s, %s)",
            items,
        )


@pytest.mark.skipif(psycopg is None, reason="psycopg required for migration CLI integration test")
def test_courses_and_memberships_are_migrated_with_audit_entries() -> None:
    """CLI should import courses & memberships after identity map."""
    from backend.tools import legacy_migration  # pylint: disable=import-error

    db_utils.require_db_or_skip()

    dsn = os.getenv("SERVICE_ROLE_DSN") or os.getenv("RLS_TEST_SERVICE_DSN")
    if not dsn:
        pytest.skip("SERVICE_ROLE_DSN required for migration CLI test")

    with psycopg.connect(dsn, autocommit=True) as conn:  # type: ignore[arg-type]
        _prepare_tables(conn)
        teacher_legacy, teacher_sub = _seed_identity(conn)
        students = _seed_students(conn)
        courses = _seed_courses(conn, teacher_legacy)
        _seed_memberships(conn, courses, students)

    runner = CliRunner()
    result = runner.invoke(
        legacy_migration.cli,
        ["--db-dsn", dsn, "--source", "test-courses"],
    )
    assert result.exit_code == 0, result.output
    assert "Processed" in result.output and "legacy users" in result.output

    with psycopg.connect(dsn, autocommit=True) as conn:  # type: ignore[arg-type]
        stored_courses = _fetch_all(
            conn,
            "select id::uuid, title, teacher_id from public.courses order by title",
        )
        assert len(stored_courses) == len(courses)
        assert all(row[2] == teacher_sub for row in stored_courses)

        stored_memberships = _fetch_all(
            conn,
            "select course_id::uuid, student_id from public.course_memberships order by course_id",
        )
        assert len(stored_memberships) == len(courses)
        assert {row[1] for row in stored_memberships}.issubset({s[1] for s in students})

        audits = _fetch_all(
            conn,
            "select entity, legacy_id, status from public.import_audit_mappings order by entity, legacy_id",
        )
        assert any(row[0] == "legacy_user" for row in audits)
        assert any(row[0] == "legacy_course" for row in audits)

    rerun = runner.invoke(
        legacy_migration.cli,
        ["--db-dsn", dsn, "--source", "test-courses"],
    )
    assert rerun.exit_code == 0, rerun.output
    assert rerun.output.count("Processed") >= 1
