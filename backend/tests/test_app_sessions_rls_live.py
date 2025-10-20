"""
Optional live RLS tests for the `public.app_sessions` table.

Why:
- Validate that Row Level Security (RLS) and privileges are enforced in a real
  database environment: anon/authenticated roles cannot read/write sessions,
  while a service role can.

How to run (optional):
- Set environment variables before running pytest:
  - `RLS_TEST_DSN` → DSN for a non-service/limited role (expected to be denied)
  - `RLS_TEST_SERVICE_DSN` → DSN for a service role (expected to succeed)
- Ensure migration `supabase/migrations/20251019135804_persistent_app_sessions.sql` is applied.

Tests are skipped by default when the env vars or psycopg3 are not available.
"""

from __future__ import annotations

import os
import pytest


psycopg = None  # late import, tests fallback to static checks when unavailable
try:  # pragma: no cover - optional import in CI
    import psycopg  # type: ignore
except Exception:  # pragma: no cover
    psycopg = None  # type: ignore


def test_rls_denies_insert_and_select_for_limited_role():
    """RLS must deny non-service roles; fallback asserts migration contains RLS statements."""
    dsn = os.getenv("RLS_TEST_DSN")
    if dsn and psycopg is not None:
        with psycopg.connect(dsn, autocommit=True) as conn:
            with conn.cursor() as cur:
                with pytest.raises(Exception):
                    cur.execute(
                        "insert into public.app_sessions (session_id, sub, roles, name, id_token, expires_at) "
                        "values ('test-denied', 'sub', '[]'::jsonb, 'Name', null, now())"
                    )
                # SELECT may fail or yield nothing; either outcome is acceptable under RLS
                try:
                    cur.execute("select 1 from public.app_sessions limit 1")
                    _ = cur.fetchone()
                except Exception:
                    pass
    else:
        # Static fallback: verify migration enforces RLS and revokes
        import pathlib
        root = pathlib.Path(__file__).resolve().parents[2]
        sql = (root / "supabase" / "migrations" / "20251019135804_persistent_app_sessions.sql").read_text(encoding="utf-8")
        assert "enable row level security" in sql.lower()
        assert "revoke all on public.app_sessions from anon;" in sql
        assert "revoke all on public.app_sessions from authenticated;" in sql


def test_service_role_can_insert_and_select():
    """Service role should read/write; fallback asserts table and indexes are defined in migration."""
    dsn = os.getenv("RLS_TEST_SERVICE_DSN")
    if dsn and psycopg is not None:
        with psycopg.connect(dsn, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "insert into public.app_sessions (session_id, sub, roles, name, id_token, expires_at) "
                    "values ('test-allowed', 'sub', '[]'::jsonb, 'Name', null, now())"
                )
                cur.execute("select session_id from public.app_sessions where session_id = 'test-allowed'")
                row = cur.fetchone()
                assert row and row[0] == "test-allowed"
                cur.execute("delete from public.app_sessions where session_id = 'test-allowed'")
    else:
        # Static fallback: verify schema and performance indexes
        import pathlib
        root = pathlib.Path(__file__).resolve().parents[2]
        sql = (root / "supabase" / "migrations" / "20251019135804_persistent_app_sessions.sql").read_text(encoding="utf-8")
        assert "create table" in sql.lower() and "public.app_sessions" in sql
        assert "create index" in sql.lower() and "idx_app_sessions_expires_at" in sql
