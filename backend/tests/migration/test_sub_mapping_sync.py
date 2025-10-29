from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest
from click.testing import CliRunner

psycopg = None
try:  # pragma: no cover - optional at runtime
    import psycopg  # type: ignore
except Exception:  # pragma: no cover
    psycopg = None  # type: ignore


def _exec(conn: "psycopg.Connection", *stmts: str) -> None:  # type: ignore[name-defined]
    with conn.cursor() as cur:  # type: ignore[attr-defined]
        for s in stmts:
            cur.execute(s)


def _fetch_all(conn: "psycopg.Connection", sql: str):  # type: ignore[name-defined]
    with conn.cursor() as cur:  # type: ignore[attr-defined]
        cur.execute(sql)
        return list(cur.fetchall())


def _setup_minimal_schema(conn: "psycopg.Connection") -> None:  # type: ignore[name-defined]
    _exec(
        conn,
        "create extension if not exists pgcrypto",
        # Mapping table
        "create table if not exists public.legacy_user_map (legacy_id uuid primary key, sub text unique)",
        "truncate table public.legacy_user_map",
        # Minimal target tables with only relevant columns
        "create table if not exists public.courses (id uuid primary key default gen_random_uuid(), title text, teacher_id text not null)",
        "create table if not exists public.units (id uuid primary key default gen_random_uuid(), title text, author_id text not null)",
        "create table if not exists public.course_memberships (course_id uuid not null, student_id text not null, created_at timestamptz default now(), primary key(course_id, student_id))",
        "create table if not exists public.learning_submissions (id uuid primary key default gen_random_uuid(), course_id uuid not null, task_id uuid not null, student_sub text not null, kind text not null, attempt_nr int not null)",
        "create table if not exists public.module_section_releases (course_module_id uuid, section_id uuid, visible boolean default true, released_at timestamptz default now(), released_by text not null)",
        # Clean slate (CASCADE to account for existing FKs in test DB)
        "truncate table public.courses, public.units, public.course_memberships, public.learning_submissions, public.module_section_releases cascade",
    )


def _seed_with_legacy_placeholders(conn: "psycopg.Connection") -> tuple[list[uuid.UUID], dict[str, str]]:  # type: ignore[name-defined]
    # Two legacy users, with placeholder-format references in multiple tables
    u1, u2 = uuid.uuid4(), uuid.uuid4()
    mapping = {
        str(u1): str(uuid.uuid4()),
        str(u2): str(uuid.uuid4()),
    }
    with conn.cursor() as cur:  # type: ignore[attr-defined]
        cur.executemany(
            "insert into public.legacy_user_map (legacy_id, sub) values (%s::uuid, %s)",
            [(u1, f"legacy:{u1}"), (u2, f"legacy:{u2}")],
        )
        # Courses (teacher)
        cur.execute("insert into public.courses (title, teacher_id) values (%s, %s)", ("Kurs A", f"legacy:{u1}"))
        # Units (author)
        cur.execute("insert into public.units (title, author_id) values (%s, %s)", ("Einheit A", f"legacy:{u2}"))
        # Memberships (student)
        cur.execute("insert into public.course_memberships (course_id, student_id) select id, %s from public.courses limit 1", (f"legacy:{u2}",))
        # (Optional) Submissions skipped here to avoid heavy FK setup; mapping tool handles it if present.
        # (Optional) Releases skipped here to avoid FK setup; mapping tool handles it if present.
    return [u1, u2], mapping


@pytest.mark.skipif(psycopg is None, reason="psycopg required for mapping sync test")
def test_sub_mapping_sync_updates_placeholders_and_is_idempotent(tmp_path: Path) -> None:
    from backend.tools import sub_mapping_sync  # type: ignore

    dsn = os.getenv("SERVICE_ROLE_DSN") or os.getenv("RLS_TEST_SERVICE_DSN")
    if not dsn:
        pytest.skip("SERVICE_ROLE_DSN required for mapping sync test")

    # Prepare DB state with placeholder references
    with psycopg.connect(dsn, autocommit=True) as conn:  # type: ignore[arg-type]
        _setup_minimal_schema(conn)
        users, mapping = _seed_with_legacy_placeholders(conn)

    # Write CSV mapping legacy_id,sub for the two users
    csv_path = tmp_path / "map.csv"
    with csv_path.open("w", encoding="utf-8") as f:
        f.write("legacy_id,sub\n")
        for legacy, sub in mapping.items():
            f.write(f"{legacy},{sub}\n")

    runner = CliRunner()
    res = runner.invoke(sub_mapping_sync.cli, ["--db-dsn", dsn, "--mapping-csv", str(csv_path)])
    assert res.exit_code == 0, res.output
    assert "Updated legacy_user_map" in res.output

    with psycopg.connect(dsn, autocommit=True) as conn:  # type: ignore[arg-type]
        # All placeholder refs should be replaced
        counts = _fetch_all(
            conn,
            """
            select
              (select count(*) from public.legacy_user_map where sub like 'legacy:%') as m_count,
              (select count(*) from public.courses where teacher_id like 'legacy:%') as c_count,
              (select count(*) from public.units where author_id like 'legacy:%') as u_count,
              (select count(*) from public.course_memberships where student_id like 'legacy:%') as cm_count,
              (select count(*) from public.learning_submissions where student_sub like 'legacy:%') as s_count,
              (select count(*) from public.module_section_releases where released_by like 'legacy:%') as r_count
            """,
        )
        m_count, c_count, u_count, cm_count, s_count, r_count = counts[0]
        assert (m_count, c_count, u_count, cm_count, s_count, r_count) == (0, 0, 0, 0, 0, 0)

    # Idempotence: running again should succeed and keep counts at zero
    res2 = runner.invoke(sub_mapping_sync.cli, ["--db-dsn", dsn, "--mapping-csv", str(csv_path)])
    assert res2.exit_code == 0, res2.output
    with psycopg.connect(dsn, autocommit=True) as conn:  # type: ignore[arg-type]
        counts = _fetch_all(
            conn,
            """
            select
              (select count(*) from public.legacy_user_map where sub like 'legacy:%') as m_count,
              (select count(*) from public.courses where teacher_id like 'legacy:%') as c_count,
              (select count(*) from public.units where author_id like 'legacy:%') as u_count,
              (select count(*) from public.course_memberships where student_id like 'legacy:%') as cm_count,
              (select count(*) from public.learning_submissions where student_sub like 'legacy:%') as s_count,
              (select count(*) from public.module_section_releases where released_by like 'legacy:%') as r_count
            """,
        )
        assert counts[0] == (0, 0, 0, 0, 0, 0)
