"""
Test DB utilities: provide environment-independent reachability checks.

Rationale:
    Several integration tests require a live Postgres instance with migrations
    applied. Instead of depending on environment variables, we probe a safe
    default DSN used by the app (limited role) when `DATABASE_URL` is absent.

Defaults:
    postgresql://gustav_app:CHANGE_ME_DEV@127.0.0.1:54322/postgres
    (APP_DB_USER / APP_DB_PASSWORD apply; TEST_DB_HOST / TEST_DB_PORT can override host/port)
"""
from __future__ import annotations

import os
import pytest


def _default_test_dsn() -> str:
    host = os.getenv("TEST_DB_HOST", "127.0.0.1")
    port = os.getenv("TEST_DB_PORT", "54322")
    user = os.getenv("APP_DB_USER", "gustav_app")
    password = os.getenv("APP_DB_PASSWORD", "CHANGE_ME_DEV")
    return f"postgresql://{user}:{password}@{host}:{port}/postgres"


def require_db_or_skip() -> None:
    """Skip test only when DB is not reachable via env or default DSN.

    Tries, in order:
      1) `DATABASE_URL` if present
      2) Default limited-role DSN (127.0.0.1:54322)
    """
    try:
        import psycopg  # type: ignore
    except Exception:
        pytest.skip("psycopg not available")

    candidates: list[str] = []
    env_dsn = os.getenv("DATABASE_URL")
    if env_dsn:
        candidates.append(env_dsn)
    candidates.append(_default_test_dsn())

    for dsn in candidates:
        try:
            with psycopg.connect(dsn, connect_timeout=1):
                return
        except Exception:
            continue
    pytest.skip("Database not reachable; ensure local DB at 127.0.0.1:54322 or set DATABASE_URL")
