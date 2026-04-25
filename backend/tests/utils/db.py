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
from urllib.parse import urlparse

import pytest


def _default_test_dsn() -> str:
    host = os.getenv("TEST_DB_HOST", "127.0.0.1")
    port = os.getenv("TEST_DB_PORT", "54322")
    user = os.getenv("APP_DB_USER", "gustav_app")
    password = os.getenv("APP_DB_PASSWORD", "CHANGE_ME_DEV")
    return f"postgresql://{user}:{password}@{host}:{port}/postgres"


def _is_local_db_host(hostname: str | None) -> bool:
    if not hostname:
        return True
    normalized = hostname.strip().lower().strip("[]")
    return normalized in {"localhost", "127.0.0.1", "::1"} or normalized.endswith(".localhost")


def is_safe_db_test_dsn(dsn: str) -> bool:
    """Return whether pytest may use this DSN as a mutable DB target.

    Local Postgres/Supabase is always acceptable because it is the documented
    test target. External hosts require an explicit isolation contract so an
    exported production DSN cannot be used accidentally.
    """

    parsed = urlparse(dsn)
    if _is_local_db_host(parsed.hostname):
        return True
    return (os.getenv("GUSTAV_DB_TEST_MODE") or "").strip().lower() == "isolated" and bool(
        (os.getenv("GUSTAV_TEST_RUN_ID") or "").strip()
    )


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
    unsafe_env_dsn = bool(env_dsn and not is_safe_db_test_dsn(env_dsn))
    if env_dsn and not unsafe_env_dsn:
        candidates.append(env_dsn)
    candidates.append(_default_test_dsn())

    for dsn in candidates:
        try:
            with psycopg.connect(dsn, connect_timeout=5):
                return
        except Exception:
            continue
    strict = (os.getenv("REQUIRE_DB_TESTS", "0") or "").strip().lower() in {"1", "true", "yes", "on"}
    message = "Database not reachable; ensure local DB at 127.0.0.1:54322 or set DATABASE_URL"
    if unsafe_env_dsn:
        message = (
            "External DATABASE_URL ignored for DB tests without "
            "GUSTAV_DB_TEST_MODE=isolated and GUSTAV_TEST_RUN_ID; local DB was not reachable"
        )
    if strict:
        pytest.fail(message)
    pytest.skip(message)
