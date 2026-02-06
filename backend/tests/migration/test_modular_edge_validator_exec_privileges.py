"""
DB security — EXECUTE hardening for modular edge validator helper.

Why:
    `validate_unit_module_edges_for_unit(...)` is used by deferrable constraint
    triggers during modular phase/module moves. The helper should be fail-closed:
    no PUBLIC execute grant, explicit execute grant for `gustav_limited`.
"""

from __future__ import annotations

import os

import pytest

from backend.tests.utils.db import require_db_or_skip as _require_db_or_skip


_SIG = "public.validate_unit_module_edges_for_unit(uuid, uuid)"


def _dsn() -> str:
    host = os.getenv("TEST_DB_HOST", "127.0.0.1")
    port = os.getenv("TEST_DB_PORT", "54322")
    user = os.getenv("APP_DB_USER", "gustav_app")
    password = os.getenv("APP_DB_PASSWORD", "CHANGE_ME_DEV")
    return os.getenv("DATABASE_URL") or f"postgresql://{user}:{password}@{host}:{port}/postgres"


@pytest.mark.anyio
async def test_modular_edge_validator_has_expected_execute_grants() -> None:
    _require_db_or_skip()
    try:
        import psycopg  # type: ignore
    except Exception:
        pytest.skip("psycopg not available")

    with psycopg.connect(_dsn()) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute("select to_regprocedure(%s)::oid", (_SIG,))
            func_oid = (cur.fetchone() or [None])[0]
            if func_oid is None:
                pytest.skip("Function not present; migrations not applied in this environment.")

            cur.execute(
                """
                select count(*)
                  from information_schema.routine_privileges rp
                 where rp.specific_schema = 'public'
                   and rp.routine_name = 'validate_unit_module_edges_for_unit'
                   and rp.grantee = 'PUBLIC'
                   and rp.privilege_type = 'EXECUTE'
                """
            )
            assert int(cur.fetchone()[0]) == 0

            cur.execute(
                """
                select count(*)
                  from information_schema.routine_privileges rp
                 where rp.specific_schema = 'public'
                   and rp.routine_name = 'validate_unit_module_edges_for_unit'
                   and rp.grantee = 'gustav_limited'
                   and rp.privilege_type = 'EXECUTE'
                """
            )
            assert int(cur.fetchone()[0]) >= 1
