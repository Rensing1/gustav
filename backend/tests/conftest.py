"""
Pytest configuration for backend tests.

Why: Force AnyIO to use the asyncio backend to avoid sandbox restrictions
that can affect the Trio backend (e.g., socketpair permission errors).
"""
import os
import importlib
import sys
from pathlib import Path
import pytest

# Load .env only when E2E suite is explicit enabled.
try:
    from dotenv import load_dotenv  # type: ignore
    if os.getenv("RUN_E2E", "0") == "1":
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
    # Only export these when the local DB is reachable to avoid hard failures in optional live-DB tests.
    if _probe(login_dsn):
        _assign_or_override("RLS_TEST_DSN", _with_connect_timeout(login_dsn))
        _assign_or_override("DATABASE_URL", _with_connect_timeout(login_dsn))
    else:
        os.environ.pop("RLS_TEST_DSN", None)
        os.environ.pop("DATABASE_URL", None)

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
    os.environ.setdefault("AUTO_CREATE_STORAGE_BUCKETS", "true")


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
    """Reset Teaching repo between tests with a connectivity-aware fallback.

    Why:
        Some tests do not require a database and should run with the in-memory
        repo when Postgres is not reachable locally. Others explicitly assert a
        DB-backed repo and will skip themselves when unavailable. Selecting the
        repo based on a quick DSN probe avoids 500s in general API tests when
        the local DB isn't up.

    Behavior:
        - If TEACHING_DATABASE_URL/RLS_TEST_DSN/DATABASE_URL is reachable via
          psycopg, use the DB-backed repo (default behavior).
        - Otherwise, fall back to the in-memory repo.
    """
    try:
        import os
        import importlib
        import routes.teaching as teaching  # type: ignore
        try:
            import psycopg  # type: ignore
        except Exception:
            # No DB driver: use in-memory
            teaching.set_repo(teaching._Repo())
        else:
            dsn = os.getenv("TEACHING_DATABASE_URL") or os.getenv("RLS_TEST_DSN") or os.getenv("DATABASE_URL")
            ok = False
            if dsn:
                try:
                    with psycopg.connect(dsn, connect_timeout=3):  # type: ignore[arg-type]
                        ok = True
                except Exception:
                    ok = False
            teaching.set_repo(teaching._build_default_repo() if ok else teaching._Repo())
        # Keep alias module in sync if loaded under backend.web.routes.teaching
        try:
            alias = importlib.import_module("backend.web.routes.teaching")
            alias.set_repo(teaching.REPO)  # type: ignore[attr-defined]
        except Exception:
            pass
    except Exception:
        pass
    yield


@pytest.fixture(autouse=True)
def _reset_auth_state_store():
    """
    Reset the global OIDC state store before each pytest case.

    Why:
        Auth tests share the `main.STATE_STORE` singleton; without a reset,
        PKCE state/nonce entries leak across tests and trigger 400 callbacks.
    Parameters:
        (autouse fixture) – no caller-supplied parameters; executes for every test.
    Behavior:
        - Re-imports `main` / `backend.web.main` if necessary.
        - Replaces their `STATE_STORE` with a fresh in-memory `StateStore`.
    Permissions:
        Internal test helper; no runtime permissions required.
    """
    try:
        from identity_access.stores import StateStore  # type: ignore
    except Exception:
        yield
        return

    modules = []
    for name in ("main", "backend.web.main"):
        mod = sys.modules.get(name)
        if mod is None:
            try:
                mod = importlib.import_module(name)  # type: ignore[assignment]
            except Exception:
                continue
        modules.append(mod)

    # Use a single shared instance for all main module aliases to avoid drift
    shared_state = StateStore()
    for mod in modules:
        if hasattr(mod, "STATE_STORE"):
            mod.STATE_STORE = shared_state
    yield


@pytest.fixture(autouse=True)
def _force_prod_env_and_clear_feature_flags(monkeypatch: pytest.MonkeyPatch):
    """Ensure a consistent prod-like environment and clear toggles per test.

    Why:
        Several suites depend on production cookie/CSRF behavior. Also, a few
        tests enable feature flags (upload proxy, dev upload stub) and forget
        to reset them, which can leak into unrelated tests in a full run.

    Behavior:
        - Force `GUSTAV_ENV=prod` so cookie/csrf/security headers are stable.
        - Clear upload-related toggles unless a test sets them explicitly.
        - Clear proxy trust/strict csrf toggles for determinism.
    """
    # Do not force prod globally; individual tests enable prod semantics where required.
    # Clear potential leftovers from other tests and provide safe defaults for secrets
    # to avoid import-time guard failures when a test opts into prod.
    if not os.getenv("SUPABASE_SERVICE_ROLE_KEY"):
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "TEST_ONLY_NOT_USED")
    if not os.getenv("KC_ADMIN_CLIENT_SECRET"):
        monkeypatch.setenv("KC_ADMIN_CLIENT_SECRET", "TEST_ONLY_NOT_USED")
    # Clear env-driven toggles that may leak across tests
    for var in (
        "GUSTAV_ENV",  # ensure default dev unless a test opts in explicitly
        "ENABLE_STORAGE_UPLOAD_PROXY",
        "ENABLE_DEV_UPLOAD_STUB",
        "STORAGE_VERIFY_ROOT",
        "GUSTAV_TRUST_PROXY",
        "STRICT_CSRF_SUBMISSIONS",
    ):
        monkeypatch.delenv(var, raising=False)
    yield


@pytest.fixture(autouse=True)
def _reset_session_store_and_oidc(monkeypatch: pytest.MonkeyPatch):
    """Reset SESSION_STORE and OIDC client to defaults per test.

    Why:
        Some tests monkeypatch these and do not restore. Suite runs then fail
        when subsequent tests rely on defaults.
    """
    try:
        import main  # type: ignore
        from identity_access.stores import SessionStore  # type: ignore
        from identity_access.oidc import OIDCClient  # type: ignore
    except Exception:
        yield
        return

    # Reset session store on both module aliases to avoid drift between
    # `main` and `backend.web.main` when different tests import different
    # aliases.
    shared_session = SessionStore()
    monkeypatch.setattr(main, "SESSION_STORE", shared_session, raising=False)
    try:
        bwm = importlib.import_module("backend.web.main")  # type: ignore
        monkeypatch.setattr(bwm, "SESSION_STORE", shared_session, raising=False)
    except Exception:
        pass
    try:
        # Recreate a fresh OIDC client bound to current config
        # Reset OIDC config to defaults to avoid cross-test pollution
        try:
            cfg = main.load_oidc_config()  # type: ignore[attr-defined]
            monkeypatch.setattr(main, "OIDC_CFG", cfg, raising=False)
        except Exception:
            pass
        fresh = OIDCClient(main.OIDC_CFG)
        monkeypatch.setattr(main, "OIDC", fresh, raising=False)
    except Exception:
        pass
    yield


@pytest.fixture(autouse=True)
def _reset_learning_requests_alias(monkeypatch: pytest.MonkeyPatch):
    """Ensure routes.learning.requests points to the real requests module by default.

    Why:
        Upload-proxy tests monkeypatch this attribute; a lingering stub can
        produce 502s in unrelated tests. This fixture rebinds it for each test.
    """
    try:
        import importlib
        import requests as real_requests  # type: ignore
        # Import both aliases and bind their symbol to the real module
        lr1 = importlib.import_module("routes.learning")
        lr2 = importlib.import_module("backend.web.routes.learning")
        monkeypatch.setattr(lr1, "requests", real_requests, raising=False)
        monkeypatch.setattr(lr2, "requests", real_requests, raising=False)
    except Exception:
        pass
    yield


@pytest.fixture(autouse=True)
def _prune_live_db_env_when_unreachable():
    """Ensure live-DB env vars are cleared when the DB is not reachable.

    Why:
        Some optional live-DB tests trigger only based on the presence of
        RLS_TEST_DSN/SERVICE_ROLE_DSN. When a developer has these set in their
        shell but the local DB isn't running, those tests would fail hard.
        Clearing the variables early in the test phase keeps the suite stable.
    """
    import os
    try:
        import psycopg  # type: ignore
    except Exception:
        # If psycopg is unavailable, treat DB as unreachable and clear vars
        for k in ("RLS_TEST_DSN", "SERVICE_ROLE_DSN", "RLS_TEST_SERVICE_DSN"):
            os.environ.pop(k, None)
        yield
        return

    def _probe(dsn: str) -> bool:
        try:
            with psycopg.connect(dsn, connect_timeout=3):  # type: ignore[arg-type]
                return True
        except Exception:
            return False

    dsn = os.getenv("RLS_TEST_DSN") or os.getenv("DATABASE_URL") or ""
    if dsn and not _probe(dsn):
        for k in ("RLS_TEST_DSN", "SERVICE_ROLE_DSN", "RLS_TEST_SERVICE_DSN"):
            os.environ.pop(k, None)
    yield


@pytest.fixture(autouse=True)
def _reset_learning_create_submission_uc(monkeypatch: pytest.MonkeyPatch):
    """Ensure routes.learning.CreateSubmissionUseCase points to the real class per test.

    Why:
        Some tests monkeypatch the submissions use case to control behavior
        (e.g., avoid DB work or simulate errors). In full-suite runs, a missing
        teardown can leak this patch into subsequent tests. This fixture
        restores the default binding before each test, while still allowing the
        test itself to override it afterwards.
    """
    try:
        import importlib
        uc_mod = importlib.import_module("backend.learning.usecases.submissions")
        real_uc = getattr(uc_mod, "CreateSubmissionUseCase")
        for alias in ("routes.learning", "backend.web.routes.learning"):
            try:
                lr = importlib.import_module(alias)
                monkeypatch.setattr(lr, "CreateSubmissionUseCase", real_uc, raising=False)
            except Exception:
                continue
    except Exception:
        pass
    yield


@pytest.fixture(autouse=True)
def _reset_settings_environment_override():
    """Reset main.SETTINGS.override_environment between tests.

    Why:
        Some tests temporarily force `prod` semantics via
        `main.SETTINGS.override_environment("prod")`. If a test aborts early
        or misses cleanup, the override can leak into unrelated tests in a full
        run. This autouse fixture restores the default (env-driven) behavior
        before each test to keep CSRF/cookie decisions deterministic.
    """
    try:
        import importlib, sys as _sys
        # Reset override on both aliases if present
        for name in ("main", "backend.web.main"):
            mod = _sys.modules.get(name) or importlib.import_module(name)
            if hasattr(mod, "SETTINGS") and hasattr(mod.SETTINGS, "override_environment"):
                mod.SETTINGS.override_environment(None)
    except Exception:
        pass
    yield


@pytest.fixture(autouse=True)
def _configure_dspy_cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Ensure DSPy/diskcache can write a cache directory during import.

    Some DSPy versions instantiate a disk-backed cache at import time. On
    read-only or unusual environments this can fail with sqlite OperationalError
    (readonly database). Point XDG/HOME and a dedicated DSPY cache dir to a
    temporary, writable path to keep the import stable across CI setups.
    """
    try:
        cache_root = tmp_path / "dspy_cache"
        cache_root.mkdir(parents=True, exist_ok=True)
        # Common envs consulted by cache libraries
        monkeypatch.setenv("XDG_CACHE_HOME", str(cache_root))
        monkeypatch.setenv("HOME", str(tmp_path))
        # Best-effort hints for DSPy variants
        monkeypatch.setenv("DSPY_CACHE_DIR", str(cache_root))
        monkeypatch.setenv("DISKCACHE_DIR", str(cache_root))
    except Exception:
        pass
    yield
