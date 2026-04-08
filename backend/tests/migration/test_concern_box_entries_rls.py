"""Migration contract for concern box entries and their RLS policies."""

from __future__ import annotations

import pytest

from backend.tests.utils.db import require_db_or_skip as _require_db_or_skip


@pytest.mark.anyio
async def test_concern_box_entries_table_and_policies_exist() -> None:
    _require_db_or_skip()
    try:
        import psycopg  # type: ignore
    except Exception:
        pytest.skip("psycopg not available")

    from backend.teaching.repo_db import DBTeachingRepo  # type: ignore

    repo = DBTeachingRepo()
    with psycopg.connect(repo._dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute(
                """
                select exists (
                  select 1
                    from information_schema.tables
                   where table_schema = 'public'
                     and table_name = 'concern_box_entries'
                )
                """
            )
            assert bool((cur.fetchone() or [False])[0]) is True

            cur.execute(
                """
                select relrowsecurity, relforcerowsecurity
                  from pg_class
                 where oid = 'public.concern_box_entries'::regclass
                """
            )
            row = cur.fetchone()
            assert row is not None
            assert bool(row[0]) is True

            cur.execute(
                """
                select policyname
                  from pg_policies
                 where schemaname = 'public'
                   and tablename = 'concern_box_entries'
                 order by policyname
                """
            )
            policies = [str(item[0]) for item in (cur.fetchall() or [])]

    assert "concern_box_entries_insert_member" in policies
    assert "concern_box_entries_select_owner" in policies
    assert "concern_box_entries_update_owner" in policies


def test_concern_box_insert_function_binds_student_to_session_sub() -> None:
    sql = (
        "supabase/migrations/20260406093338_concern_box_entries_insert_function.sql"
    )
    source = open(sql, encoding="utf-8").read()

    assert "current_setting('app.current_sub', true)" in source
