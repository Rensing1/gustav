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
        "create table if not exists staging.users (id uuid, sub text)",
        "create table if not exists staging.courses (id uuid, title text, creator_id uuid)",
        "create table if not exists staging.course_students (course_id uuid, student_id uuid, created_at timestamptz)",
        "create table if not exists staging.learning_units (id uuid, title text, description text, creator_id uuid)",
        "create table if not exists staging.unit_sections (id uuid, unit_id uuid, title text, order_in_unit int)",
        "create table if not exists staging.course_unit_assignments (course_id uuid, unit_id uuid, position int)",
        "create table if not exists staging.section_releases (course_id uuid, unit_id uuid, section_id uuid, visible boolean, released_at timestamptz)",
        "create table if not exists staging.materials_json (id uuid, section_id uuid, kind text, title text, body_md text, position int)",
        "create table if not exists staging.tasks_base (id uuid, instruction_md text, assessment_criteria jsonb, hints_md text)",
        "create table if not exists staging.tasks_regular (id uuid, section_id uuid, order_in_section int, max_attempts int, created_at timestamptz)",
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
        "create table if not exists public.legacy_user_map (legacy_id uuid, sub text)",
        "truncate table staging.users",
        "truncate table public.import_audit_mappings, public.import_audit_runs cascade",
        "truncate table public.legacy_user_map",
    ]
    _execute_statements(conn, statements)


@pytest.mark.skipif(psycopg is None, reason="psycopg required for migration CLI integration test")
def test_resume_skips_completed_identity_phase() -> None:
    from backend.tools import legacy_migration

    db_utils.require_db_or_skip()
    dsn = os.getenv("SERVICE_ROLE_DSN") or os.getenv("RLS_TEST_SERVICE_DSN")
    if not dsn:
        pytest.skip("SERVICE_ROLE_DSN required for migration CLI test")

    with psycopg.connect(dsn, autocommit=True) as conn:  # type: ignore[arg-type]
        _prepare_tables(conn)
        # create previous run marked as completed for identity_map phase
        with conn.cursor() as cur:  # type: ignore[attr-defined]
            cur.execute("insert into public.import_audit_runs (source, notes) values (%s, %s) returning id", ("resume-source", "failed: simulated"))
            resume_id = cur.fetchone()[0]
            cur.execute(
                "insert into public.import_audit_mappings(run_id, entity, legacy_id, target_table, status) values (%s, %s, %s, %s, %s)",
                (resume_id, "phase", "identity_map", "system", "ok"),
            )
        # place some staging users that would be imported if not skipped
        with conn.cursor() as cur:  # type: ignore[attr-defined]
            cur.execute("insert into staging.users (id, sub) values (%s, %s)", (uuid.uuid4(), "sub-1"))

    runner = CliRunner()
    result = runner.invoke(
        legacy_migration.cli,
        ["--db-dsn", dsn, "--source", "resume-run", "--resume-run", str(resume_id)],
    )
    assert result.exit_code == 0, result.output
    assert "Skipping phase identity_map" in result.output

    with psycopg.connect(dsn, autocommit=True) as conn:  # type: ignore[arg-type]
        rows = _fetch_all(conn, "select * from public.legacy_user_map")
        # skipped: no new entries created
        assert rows == []

