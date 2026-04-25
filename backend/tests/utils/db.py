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
import ipaddress
from urllib.parse import parse_qsl, urlparse

import pytest


def _default_test_dsn() -> str:
    host = os.getenv("TEST_DB_HOST", "127.0.0.1")
    port = os.getenv("TEST_DB_PORT", "54322")
    user = os.getenv("APP_DB_USER", "gustav_app")
    password = os.getenv("APP_DB_PASSWORD", "CHANGE_ME_DEV")
    return f"postgresql://{user}:{password}@{host}:{port}/postgres"


def _split_libpq_host_values(values: list[str]) -> list[str]:
    """Return individual libpq host targets from repeated/comma-separated fields."""

    targets: list[str] = []
    for value in values:
        targets.extend(part.strip() for part in value.split(",") if part.strip())
    return targets


def _declared_db_targets(dsn: str) -> list[tuple[str, bool]]:
    """Extract every declared DB target and whether it may be a Unix socket.

    libpq URLs can hide the actual host in query parameters, for example
    `postgresql:///postgres?host=db.example`. Tests mutate their target DB, so
    the guard must inspect both the URI authority and libpq's query fields.
    """

    parsed = urlparse(dsn)
    targets: list[tuple[str, bool]] = []
    if parsed.hostname:
        targets.append((parsed.hostname, False))

    query_values: dict[str, list[str]] = {}
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        query_values.setdefault(key.lower(), []).append(value)

    for host in _split_libpq_host_values(query_values.get("host", [])):
        targets.append((host, True))
    for hostaddr in _split_libpq_host_values(query_values.get("hostaddr", [])):
        targets.append((hostaddr, False))
    return targets


def _is_local_db_target(target: str, *, allow_unix_socket: bool) -> bool:
    normalized = target.strip().lower().strip("[]")
    if allow_unix_socket and normalized.startswith("/"):
        return True
    if normalized == "localhost" or normalized.endswith(".localhost"):
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def is_safe_db_test_dsn(dsn: str) -> bool:
    """Return whether pytest may use this DSN as a mutable DB target.

    Local Postgres/Supabase is always acceptable because it is the documented
    test target. External hosts require an explicit isolation contract so an
    exported production DSN cannot be used accidentally.
    """

    targets = _declared_db_targets(dsn)
    if targets and all(_is_local_db_target(target, allow_unix_socket=allow_socket) for target, allow_socket in targets):
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
