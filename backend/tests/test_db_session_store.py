"""
Integration-like tests for the Postgres-backed DBSessionStore.

These tests are skipped unless psycopg is available and a DSN is provided via
`DATABASE_URL` or `SUPABASE_DB_URL` (or `DB_SESSION_TEST_DSN`).

The test ensures basic create/get/delete works and that expired sessions are
filtered out at read time. It creates the table if it does not already exist
to support local development without running migrations.
"""

from __future__ import annotations

import os
import pytest


try:
    import psycopg  # type: ignore
    HAVE_PSYCOPG = True
except Exception:  # pragma: no cover
    HAVE_PSYCOPG = False


DSN = (
    os.getenv("DB_SESSION_TEST_DSN")
    or os.getenv("DATABASE_URL")
    or os.getenv("SUPABASE_DB_URL")
)


pytestmark = pytest.mark.skipif(not HAVE_PSYCOPG or not DSN, reason="psycopg or DSN missing for DB tests")


def _ensure_schema():
    sql = """
    create extension if not exists pgcrypto;
    create table if not exists public.app_sessions (
        session_id text primary key,
        sub text not null,
        roles jsonb not null,
        name text not null,
        id_token text,
        expires_at timestamptz not null
    );
    create index if not exists idx_app_sessions_sub on public.app_sessions (sub);
    create index if not exists idx_app_sessions_expires_at on public.app_sessions (expires_at);
    alter table public.app_sessions enable row level security;
    """
    with psycopg.connect(DSN, autocommit=True) as conn:  # type: ignore
        with conn.cursor() as cur:
            cur.execute(sql)


def test_create_get_delete_roundtrip():
    _ensure_schema()
    from backend.identity_access.stores_db import DBSessionStore

    store = DBSessionStore(dsn=DSN)
    rec = store.create(sub="user-1", roles=["student"], name="Max", ttl_seconds=60)
    assert rec.session_id
    got = store.get(rec.session_id)
    assert got is not None
    assert got.sub == "user-1"
    assert got.roles == ["student"]
    assert got.name == "Max"
    assert isinstance(got.expires_at, int)

    store.delete(rec.session_id)
    assert store.get(rec.session_id) is None


def test_get_filters_expired_sessions():
    _ensure_schema()
    from backend.identity_access.stores_db import DBSessionStore

    store = DBSessionStore(dsn=DSN)
    # Create an already-expired session by passing a negative TTL
    rec = store.create(sub="u2", roles=["student"], name="Expired", ttl_seconds=-10)
    assert rec.session_id
    assert store.get(rec.session_id) is None

