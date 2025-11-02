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
    app_user = os.getenv("APP_DB_USER", "gustav_app")
    app_password = os.getenv("APP_DB_PASSWORD", "CHANGE_ME_DEV")
    if not app_user or app_user == "gustav_limited":
        raise RuntimeError(
            "APP_DB_USER must point to the environment-specific login role "
            "(e.g. gustav_app). Run `make db-login-user` to provision it."
        )
    login_dsn = f"postgresql://{app_user}:{app_password}@{host}:{port}/postgres"

    def _with_connect_timeout(dsn: str, seconds: int = 5) -> str:
        """Ensure the DSN enforces a connect timeout for robust tests.

        Simple, dependency-free manipulation: append `connect_timeout` unless
        already present. This bounds hangs when DB is slow/unreachable.
        """
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

    # Ensure session tests use the real DB unless already configured.
    def _assign_or_override(var: str, default: str) -> None:
        current = os.getenv(var)
        if not current or "supabase_db_gustav-alpha2" in current:
            os.environ[var] = default

    # Prefer the app login DSN (IN ROLE gustav_limited) for application traffic so every query is RLS-protected.
    # Respect pre-configured env (e.g., a CI-provided login).
    _assign_or_override("RLS_TEST_DSN", _with_connect_timeout(login_dsn))
    _assign_or_override("DATABASE_URL", _with_connect_timeout(login_dsn))

    # Still expose service DSNs for dedicated tests when the host DB is reachable.
    if _probe(service_dsn):
        _assign_or_override("SESSION_TEST_DSN", _with_connect_timeout(service_dsn))
        _assign_or_override("RLS_TEST_SERVICE_DSN", _with_connect_timeout(service_dsn))
        _assign_or_override("SERVICE_ROLE_DSN", _with_connect_timeout(service_dsn))
    else:
        os.environ.pop("SESSION_TEST_DSN", None)
        os.environ.pop("RLS_TEST_SERVICE_DSN", None)
        os.environ.pop("SERVICE_ROLE_DSN", None)

    os.environ["SESSIONS_BACKEND"] = os.getenv("SESSIONS_BACKEND", "db")


_ensure_db_env_defaults()

# Ensure modules in backend/ and backend/web are importable across tests
REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
WEB_DIR = BACKEND_DIR / "web"
TESTS_DIR = BACKEND_DIR / "tests"
for p in (str(REPO_ROOT), str(BACKEND_DIR), str(WEB_DIR), str(TESTS_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def _reset_teaching_repo_between_tests():
    """Reset Teaching repo to default (DB if available) before each test.

    Prevents cross-test pollution when a test switches to the in-memory
    repo; DB-backed tests remain deterministic.
    """
    try:
        import routes.teaching as teaching  # type: ignore
        teaching.set_repo(teaching._build_default_repo())
    except Exception:
        pass
    yield
