"""Runtime configuration helpers for the learning submission worker."""

from __future__ import annotations

import logging
import os
import re

LOG = logging.getLogger(__name__)

DEFAULT_LEASE_SECONDS = 45
DEFAULT_LEASE_MULTIPLIER = 4
MAX_CONCURRENCY = 4
_TRUTHY = {"1", "true", "yes", "on"}


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name, str(default))
    try:
        return int(raw)
    except ValueError:
        LOG.warning("Invalid %s=%s, defaulting to %s", name, raw, default)
        return default


def backoff_seconds() -> int:
    """Return configured backoff seconds with a minimum of one second."""

    return max(1, _int_env("WORKER_BACKOFF_SECONDS", 10))


def concurrency_limit() -> int:
    """Parse WORKER_CONCURRENCY with sane lower and upper bounds."""

    value = _int_env("WORKER_CONCURRENCY", 1)
    if value > MAX_CONCURRENCY:
        LOG.warning("WORKER_CONCURRENCY=%s capped to %s", value, MAX_CONCURRENCY)
    return max(1, min(value, MAX_CONCURRENCY))


def lease_seconds() -> int:
    """Return the base lease seconds with lenient parsing."""

    return max(1, _int_env("WORKER_LEASE_SECONDS", DEFAULT_LEASE_SECONDS))


def lease_multiplier() -> int:
    """Return the lease multiplier with lenient parsing."""

    return max(1, _int_env("WORKER_LEASE_MULTIPLIER", DEFAULT_LEASE_MULTIPLIER))


def lease_duration_seconds() -> int:
    """Compute the effective lease window for long-running Vision/Feedback jobs."""

    base = lease_seconds()
    return max(base, base * lease_multiplier())


def truthy_env(name: str, *, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in _TRUTHY


def dsn_username(dsn: str) -> str:
    try:
        from urllib.parse import urlparse

        parsed = urlparse(dsn)
        if parsed.username:
            return parsed.username
    except Exception:
        pass
    match = re.match(r"^[a-z]+://(?P<user>[^:@/]+)", dsn or "")
    return match.group("user") if match else ""


def resolve_worker_dsn() -> str:
    """
    Resolve the Postgres DSN for the learning worker with least-privilege guards.

    The worker prefers explicit worker DSNs, falls back to legacy learning DSNs
    for compatibility, and otherwise builds a DSN for the dedicated worker role.
    Service-role or superuser accounts are rejected unless explicitly opted in
    for local debugging or E2E runs.
    """

    candidates = [
        os.getenv("LEARNING_WORKER_DATABASE_URL"),
        os.getenv("LEARNING_WORKER_DB_URL"),
        os.getenv("LEARNING_DATABASE_URL"),
        os.getenv("LEARNING_DB_URL"),
    ]
    for candidate in candidates:
        if candidate:
            dsn = candidate
            break
    else:
        host = os.getenv("TEST_DB_HOST", "127.0.0.1")
        port = os.getenv("TEST_DB_PORT", "54322")
        user = os.getenv("LEARNING_WORKER_DB_USER", "gustav_worker")
        password = os.getenv("LEARNING_WORKER_DB_PASSWORD", "CHANGE_ME_DEV")
        dsn = f"postgresql://{user}:{password}@{host}:{port}/postgres"

    allow_service = (
        truthy_env("ALLOW_SERVICE_DSN_FOR_TESTING")
        or truthy_env("RUN_E2E")
        or truthy_env("RUN_SUPABASE_E2E")
    )
    user = dsn_username(dsn)
    if user in {"postgres", "service_role", "supabase_admin"} and not allow_service:
        raise RuntimeError(
            "Learning worker requires the gustav_worker login role. "
            "Set LEARNING_WORKER_DATABASE_URL with the dedicated worker account or set "
            "ALLOW_SERVICE_DSN_FOR_TESTING=true for temporary local debugging."
        )
    return dsn
