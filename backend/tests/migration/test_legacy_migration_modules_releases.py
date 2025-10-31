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
        # target tables (if not already present via migrations)
        """
        create table if not exists public.courses (
            id uuid primary key,
            title text not null,
            teacher_id text not null,
            created_at timestamptz not null default now()
        )
        """,
        """
        create table if not exists public.units (
            id uuid primary key,
            title text not null,
            summary text null,
            author_id text not null,
            created_at timestamptz not null default now(),
            updated_at timestamptz not null default now()
        )
        """,
        """
        create table if not exists public.course_modules (
            id uuid primary key default gen_random_uuid(),
            course_id uuid not null references public.courses(id) on delete cascade,
            unit_id uuid not null references public.units(id) on delete cascade,
            position integer not null,
            unique (course_id, position),
            unique (course_id, unit_id)
        )
        """,
        """
        create table if not exists public.unit_sections (
            id uuid primary key,
            unit_id uuid not null references public.units(id) on delete cascade,
            title text not null,
            position integer not null
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
        # cleanup
        "truncate table staging.course_unit_assignments",
        "truncate table staging.section_releases",
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
        "truncate table staging.materials_json",
        "truncate table staging.tasks_base",
        "truncate table staging.tasks_regular",
        "truncate table public.module_section_releases, public.course_modules cascade",
        "truncate table public.unit_materials, public.unit_sections cascade",
        "truncate table public.units cascade",
        "truncate table public.course_memberships, public.courses cascade",
        "truncate table public.legacy_user_map",
        "truncate table public.import_audit_mappings, public.import_audit_runs cascade",
    ]
    _execute_statements(conn, statements)


def _seed_courses_units_sections(conn: psycopg.Connection) -> tuple[list[uuid.UUID], list[uuid.UUID], list[uuid.UUID]]:
    course_ids = [uuid.uuid4()]
    unit_ids = [uuid.uuid4()]
    section_ids = [uuid.uuid4()]
    with conn.cursor() as cur:  # type: ignore[attr-defined]
        cur.execute(
            "insert into public.courses (id, title, teacher_id) values (%s, %s, %s)",
            (course_ids[0], "Testkurs", "teacher-sub"),
        )
        cur.execute(
            "insert into public.units (id, title, summary, author_id) values (%s, %s, %s, %s)",
            (unit_ids[0], "Einheit", None, "teacher-sub"),
        )
        cur.execute(
            "insert into public.unit_sections (id, unit_id, title, position) values (%s, %s, %s, %s)",
            (section_ids[0], unit_ids[0], "Abschnitt 1", 1),
        )
    return course_ids, unit_ids, section_ids


def _seed_staging_modules_releases(conn: psycopg.Connection, course_id: uuid.UUID, unit_id: uuid.UUID, section_id: uuid.UUID) -> None:
    with conn.cursor() as cur:  # type: ignore[attr-defined]
        cur.execute(
            "insert into staging.course_unit_assignments (course_id, unit_id, position) values (%s, %s, %s)",
            (course_id, unit_id, 1),
        )
        cur.execute(
            "insert into staging.section_releases (course_id, unit_id, section_id, visible, released_at) values (%s, %s, %s, %s, now())",
            (course_id, unit_id, section_id, True),
        )


@pytest.mark.skipif(psycopg is None, reason="psycopg required for migration CLI integration test")
def test_modules_and_releases_migrate_with_audit() -> None:
    from backend.tools import legacy_migration

    db_utils.require_db_or_skip()
    dsn = os.getenv("SERVICE_ROLE_DSN") or os.getenv("RLS_TEST_SERVICE_DSN")
    if not dsn:
        pytest.skip("SERVICE_ROLE_DSN required for migration CLI test")

    with psycopg.connect(dsn, autocommit=True) as conn:  # type: ignore[arg-type]
        _prepare_tables(conn)
        course_ids, unit_ids, section_ids = _seed_courses_units_sections(conn)
        _seed_staging_modules_releases(conn, course_ids[0], unit_ids[0], section_ids[0])

    runner = CliRunner()
    result = runner.invoke(
        legacy_migration.cli,
        ["--db-dsn", dsn, "--source", "test-modules-releases"],
    )
    assert result.exit_code == 0, result.output

    with psycopg.connect(dsn, autocommit=True) as conn:  # type: ignore[arg-type]
        modules = _fetch_all(
            conn,
            "select course_id::uuid, unit_id::uuid, position from public.course_modules",
        )
        assert modules and modules[0][0] == course_ids[0] and modules[0][1] == unit_ids[0] and modules[0][2] == 1

        releases = _fetch_all(
            conn,
            "select r.section_id::uuid, r.visible from public.module_section_releases r",
        )
        assert releases and releases[0][0] == section_ids[0] and releases[0][1] is True

        audits = _fetch_all(
            conn,
            "select entity, status from public.import_audit_mappings",
        )
        assert any(a[0] == "legacy_course_module" and a[1] == "ok" for a in audits)
        assert any(a[0] == "legacy_section_release" and a[1] == "ok" for a in audits)
