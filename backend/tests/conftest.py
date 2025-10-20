"""
Pytest configuration for backend tests.

Why: Force AnyIO to use the asyncio backend to avoid sandbox restrictions
that can affect the Trio backend (e.g., socketpair permission errors).
"""
import os
import sys
from pathlib import Path
import pytest

# Load .env so E2E tests pick up credentials (KEYCLOAK_ADMIN, ...)
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass


def _ensure_db_env_defaults() -> None:
    """Set sensible defaults so pytest uses the local Postgres instance."""

    # Prefer explicitly provided overrides (e.g., CI). Otherwise fall back to
    # the host-exposed Supabase instance that Docker publishes on 127.0.0.1:54322.
    host = os.getenv("TEST_DB_HOST", "127.0.0.1")
    port = os.getenv("TEST_DB_PORT", "54322")
    service_dsn = f"postgresql://postgres:postgres@{host}:{port}/postgres"
    limited_dsn = f"postgresql://gustav_limited:gustav-limited@{host}:{port}/postgres"

    def _probe(dsn: str) -> bool:
        try:
            import psycopg  # type: ignore
        except Exception:
            return False
        try:
            with psycopg.connect(dsn, connect_timeout=1):  # type: ignore[arg-type]
                return True
        except Exception:
            return False

    # Ensure session tests use the real DB unless already configured.
    def _assign_or_override(var: str, default: str) -> None:
        current = os.getenv(var)
        if not current or "supabase_db_gustav-alpha2" in current:
            os.environ[var] = default

    _assign_or_override("SESSION_TEST_DSN", service_dsn)
    _assign_or_override("RLS_TEST_SERVICE_DSN", service_dsn)

    # Limited DSN is optional: only enable live RLS checks when the role exists.
    if "RLS_TEST_DSN" not in os.environ and _probe(limited_dsn):
        os.environ["RLS_TEST_DSN"] = limited_dsn

    # Main app should also use the host-reachable DSN during tests to avoid
    # `supabase_db_gustav-alpha2` hostname resolution issues outside Docker.
    _assign_or_override("DATABASE_URL", service_dsn)
    os.environ["SESSIONS_BACKEND"] = os.getenv("SESSIONS_BACKEND", "db")


_ensure_db_env_defaults()

# Ensure modules in backend/ and backend/web are importable across tests
REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
WEB_DIR = BACKEND_DIR / "web"
for p in (str(REPO_ROOT), str(BACKEND_DIR), str(WEB_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)


@pytest.fixture
def anyio_backend():
    return "asyncio"
