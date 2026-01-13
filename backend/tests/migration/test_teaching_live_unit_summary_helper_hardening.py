"""
DB security — harden `get_unit_latest_submissions_for_owner` (SECURITY DEFINER).

Why:
    The teacher live matrix relies on a SECURITY DEFINER helper that reads from
    `learning_submissions` (student-scoped RLS). Because the function executes
    with elevated privileges, we must minimize its attack surface:
    - PUBLIC must not be able to EXECUTE it.
    - The function must use a safe search_path (no pg_temp).
    - Authorization must bind to the session subject (app.current_sub), not a
      user-controlled parameter (`p_owner_sub`).
"""

from __future__ import annotations

import os
import re

import pytest

from backend.tests.utils.db import require_db_or_skip as _require_db_or_skip


_SIG = "public.get_unit_latest_submissions_for_owner(text, uuid, uuid, timestamptz, integer, integer)"


def _dsn() -> str:
    host = os.getenv("TEST_DB_HOST", "127.0.0.1")
    port = os.getenv("TEST_DB_PORT", "54322")
    user = os.getenv("APP_DB_USER", "gustav_app")
    password = os.getenv("APP_DB_PASSWORD", "CHANGE_ME_DEV")
    return os.getenv("DATABASE_URL") or f"postgresql://{user}:{password}@{host}:{port}/postgres"


@pytest.mark.anyio
async def test_unit_latest_submissions_helper_is_hardened() -> None:
    _require_db_or_skip()
    try:
        import psycopg  # type: ignore
    except Exception:
        pytest.skip("psycopg not available")

    with psycopg.connect(_dsn()) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            # Function must exist (migrations applied).
            cur.execute("select to_regprocedure(%s)::oid", (_SIG,))
            func_oid = (cur.fetchone() or [None])[0]
            if func_oid is None:
                pytest.skip("Helper function not present; migrations not applied in this environment.")

            # 1) EXECUTE privileges: PUBLIC must not have it.
            cur.execute(
                """
                select count(*)
                  from information_schema.routine_privileges rp
                 where rp.specific_schema = 'public'
                   and rp.routine_name = 'get_unit_latest_submissions_for_owner'
                   and rp.grantee = 'PUBLIC'
                   and rp.privilege_type = 'EXECUTE'
                """
            )
            assert int(cur.fetchone()[0]) == 0

            # 2) App role must be able to execute it (grant exists).
            cur.execute(
                """
                select count(*)
                  from information_schema.routine_privileges rp
                 where rp.specific_schema = 'public'
                   and rp.routine_name = 'get_unit_latest_submissions_for_owner'
                   and rp.grantee = 'gustav_limited'
                   and rp.privilege_type = 'EXECUTE'
                """
            )
            assert int(cur.fetchone()[0]) >= 1

            # 3) Definition hardening: safe search_path + session-bound owner checks.
            cur.execute("select pg_get_functiondef(%s::oid)", (func_oid,))
            definition = str((cur.fetchone() or [""])[0])
            upper = definition.upper()
            assert "SECURITY DEFINER" in upper
            assert re.search(
                r"SET\s+SEARCH_PATH\s+TO\s+'?PG_CATALOG'?\s*,\s+'?PUBLIC'?",
                upper,
            ), definition
            assert "PG_TEMP" not in upper

            # The owner check must bind to the session user, not trust p_owner_sub.
            assert re.search(
                r"teacher_id\s*=\s*coalesce\(\s*current_setting\('app\.current_sub'(::text)?,\s*true\)\s*,",
                definition,
            ), definition
