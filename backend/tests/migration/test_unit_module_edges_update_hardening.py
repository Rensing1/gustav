"""
DB security — unit_module_edges must not allow UPDATE for gustav_limited.

Why:
    Edges are immutable by design (delete + insert). Allowing UPDATE on the
    table widens the write surface without a matching API/use-case.
"""

from __future__ import annotations

import os

import pytest

from backend.tests.utils.db import require_db_or_skip as _require_db_or_skip


def _dsn() -> str:
    host = os.getenv("TEST_DB_HOST", "127.0.0.1")
    port = os.getenv("TEST_DB_PORT", "54322")
    user = os.getenv("APP_DB_USER", "gustav_app")
    password = os.getenv("APP_DB_PASSWORD", "CHANGE_ME_DEV")
    return os.getenv("DATABASE_URL") or f"postgresql://{user}:{password}@{host}:{port}/postgres"


@pytest.mark.anyio
async def test_unit_module_edges_has_no_update_grant_or_update_policy() -> None:
    _require_db_or_skip()
    try:
        import psycopg  # type: ignore
    except Exception:
        pytest.skip("psycopg not available")

    with psycopg.connect(_dsn()) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute("select to_regclass('public.unit_module_edges')")
            if (cur.fetchone() or [None])[0] is None:
                pytest.skip("unit_module_edges table not present; migrations not applied")

            cur.execute(
                """
                select count(*)
                  from information_schema.role_table_grants rg
                 where rg.table_schema = 'public'
                   and rg.table_name = 'unit_module_edges'
                   and rg.grantee = 'gustav_limited'
                   and rg.privilege_type = 'UPDATE'
                """
            )
            assert int(cur.fetchone()[0]) == 0

            cur.execute(
                """
                select count(*)
                  from pg_policies p
                 where p.schemaname = 'public'
                   and p.tablename = 'unit_module_edges'
                   and p.policyname = 'unit_module_edges_update_author'
                """
            )
            assert int(cur.fetchone()[0]) == 0

            for privilege in ("SELECT", "INSERT", "DELETE"):
                cur.execute(
                    """
                    select count(*)
                      from information_schema.role_table_grants rg
                     where rg.table_schema = 'public'
                       and rg.table_name = 'unit_module_edges'
                       and rg.grantee = 'gustav_limited'
                       and rg.privilege_type = %s
                    """,
                    (privilege,),
                )
                assert int(cur.fetchone()[0]) >= 1
