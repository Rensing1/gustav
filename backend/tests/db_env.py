"""Local DB environment defaults for backend pytest runs."""

from __future__ import annotations

import os

from backend.tests.utils.db import is_safe_db_test_dsn


def _with_connect_timeout(dsn: str, seconds: int = 5) -> str:
    """Append a connect timeout unless the DSN already defines one."""

    if not isinstance(dsn, str) or not dsn:
        return dsn
    if "connect_timeout=" in dsn:
        return dsn
    sep = "&" if "?" in dsn else "?"
    return f"{dsn}{sep}connect_timeout={seconds}"


def _probe(dsn: str) -> bool:
    try:
        import psycopg  # type: ignore
    except Exception:
        return False
    try:
        with psycopg.connect(dsn, connect_timeout=5):  # type: ignore[arg-type]
            return True
    except Exception:
        return False


def _assign_or_override(var: str, default: str) -> None:
    current = os.getenv(var)
    if not current or "supabase_db_gustav-alpha2" in current or not is_safe_db_test_dsn(current):
        os.environ[var] = default


def ensure_db_env_defaults() -> None:
    """Set sensible defaults so pytest uses the local Postgres instance."""

    host = os.getenv("TEST_DB_HOST", "127.0.0.1")
    port = os.getenv("TEST_DB_PORT", "54322")
    svc_user = os.getenv("TEST_DB_SUPERUSER") or os.getenv("DB_SUPERUSER") or "supabase_admin"
    svc_password = os.getenv("TEST_DB_SUPERPASSWORD") or os.getenv("DB_SUPERPASSWORD") or "postgres"
    preferred_service_dsn = f"postgresql://{svc_user}:{svc_password}@{host}:{port}/postgres"
    legacy_service_dsn = f"postgresql://postgres:postgres@{host}:{port}/postgres"
    app_user = os.getenv("APP_DB_USER", "gustav_app")
    app_password = os.getenv("APP_DB_PASSWORD", "CHANGE_ME_DEV")
    if not app_user or app_user == "gustav_limited":
        raise RuntimeError(
            "APP_DB_USER must point to the environment-specific login role "
            "(e.g. gustav_app). Run `make db-login-user` to provision it."
        )
    login_dsn = f"postgresql://{app_user}:{app_password}@{host}:{port}/postgres"

    # Prefer the app login DSN for application traffic so every query is RLS-protected.
    if _probe(login_dsn):
        _assign_or_override("RLS_TEST_DSN", _with_connect_timeout(login_dsn))
        _assign_or_override("DATABASE_URL", _with_connect_timeout(login_dsn))
    else:
        os.environ.pop("RLS_TEST_DSN", None)
        os.environ.pop("DATABASE_URL", None)

    # Still expose service DSNs for dedicated tests when the host DB is reachable.
    resolved_service_dsn = ""
    for candidate in [preferred_service_dsn, legacy_service_dsn]:
        if candidate and _probe(candidate):
            resolved_service_dsn = candidate
            break
    if resolved_service_dsn:
        _assign_or_override("RLS_TEST_SERVICE_DSN", _with_connect_timeout(resolved_service_dsn))
        _assign_or_override("SERVICE_ROLE_DSN", _with_connect_timeout(resolved_service_dsn))
        _assign_or_override("SESSION_TEST_DSN", _with_connect_timeout(resolved_service_dsn))
    else:
        os.environ.pop("SESSION_TEST_DSN", None)
        os.environ.pop("RLS_TEST_SERVICE_DSN", None)
        os.environ.pop("SERVICE_ROLE_DSN", None)

    os.environ["SESSIONS_BACKEND"] = os.getenv("SESSIONS_BACKEND", "db")
    os.environ.setdefault("AUTO_CREATE_STORAGE_BUCKETS", "true")
