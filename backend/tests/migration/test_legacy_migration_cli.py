from __future__ import annotations

import os
import re
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


def _fetch_one(conn: psycopg.Connection, sql: str, *params) -> tuple | None:
    with conn.cursor() as cur:  # type: ignore[attr-defined]
        cur.execute(sql, params or None)
        return cur.fetchone()


def _fetch_all(conn: psycopg.Connection, sql: str, *params) -> list[tuple]:
    with conn.cursor() as cur:  # type: ignore[attr-defined]
        cur.execute(sql, params or None)
        return list(cur.fetchall())


def _prepare_tables(conn: psycopg.Connection) -> None:
    statements = [
        "create schema if not exists staging",
        """
        create table if not exists staging.users (
            id uuid primary key,
            sub text not null
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
        """
        create table if not exists public.legacy_user_map (
            legacy_id uuid primary key,
            sub text unique
        )
        """,
        "truncate table staging.users",
        # Additional empty staging to prevent later phases from failing in dry-run
        "create table if not exists staging.courses (id uuid, title text, creator_id uuid)",
        "create table if not exists staging.course_students (course_id uuid, student_id uuid, created_at timestamptz)",
        "create table if not exists staging.learning_units (id uuid, title text, description text, creator_id uuid)",
        "create table if not exists staging.unit_sections (id uuid, unit_id uuid, title text, order_in_unit int)",
        # Clean up any leftover staging.materials_json artifacts from previous runs
        # (tables or composite types) to keep tests idempotent.
        "drop table if exists staging.materials_json",
        "drop type if exists staging.materials_json cascade",
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
        "truncate table staging.courses",
        "truncate table staging.course_students",
        "truncate table staging.learning_units",
        "truncate table staging.unit_sections",
        "truncate table staging.materials_json",
        "truncate table staging.tasks_base",
        "truncate table staging.tasks_regular",
        "create table if not exists staging.course_unit_assignments (course_id uuid, unit_id uuid, position integer)",
        "create table if not exists staging.section_releases (course_id uuid, unit_id uuid, section_id uuid, visible boolean, released_at timestamptz)",
        "truncate table staging.course_unit_assignments",
        "truncate table staging.section_releases",
        # Truncate audit tables in one statement due to FK constraint
        "truncate table public.import_audit_mappings, public.import_audit_runs cascade",
        "truncate table public.legacy_user_map",
    ]
    _execute_statements(conn, statements)


def _seed_staging_users(conn: psycopg.Connection) -> list[tuple[uuid.UUID, str]]:
    users = [
        (uuid.uuid4(), "sub-student-1"),
        (uuid.uuid4(), "sub-teacher-2"),
    ]
    with conn.cursor() as cur:  # type: ignore[attr-defined]
        cur.executemany(
            "insert into staging.users (id, sub) values (%s, %s)",
            users,
        )
    return users


@pytest.mark.skipif(psycopg is None, reason="psycopg required for migration CLI integration test")
def test_identity_map_cli_creates_audit_entries_and_imports_users() -> None:
    """CLI should support dry-run + real-run and emit audit information."""
    from backend.tools import legacy_migration  # Import must succeed for test to continue

    db_utils.require_db_or_skip()

    dsn = os.getenv("SERVICE_ROLE_DSN") or os.getenv("RLS_TEST_SERVICE_DSN")
    if not dsn:
        pytest.skip("SERVICE_ROLE_DSN required for migration CLI test")

    with psycopg.connect(dsn, autocommit=True) as conn:  # type: ignore[arg-type]
        _prepare_tables(conn)
        staged = _seed_staging_users(conn)

    runner = CliRunner()

    dry_run_result = runner.invoke(
        legacy_migration.cli,
        ["--db-dsn", dsn, "--dry-run", "--source", "test-snapshot"],
    )
    assert dry_run_result.exit_code == 0, dry_run_result.output
    assert "dry-run" in dry_run_result.output.lower()
    dry_run_id_match = re.search(r"Run ID:\s*([0-9a-f-]{36})", dry_run_result.output)
    assert dry_run_id_match, dry_run_result.output
    dry_run_id = uuid.UUID(dry_run_id_match.group(1))

    with psycopg.connect(dsn, autocommit=True) as conn:  # type: ignore[arg-type]
        count_legacy = _fetch_one(conn, "select count(*) from public.legacy_user_map")
        assert count_legacy and count_legacy[0] == 0
        audit_runs = _fetch_one(
            conn,
            "select source, notes from public.import_audit_runs where id = %s",
            dry_run_id,
        )
        assert audit_runs == ("test-snapshot", "dry-run")
        entries = _fetch_all(
            conn,
            """
            select legacy_id, status, reason
            from public.import_audit_mappings
            where run_id = %s and entity = 'legacy_user'
            order by legacy_id
            """,
            dry_run_id,
        )
        assert len(entries) == len(staged)
        assert all(row[1] == "skip" and row[2] == "dry-run" for row in entries)

    real_run_result = runner.invoke(
        legacy_migration.cli,
        ["--db-dsn", dsn, "--source", "test-snapshot"],
    )
    assert real_run_result.exit_code == 0, real_run_result.output
    assert "Processed 2 legacy users" in real_run_result.output
    real_run_id_match = re.search(r"Run ID:\s*([0-9a-f-]{36})", real_run_result.output)
    assert real_run_id_match, real_run_result.output
    real_run_id = uuid.UUID(real_run_id_match.group(1))

    with psycopg.connect(dsn, autocommit=True) as conn:  # type: ignore[arg-type]
        count_legacy = _fetch_one(conn, "select count(*) from public.legacy_user_map")
        assert count_legacy and count_legacy[0] == len(staged)
        mappings = _fetch_all(
            conn,
            "select legacy_id::uuid, sub from public.legacy_user_map order by legacy_id",
        )
        # Order by legacy_id differs from insertion order; compare as sets
        assert set((row[0], row[1]) for row in mappings) == set(staged)
        audit_runs = _fetch_one(
            conn,
            "select source, notes from public.import_audit_runs where id = %s",
            real_run_id,
        )
        assert audit_runs == ("test-snapshot", None)
        entries = _fetch_all(
            conn,
            """
            select legacy_id::uuid, status, reason
            from public.import_audit_mappings
            where run_id = %s and entity = 'legacy_user'
            order by legacy_id::uuid
            """,
            real_run_id,
        )
        assert len(entries) == len(staged)
        assert all(row[1] == "ok" and row[2] is None for row in entries)
        assert {row[0] for row in entries} == {user[0] for user in staged}
