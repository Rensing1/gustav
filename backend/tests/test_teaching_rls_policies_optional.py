"""
Optional RLS policy test (single-DSN): verifies that a limited role is
constrained by app.current_sub. Uses only one DSN (limited) and seeds rows by
acting as the owning teacher via `set_config('app.current_sub', ...)`.

Skips if no database is reachable via RLS_TEST_DSN or DATABASE_URL.
"""
from __future__ import annotations

import os
import pytest


def _probe(dsn: str) -> bool:
    try:
        import psycopg  # type: ignore
        with psycopg.connect(dsn, connect_timeout=1):
            return True
    except Exception:
        return False


@pytest.mark.anyio
async def test_rls_limited_role_sees_only_own_rows():
    dsn = os.getenv("RLS_TEST_DSN") or os.getenv("DATABASE_URL") or ""
    if not dsn or not _probe(dsn):
        pytest.skip("RLS limited DSN not configured or DB unreachable")

    import psycopg  # type: ignore

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
