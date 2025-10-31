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
        create table if not exists staging.learning_units (
            id uuid primary key,
            title text not null,
            description text null,
            creator_id uuid not null
        )
        """,
        """
        create table if not exists staging.unit_sections (
            id uuid primary key,
            unit_id uuid not null,
            title text not null,
            order_in_unit integer not null
        )
        """,
        # target tables (if not already present via migrations)
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
        create table if not exists public.unit_sections (
            id uuid primary key,
            unit_id uuid not null references public.units(id) on delete cascade,
            title text not null,
            position integer not null,
            created_at timestamptz not null default now(),
            updated_at timestamptz not null default now(),
            unique (unit_id, position)
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
        "truncate table staging.learning_units",
        "truncate table staging.unit_sections",
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
        "create table if not exists staging.course_unit_assignments (course_id uuid, unit_id uuid, position integer)",
        "create table if not exists staging.section_releases (course_id uuid, unit_id uuid, section_id uuid, visible boolean, released_at timestamptz)",
        "truncate table staging.course_unit_assignments",
        "truncate table staging.section_releases",
        "truncate table public.unit_sections, public.units cascade",
        "truncate table public.legacy_user_map",
        "truncate table public.import_audit_mappings, public.import_audit_runs cascade",
    ]
    _execute_statements(conn, statements)


def _seed_identity(conn: psycopg.Connection) -> tuple[uuid.UUID, str]:
    legacy_author = uuid.uuid4()
    author_sub = "author-sub-xyz"
    with conn.cursor() as cur:  # type: ignore[attr-defined]
        cur.execute(
            "insert into public.legacy_user_map (legacy_id, sub) values (%s, %s)",
            (legacy_author, author_sub),
        )
    return legacy_author, author_sub


def _seed_units_sections(conn: psycopg.Connection, author_legacy: uuid.UUID) -> tuple[list[tuple], list[tuple]]:
    units = [
        (uuid.uuid4(), "Einheit A", "Desc A", author_legacy),
        (uuid.uuid4(), "Einheit B", None, author_legacy),
    ]
    with conn.cursor() as cur:  # type: ignore[attr-defined]
        cur.executemany(
            "insert into staging.learning_units (id, title, description, creator_id) values (%s, %s, %s, %s)",
            units,
        )

    sections = [
        (uuid.uuid4(), units[0][0], "Abschnitt 1", 1),
        (uuid.uuid4(), units[0][0], "Abschnitt 2", 2),
        (uuid.uuid4(), units[1][0], "Abschnitt B1", 1),
    ]
    with conn.cursor() as cur:  # type: ignore[attr-defined]
        cur.executemany(
            "insert into staging.unit_sections (id, unit_id, title, order_in_unit) values (%s, %s, %s, %s)",
            sections,
        )

    return units, sections


@pytest.mark.skipif(psycopg is None, reason="psycopg required for migration CLI integration test")
def test_units_and_sections_migrate_with_audit() -> None:
    from backend.tools import legacy_migration

    db_utils.require_db_or_skip()
    dsn = os.getenv("SERVICE_ROLE_DSN") or os.getenv("RLS_TEST_SERVICE_DSN")
    if not dsn:
        pytest.skip("SERVICE_ROLE_DSN required for migration CLI test")

    with psycopg.connect(dsn, autocommit=True) as conn:  # type: ignore[arg-type]
        _prepare_tables(conn)
        author_legacy, author_sub = _seed_identity(conn)
        units, sections = _seed_units_sections(conn, author_legacy)

    runner = CliRunner()
    result = runner.invoke(
        legacy_migration.cli,
        ["--db-dsn", dsn, "--source", "test-units-sections"],
    )
    assert result.exit_code == 0, result.output

    with psycopg.connect(dsn, autocommit=True) as conn:  # type: ignore[arg-type]
        stored_units = _fetch_all(
            conn,
            "select id::uuid, title, summary, author_id from public.units order by title",
        )
        assert len(stored_units) == len(units)
        assert all(row[3] == author_sub for row in stored_units)

        stored_sections = _fetch_all(
            conn,
            "select id::uuid, unit_id::uuid, title, position from public.unit_sections order by title",
        )
        assert len(stored_sections) == len(sections)
        # ensure positions mapped from order_in_unit
        expected_positions = {s[0]: s[3] for s in sections}
        assert all(expected_positions[row[0]] == row[3] for row in stored_sections)

        audits = _fetch_all(
            conn,
            "select entity, status from public.import_audit_mappings order by entity",
        )
        # must contain unit and section entries with status ok
        assert any(a[0] == "legacy_unit" and a[1] == "ok" for a in audits)
        assert any(a[0] == "legacy_unit_section" and a[1] == "ok" for a in audits)
