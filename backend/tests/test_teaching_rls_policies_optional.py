"""
RLS policy test (single-DSN): verifies that a limited role is constrained by
app.current_sub.

Uses only one DSN (limited) and seeds rows by acting as the owning teacher via
`set_config('app.current_sub', ...)`. In the hard DB-security gate,
`require_db_or_skip()` turns a missing DB into a failure via REQUIRE_DB_TESTS=1.
"""
from __future__ import annotations

import os
import pytest

from utils.db import require_db_or_skip as _require_db_or_skip


pytestmark = pytest.mark.db_write


def _limited_dsn() -> str:
    host = os.getenv("TEST_DB_HOST", "127.0.0.1")
    port = os.getenv("TEST_DB_PORT", "54322")
    user = os.getenv("APP_DB_USER", "gustav_app")
    password = os.getenv("APP_DB_PASSWORD", "CHANGE_ME_DEV")
    return os.getenv("RLS_TEST_DSN") or os.getenv("DATABASE_URL") or f"postgresql://{user}:{password}@{host}:{port}/postgres"


@pytest.mark.anyio
async def test_rls_limited_role_sees_only_own_rows():
    _require_db_or_skip()
    import psycopg  # type: ignore

    dsn = _limited_dsn()
    t1, t2 = "teacher-rls-1", "teacher-rls-2"

    # Cleanup any leftovers from previous runs for deterministic assertions
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, false)", (t1,))
            cur.execute("delete from public.courses where teacher_id = current_setting('app.current_sub', true)")
            cur.execute("select set_config('app.current_sub', %s, false)", (t2,))
            cur.execute("delete from public.courses where teacher_id = current_setting('app.current_sub', true)")
            conn.commit()

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            # Seed rows as their respective owners (RLS-compliant)
            # Use is_local=false so the setting persists across statements in this session
            cur.execute("select set_config('app.current_sub', %s, false)", (t1,))
            cur.execute("insert into public.courses (title, teacher_id) values ('A', %s) returning id", (t1,))
            cur.execute("select set_config('app.current_sub', %s, false)", (t2,))
            cur.execute("insert into public.courses (title, teacher_id) values ('B', %s) returning id", (t2,))
            conn.commit()

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            # As teacher t1: only A is visible
            cur.execute("select set_config('app.current_sub', %s, true)", (t1,))
            cur.execute("select title from public.courses order by title")
            rows = [r[0] for r in (cur.fetchall() or [])]
            assert rows == ["A"]

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            # As unrelated student: none visible
            cur.execute("select set_config('app.current_sub', %s, true)", ("student-rls-x",))
            cur.execute("select title from public.courses order by title")
            rows = cur.fetchall() or []
            assert rows == []
