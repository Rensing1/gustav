"""
RLS helper EXECUTE privilege tests (TDD).

Asserts:
- PUBLIC has no EXECUTE on student-facing RLS helper functions
- gustav_limited can EXECUTE them (and they run successfully)
"""
from __future__ import annotations

import os

import pytest

from utils.db import require_db_or_skip as _require_db_or_skip


HELPERS = (
    ("student_is_course_member", "text, uuid", ("sub", "00000000-0000-0000-0000-000000000000")),
    ("student_can_access_unit", "text, uuid", ("sub", "00000000-0000-0000-0000-000000000000")),
    (
        "student_can_access_course_module",
        "text, uuid",
        ("sub", "00000000-0000-0000-0000-000000000000"),
    ),
    ("student_can_access_section", "text, uuid", ("sub", "00000000-0000-0000-0000-000000000000")),
)


@pytest.mark.anyio
async def test_rls_helpers_no_public_execute_and_app_role_can_run():
    _require_db_or_skip()
    try:
        import psycopg  # type: ignore
    except Exception:  # pragma: no cover - safety
        pytest.skip("psycopg not available")

    dsn = (
        os.getenv("DATABASE_URL")
        or f"postgresql://gustav_limited:gustav-limited@{os.getenv('TEST_DB_HOST', '127.0.0.1')}:{os.getenv('TEST_DB_PORT', '54322')}/postgres"
    )
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            # Verify PUBLIC has no EXECUTE grant on the helpers
            cur.execute(
                """
                select count(*)
                  from information_schema.routine_privileges rp
                 where rp.specific_schema = 'public'
                   and rp.routine_name = any(%s)
                   and rp.grantee = 'PUBLIC'
                   and rp.privilege_type = 'EXECUTE'
                """,
                ([h[0] for h in HELPERS],),
            )
            public_exec = int(cur.fetchone()[0])
            assert public_exec == 0

            # Verify gustav_limited has EXECUTE
            cur.execute(
                """
                select count(*)
                  from information_schema.routine_privileges rp
                 where rp.specific_schema = 'public'
                   and rp.routine_name = any(%s)
                   and rp.grantee = 'gustav_limited'
                   and rp.privilege_type = 'EXECUTE'
                """,
                ([h[0] for h in HELPERS],),
            )
            app_exec = int(cur.fetchone()[0])
            assert app_exec >= len(HELPERS)

            # Also sanity-check we can actually execute the helpers as app role
            for name, _sig, args in HELPERS:
                cur.execute("select set_config('app.current_sub', %s, true)", (args[0],))
                cur.execute(
                    f"select public.{name}(%s, %s)",
                    (args[0], args[1]),
                )
                # The value is arbitrary false for dummy ids; we only care execution works
                _ = cur.fetchone()[0]

