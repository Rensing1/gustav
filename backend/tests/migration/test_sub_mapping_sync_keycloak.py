from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest
from click.testing import CliRunner

psycopg = None
try:  # pragma: no cover
    import psycopg  # type: ignore
except Exception:  # pragma: no cover
    psycopg = None  # type: ignore


def _exec(conn: "psycopg.Connection", *stmts: str) -> None:  # type: ignore[name-defined]
    with conn.cursor() as cur:  # type: ignore[attr-defined]
        for s in stmts:
            cur.execute(s)


def _setup_minimal_schema(conn: "psycopg.Connection") -> None:  # type: ignore[name-defined]
    _exec(
        conn,
        "create extension if not exists pgcrypto",
        "create table if not exists public.legacy_user_map (legacy_id uuid primary key, sub text unique)",
        "truncate table public.legacy_user_map",
        "create table if not exists public.courses (id uuid primary key default gen_random_uuid(), title text, teacher_id text not null)",
        "create table if not exists public.units (id uuid primary key default gen_random_uuid(), title text, author_id text not null)",
        "create table if not exists public.course_memberships (course_id uuid not null, student_id text not null, created_at timestamptz default now(), primary key(course_id, student_id))",
        "truncate table public.courses, public.units, public.course_memberships cascade",
    )


def _seed_placeholders(conn: "psycopg.Connection") -> tuple[list[uuid.UUID], dict[str, str]]:  # type: ignore[name-defined]
    u1, u2 = uuid.uuid4(), uuid.uuid4()
    mapping = {str(u1): str(uuid.uuid4()), str(u2): str(uuid.uuid4())}
    with conn.cursor() as cur:  # type: ignore[attr-defined]
        cur.executemany(
            "insert into public.legacy_user_map (legacy_id, sub) values (%s::uuid, %s)",
            [(u1, f"legacy:{u1}"), (u2, f"legacy:{u2}")],
        )
        # One course per user placeholder
        cur.execute("insert into public.courses (title, teacher_id) values (%s, %s)", ("Kurs-KC", f"legacy:{u1}"))
        cur.execute("insert into public.units (title, author_id) values (%s, %s)", ("Unit-KC", f"legacy:{u2}"))
        cur.execute("insert into public.course_memberships (course_id, student_id) select id, %s from public.courses limit 1", (f"legacy:{u2}",))
    return [u1, u2], mapping


@pytest.mark.skipif(psycopg is None, reason="psycopg required for mapping sync test")
def test_keycloak_email_mode_updates_placeholders(monkeypatch, tmp_path: Path) -> None:
    from backend.tools import sub_mapping_sync  # type: ignore

    dsn = os.getenv("SERVICE_ROLE_DSN") or os.getenv("RLS_TEST_SERVICE_DSN")
    if not dsn:
        pytest.skip("SERVICE_ROLE_DSN required for mapping sync test")

    with psycopg.connect(dsn, autocommit=True) as conn:  # type: ignore[arg-type]
        _setup_minimal_schema(conn)
        users, mapping = _seed_placeholders(conn)

    # Monkeypatch the internal KC mapping function to avoid network
    def fake_kc_map(**kwargs):
        # Return list[(legacy_id, sub)]
        return list(mapping.items())

    monkeypatch.setattr(sub_mapping_sync, "_kc_email_mapping", lambda **kw: fake_kc_map(**kw))

    runner = CliRunner()
    res = runner.invoke(
        sub_mapping_sync.cli,
        [
            "--db-dsn",
            dsn,
            "--from-keycloak",
            "--legacy-dsn",
            "postgresql://does/not/matter",
            "--kc-base-url",
            "http://kc",
            "--kc-host-header",
            "id.localhost",
            "--realm",
            "gustav",
            "--kc-admin-user",
            "admin",
            "--kc-admin-pass",
            "admin",
        ],
    )
    assert res.exit_code == 0, res.output
    assert "Updated legacy_user_map" in res.output

    with psycopg.connect(dsn, autocommit=True) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:  # type: ignore[attr-defined]
            cur.execute("select count(*) from public.courses where teacher_id like 'legacy:%'")
            assert cur.fetchone()[0] == 0
            cur.execute("select count(*) from public.units where author_id like 'legacy:%'")
            assert cur.fetchone()[0] == 0
            cur.execute("select count(*) from public.course_memberships where student_id like 'legacy:%'")
            assert cur.fetchone()[0] == 0

