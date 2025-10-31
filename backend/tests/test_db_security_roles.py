"""
Security regression test: the application role must not be a LOGIN role.

Why: Prevents accidentally shipping a known-credential DB user into staging/production.

Behavior:
- Given a reachable database,
- When we inspect `pg_roles` for `gustav_limited`,
- Then `rolcanlogin` must be false.

Notes:
- The test is skipped if no DSN is configured or the database is unreachable.
- This asserts the effect of a migration that sets `gustav_limited` to NOLOGIN.
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
async def test_app_role_is_nologin():
    dsn = (
        os.getenv("RLS_TEST_DSN")
        or os.getenv("DATABASE_URL")
        or os.getenv("TEACHING_DATABASE_URL")
        or os.getenv("SESSION_DATABASE_URL")
        or ""
    )
    if not dsn or not _probe(dsn):
        pytest.skip("DB unreachable or no DSN configured for role inspection")

    import psycopg  # type: ignore

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "select rolcanlogin from pg_roles where rolname = 'gustav_limited'"
            )
            row = cur.fetchone()
            assert row is not None, "gustav_limited role must exist"
            can_login = bool(row[0])
            assert can_login is False, "gustav_limited must be NOLOGIN (rolcanlogin=false)"

