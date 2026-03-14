"""Preflight checks for `make verify` DB prerequisites.

Why:
    `make verify` runs DB-backed tests with `REQUIRE_DB_TESTS=1`. When the local
    schema is behind migrations, failures can appear late and noisy (for example
    `unit_tasks_kind_check` rejecting `kind='calliope'`).

This preflight fails early with a focused error and concrete remediation steps.
"""

from __future__ import annotations

import os
import sys
from typing import TextIO


def build_dsn() -> str:
    """Build a DSN from env vars, preferring `DATABASE_URL` when present."""
    env_dsn = (os.getenv("DATABASE_URL") or "").strip()
    if env_dsn:
        return env_dsn
    host = os.getenv("TEST_DB_HOST", "127.0.0.1")
    port = os.getenv("TEST_DB_PORT", "54322")
    user = os.getenv("APP_DB_USER", "gustav_app")
    password = os.getenv("APP_DB_PASSWORD", "CHANGE_ME_DEV")
    return f"postgresql://{user}:{password}@{host}:{port}/postgres"


def _connect(dsn: str):
    """Open a short-timeout Postgres connection."""
    import psycopg  # type: ignore

    return psycopg.connect(dsn, connect_timeout=5)


def fetch_unit_tasks_kind_constraintdef(conn) -> str | None:  # noqa: ANN001
    """Return `unit_tasks_kind_check` definition from public schema, if present."""
    with conn.cursor() as cur:
        cur.execute(
            """
            select pg_get_constraintdef(c.oid)
            from pg_constraint c
            join pg_class t on t.oid = c.conrelid
            join pg_namespace n on n.oid = t.relnamespace
            where n.nspname = 'public'
              and t.relname = 'unit_tasks'
              and c.conname = 'unit_tasks_kind_check'
            limit 1
            """
        )
        row = cur.fetchone()
    if not row or not row[0]:
        return None
    return str(row[0])


def constraint_supports_calliope(definition: str | None) -> bool:
    """Check whether the constraint definition allows `kind='calliope'`."""
    if not definition:
        return False
    return "'calliope'" in definition.lower()


def _remediation_hint() -> str:
    return (
        "Run one of:\n"
        "  1) supabase migration up && make db-login-user\n"
        "  2) make reset-local"
    )


def run_preflight(*, dsn: str | None = None, out: TextIO | None = None, err: TextIO | None = None) -> int:
    """Validate local DB state required for `make verify`."""
    out_stream = out or sys.stdout
    err_stream = err or sys.stderr
    target_dsn = dsn or build_dsn()

    try:
        with _connect(target_dsn) as conn:
            definition = fetch_unit_tasks_kind_constraintdef(conn)
    except Exception as exc:
        print(f"Database preflight failed: cannot connect/check schema ({exc}).", file=err_stream)
        print(_remediation_hint(), file=err_stream)
        return 2

    if not definition:
        print("Database preflight failed: unit_tasks_kind_check is missing.", file=err_stream)
        print(_remediation_hint(), file=err_stream)
        return 2

    if not constraint_supports_calliope(definition):
        print("Database preflight failed: unit_tasks_kind_check does not allow kind='calliope'.", file=err_stream)
        print(f"Current constraint: {definition}", file=err_stream)
        print(_remediation_hint(), file=err_stream)
        return 2

    print("DB preflight OK: unit_tasks_kind_check includes calliope.", file=out_stream)
    return 0


def main() -> int:
    return run_preflight()


if __name__ == "__main__":
    raise SystemExit(main())
