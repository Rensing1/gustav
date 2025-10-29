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
        create table if not exists staging.materials_json (
            id uuid primary key,
            section_id uuid not null,
            kind text not null,
            title text null,
            body_md text null,
            storage_key text null,
            mime_type text null,
            size_bytes bigint null,
            sha256 text null,
            position int not null,
            created_at timestamptz null,
            legacy_url text null
        )
        """,
        """
        create table if not exists staging.tasks_base (
            id uuid primary key,
            instruction_md text not null,
            assessment_criteria jsonb null,
            hints_md text null
        )
        """,
        """
        create table if not exists staging.tasks_regular (
            id uuid primary key,
            section_id uuid not null,
            order_in_section int not null,
            max_attempts int null,
            created_at timestamptz null
        )
        """,
        # auxiliary empty staging to avoid other phases interfering
        "create table if not exists staging.users (id uuid, sub text)",
        "create table if not exists staging.courses (id uuid, title text, creator_id uuid)",
        "create table if not exists staging.course_students (course_id uuid, student_id uuid, created_at timestamptz)",
        "create table if not exists staging.course_unit_assignments (course_id uuid, unit_id uuid, position integer)",
        "create table if not exists staging.section_releases (course_id uuid, unit_id uuid, section_id uuid, visible boolean, released_at timestamptz)",
        # target tables
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
        create table if not exists public.unit_materials (
            id uuid primary key,
            unit_id uuid not null references public.units(id) on delete cascade,
            section_id uuid not null references public.unit_sections(id) on delete cascade,
            kind text not null,
            title text null,
            body_md text null,
            storage_key text null,
            mime_type text null,
            size_bytes bigint null,
            sha256 text null,
            position int not null,
            created_at timestamptz not null default now()
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
        # audit tables
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
        "truncate table staging.materials_json",
        "truncate table staging.tasks_regular",
        "truncate table staging.tasks_base",
        "truncate table staging.users",
        "truncate table staging.courses",
        "truncate table staging.course_students",
        "truncate table staging.course_unit_assignments",
        "truncate table staging.section_releases",
        "truncate table public.unit_materials",
        "truncate table public.unit_tasks cascade",
        "truncate table public.unit_sections cascade",
        "truncate table public.units cascade",
        "truncate table public.import_audit_mappings, public.import_audit_runs cascade",
    ]
    _execute_statements(conn, statements)


def _seed_units_sections(conn: psycopg.Connection) -> tuple[uuid.UUID, list[uuid.UUID]]:
    unit_id = uuid.uuid4()
    section_ids = [uuid.uuid4(), uuid.uuid4()]
    with conn.cursor() as cur:  # type: ignore[attr-defined]
        cur.execute(
            "insert into public.units (id, title, summary, author_id) values (%s, %s, %s, %s)",
            (unit_id, "Einheit", None, "author-sub"),
        )
        cur.execute(
            "insert into public.unit_sections (id, unit_id, title, position) values (%s, %s, %s, %s)",
            (section_ids[0], unit_id, "Abschnitt 1", 1),
        )
        cur.execute(
            "insert into public.unit_sections (id, unit_id, title, position) values (%s, %s, %s, %s)",
            (section_ids[1], unit_id, "Abschnitt 2", 2),
        )
    return unit_id, section_ids


def _seed_materials(conn: psycopg.Connection, section_ids: list[uuid.UUID]) -> tuple[uuid.UUID, uuid.UUID]:
    mid_md = uuid.uuid4()
    mid_file = uuid.uuid4()
    with conn.cursor() as cur:  # type: ignore[attr-defined]
        # Markdown material
        cur.execute(
            "insert into staging.materials_json (id, section_id, kind, title, body_md, position) values (%s, %s, %s, %s, %s, %s)",
            (mid_md, section_ids[0], "markdown", "Titel", "Hello MD", 1),
        )
        # File material with missing metadata → fallback
        cur.execute(
            "insert into staging.materials_json (id, section_id, kind, title, storage_key, mime_type, size_bytes, sha256, legacy_url, position) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (mid_file, section_ids[1], "file", "Datei", "legacy/path/file.pdf", "application/pdf", None, None, "http://legacy.local/f.pdf", 1),
        )
    return mid_md, mid_file


def _seed_tasks(conn: psycopg.Connection, section_id: uuid.UUID) -> uuid.UUID:
    tid = uuid.uuid4()
    with conn.cursor() as cur:  # type: ignore[attr-defined]
        cur.execute(
            "insert into staging.tasks_base (id, instruction_md, assessment_criteria, hints_md) values (%s, %s, %s::jsonb, %s)",
            (tid, "Instruktion", '[" Kriterium 1 ", "", "Kriterium 1"]', "Hinweise"),
        )
        cur.execute(
            "insert into staging.tasks_regular (id, section_id, order_in_section, max_attempts) values (%s, %s, %s, %s)",
            (tid, section_id, 1, 3),
        )
    return tid


@pytest.mark.skipif(psycopg is None, reason="psycopg required for migration CLI integration test")
def test_materials_and_tasks_migrate_with_audit() -> None:
    from backend.tools import legacy_migration

    db_utils.require_db_or_skip()
    dsn = os.getenv("SERVICE_ROLE_DSN") or os.getenv("RLS_TEST_SERVICE_DSN")
    if not dsn:
        pytest.skip("SERVICE_ROLE_DSN required for migration CLI test")

    with psycopg.connect(dsn, autocommit=True) as conn:  # type: ignore[arg-type]
        _prepare_tables(conn)
        unit_id, section_ids = _seed_units_sections(conn)
        mid_md, mid_file = _seed_materials(conn, section_ids)
        tid = _seed_tasks(conn, section_ids[0])

    runner = CliRunner()
    result = runner.invoke(
        legacy_migration.cli,
        ["--db-dsn", dsn, "--source", "test-materials-tasks"],
    )
    assert result.exit_code == 0, result.output

    with psycopg.connect(dsn, autocommit=True) as conn:  # type: ignore[arg-type]
        mats = _fetch_all(
            conn,
            "select id::uuid, section_id::uuid, unit_id::uuid, kind, body_md from public.unit_materials order by id",
        )
        assert len(mats) == 2
        # Fallback for file without metadata should be markdown with note
        kinds = {m[3] for m in mats}
        assert kinds == {"markdown"}
        assert any("Datei nicht verfügbar" in (m[4] or "") for m in mats)

        tasks = _fetch_all(
            conn,
            "select id::uuid, unit_id::uuid, section_id::uuid, instruction_md, criteria, max_attempts, position from public.unit_tasks",
        )
        assert len(tasks) == 1
        t = tasks[0]
        assert t[1] == unit_id and t[2] == section_ids[0]
        assert t[4] == ["Kriterium 1"] and t[5] == 3 and t[6] == 1

        audits = _fetch_all(
            conn,
            "select entity, status from public.import_audit_mappings",
        )
        assert any(a[0] == "legacy_material" and a[1] == "ok" for a in audits)
        assert any(a[0] == "legacy_task" and a[1] == "ok" for a in audits)
