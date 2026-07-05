"""
DB performance guardrail — modular unlock helper should not query edges per module.

Why:
    `modular_section_is_open_or_done_for_student(...)` is called from visibility
    helpers in submission-related paths. The boolean helper now delegates to a
    table-valued state helper; N+1 edge scans must still be prevented there.
"""

from __future__ import annotations

import os

import pytest

from backend.tests.utils.db import require_db_or_skip as _require_db_or_skip


pytestmark = pytest.mark.db_read


_BOOL_SIG = "public.modular_section_is_open_or_done_for_student(text, uuid, uuid, uuid)"
_STATE_SIG = "public.get_modular_unit_module_states_for_student(text, uuid, uuid)"


def _dsn() -> str:
    host = os.getenv("TEST_DB_HOST", "127.0.0.1")
    port = os.getenv("TEST_DB_PORT", "54322")
    user = os.getenv("APP_DB_USER", "gustav_app")
    password = os.getenv("APP_DB_PASSWORD", "CHANGE_ME_DEV")
    return os.getenv("DATABASE_URL") or f"postgresql://{user}:{password}@{host}:{port}/postgres"


@pytest.mark.anyio
async def test_modular_unlock_helpers_delegate_and_preload_edges_without_n_plus_one() -> None:
    _require_db_or_skip()
    try:
        import psycopg  # type: ignore
    except Exception:
        pytest.skip("psycopg not available")

    with psycopg.connect(_dsn()) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute("select to_regprocedure(%s)", (_BOOL_SIG,))
            bool_regproc = (cur.fetchone() or [None])[0]
            if bool_regproc is None:
                pytest.skip("Boolean helper not present; migrations not applied in this environment.")

            cur.execute("select to_regprocedure(%s)", (_STATE_SIG,))
            state_regproc = (cur.fetchone() or [None])[0]
            if state_regproc is None:
                pytest.skip("State helper not present; migrations not applied in this environment.")

            cur.execute("select pg_get_functiondef(to_regprocedure(%s))", (_BOOL_SIG,))
            bool_body = str((cur.fetchone() or [""])[0] or "").lower()
            assert "from public.get_modular_unit_module_states_for_student(" in bool_body

            cur.execute("select pg_get_functiondef(to_regprocedure(%s))", (_STATE_SIG,))
            state_body = str((cur.fetchone() or [""])[0] or "").lower()

            # Guardrail against the original N+1 pattern:
            #   ... from unit_module_edges e
            #   where e.unit_id = p_unit_id
            #     and e.to_module_id = v_module.module_id;
            assert "and e.to_module_id = v_module.module_id" not in state_body

            # Ensure the optimized shape pre-aggregates edges once per unit.
            assert "jsonb_object_agg(edge_rows.to_module_id" in state_body
