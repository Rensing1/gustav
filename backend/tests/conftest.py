"""
Pytest configuration for backend tests.

Why: Force AnyIO to use the asyncio backend to avoid sandbox restrictions
that can affect the Trio backend (e.g., socketpair permission errors).
"""
import os
import importlib
import re
import sys
from pathlib import Path
import pytest

from backend.tests.import_paths import configure_test_import_paths
from backend.tests.import_paths import canonicalize_legacy_route_aliases
from backend.tests.runtime_auth_helpers import install_session_store
from backend.tests.utils.db import is_safe_db_test_dsn

LEGACY_MIGRATION_MARKER = "legacy_migration"
GLOBAL_PUBLIC_TRUNCATE_RE = re.compile(r"truncate\s+table\s+public\.", re.IGNORECASE)

def _truthy_env(name: str) -> bool:
    return (os.getenv(name) or "").strip().lower() in ("1", "true", "yes", "on")


def _item_path(item: object) -> Path | None:
    """Return a filesystem path for a collected pytest item, if available."""
    raw = getattr(item, "path", None) or getattr(item, "fspath", None)
    if not raw:
        return None
    return Path(str(raw))


def _item_has_marker(item: object, marker: str) -> bool:
    """Return whether a collected pytest item has a marker keyword."""
    keywords = getattr(item, "keywords", {})
    try:
        return marker in keywords
    except TypeError:
        return False


def _item_source_contains_global_public_truncate(item: object) -> bool:
    """Return whether the test source contains a global public table truncate.

    Why:
        Test collection is the last safe point before an accidentally collected
        DB test could clear prod-like local data.
    """
    path = _item_path(item)
    if not path or not path.exists() or not path.is_file():
        return False
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    return bool(GLOBAL_PUBLIC_TRUNCATE_RE.search(text))


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:  # pragma: no cover
    """Skip retired Alpha1 import tests unless explicitly requested."""
    offenders: list[str] = []
    for item in items:
        if _item_source_contains_global_public_truncate(item) and not _item_has_marker(item, LEGACY_MIGRATION_MARKER):
            path = _item_path(item)
            offenders.append(str(path) if path else getattr(item, "nodeid", "<unknown test item>"))
    if offenders:
        raise pytest.UsageError(
            "Tests with global `TRUNCATE table public.*` must be marked "
            f"`pytest.mark.{LEGACY_MIGRATION_MARKER}` and gated out of default verify: "
            + ", ".join(sorted(set(offenders)))
        )

    if _truthy_env("RUN_LEGACY_MIGRATION_TESTS"):
        return
    skip_legacy = pytest.mark.skip(
        reason=(
            "Alpha1 legacy migration tests are retired from the default suite; "
            "set RUN_LEGACY_MIGRATION_TESTS=1 to run them explicitly."
        )
    )
    for item in items:
        if _item_has_marker(item, LEGACY_MIGRATION_MARKER):
            item.add_marker(skip_legacy)


def _is_prod_like(env_value: str | None) -> bool:
    return (env_value or "").strip().lower() in {"prod", "production", "stage", "staging"}


def _guard_against_prod_env_during_pytest() -> None:
    """Prevent import-time SystemExit when a developer exported prod-like env vars.

    Why:
        `backend/web/main.py` calls the startup security guard at import time.
        If a developer has `GUSTAV_ENV=prod` exported in their shell, pytest
        collection would abort unless *all* production secrets are configured.

        For tests, we want deterministic, hermetic defaults. Individual tests
        that validate prod guards explicitly set `GUSTAV_ENV=prod` themselves.
    """
    # Ensure application modules never auto-load `.env` during pytest collection.
    # Integration suites that need `.env` load it explicitly in `pytest_configure`.
    os.environ.setdefault("GUSTAV_ENABLE_DOTENV", "false")
    if _is_prod_like(os.getenv("GUSTAV_ENV")):
        os.environ["GUSTAV_ENV"] = "dev"


def _prune_external_wiring_env_by_default() -> None:
    """Keep the default unit/in-process suite independent from external services.

    Why:
        Several tests intentionally validate "storage unavailable" behaviour.
        If a developer has Supabase env vars exported (or accidentally loads
        `.env`) those tests would flip into the real storage adapter path and
        fail in surprising ways.

        Integration suites enable wiring explicitly via RUN_* flags and marker
        selection (see Makefile targets).
    """
    if _truthy_env("RUN_E2E") or _truthy_env("RUN_SUPABASE_E2E") or _truthy_env("RUN_OPENAI_E2E"):
        return
    for var in (
        "SUPABASE_URL",
        "SUPABASE_PUBLIC_URL",
        "SUPABASE_SERVICE_ROLE_KEY",
    ):
        os.environ.pop(var, None)
    for var in (
        "KC_BASE_URL",
        "KC_PUBLIC_BASE_URL",
    ):
        os.environ.pop(var, None)


_guard_against_prod_env_during_pytest()
_prune_external_wiring_env_by_default()


def pytest_configure(config: pytest.Config) -> None:  # pragma: no cover
    """Load `.env` only for explicitly selected integration suites.

    Contract:
        - Unit/in-process suite (`pytest` / `make test`) must not depend on `.env`.
        - E2E (`make test-e2e`) requires RUN_E2E=1 and uses `-m e2e`.
        - Supabase integration (`make test-supabase`) requires RUN_SUPABASE_E2E=1 and uses `-m supabase_integration`.
        - OpenAI integration (`make test-openai`) requires RUN_OPENAI_E2E=1 and uses `-m openai_integration`.
    """
    markexpr = (getattr(config.option, "markexpr", "") or "").strip()

    # Protect developers from the common "set RUN_E2E=1 and run full suite" pitfall.
    # It mixes contradictory assumptions (external services wired vs deliberately unavailable tests).
    if _truthy_env("RUN_E2E") and not markexpr:
        raise pytest.UsageError("RUN_E2E=1 requires marker selection. Use `make test-e2e` or `pytest -m e2e`.")
    if _truthy_env("RUN_SUPABASE_E2E") and not markexpr:
        raise pytest.UsageError(
            "RUN_SUPABASE_E2E=1 requires marker selection. Use `make test-supabase` or `pytest -m supabase_integration`."
        )
    if _truthy_env("RUN_OPENAI_E2E") and not markexpr:
        raise pytest.UsageError(
            "RUN_OPENAI_E2E=1 requires marker selection. Use `make test-openai` or `pytest -m openai_integration`."
        )

    # Load `.env` only when an integration suite is explicitly requested.
    if not (_truthy_env("RUN_E2E") or _truthy_env("RUN_SUPABASE_E2E") or _truthy_env("RUN_OPENAI_E2E")):
        return

    try:
        from dotenv import load_dotenv  # type: ignore

        # Load `.env` as defaults; explicit env vars (e.g. Makefile overrides)
        # must take precedence.
        load_dotenv(override=False)
    except Exception:
        # `.env` loading is best-effort; integration tests will fail with a clear
        # message when required vars are missing.
        return


def _ensure_db_env_defaults() -> None:
    """Set sensible defaults so pytest uses the local Postgres instance."""

    # Prefer explicitly provided overrides (e.g., CI). Otherwise fall back to
    # the host-exposed Supabase instance that Docker publishes on 127.0.0.1:54322.
    host = os.getenv("TEST_DB_HOST", "127.0.0.1")
    port = os.getenv("TEST_DB_PORT", "54322")
    # Service-role DB access in local Supabase should default to `supabase_admin`.
    # Newer local setups keep `postgres` without CREATE on `public`, which breaks
    # migration-style tests that need to create/drop helper tables.
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
        if not current or "supabase_db_gustav-alpha2" in current or not is_safe_db_test_dsn(current):
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
    # Prefer a DSN with CREATE privileges on `public` (supabase_admin-first).
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


_ensure_db_env_defaults()

configure_test_import_paths()


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def _canonicalize_legacy_route_aliases_between_tests():
    """Repair legacy route aliases before tests can mutate route globals."""

    canonicalize_legacy_route_aliases()
    yield


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
        teaching = importlib.import_module("backend.web.routes.teaching")
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
    except Exception:
        pass
    yield


@pytest.fixture(autouse=True)
def _reset_learning_repo_between_tests():
    """Reset Learning repo between tests when the local DB is reachable.

    Why:
        Several Learning tests temporarily replace `backend.web.routes.learning.REPO`.
        Without a symmetric reset, later DB-backed tests can accidentally use a
        stale in-memory/stub repository and fail with misleading 503 responses.
    """

    try:
        import os
        import importlib
        learning = importlib.import_module("backend.web.routes.learning")
        try:
            import psycopg  # type: ignore
        except Exception:
            yield
            return

        dsn = os.getenv("LEARNING_DATABASE_URL") or os.getenv("RLS_TEST_DSN") or os.getenv("DATABASE_URL")
        if not dsn:
            host = os.getenv("TEST_DB_HOST", "127.0.0.1")
            port = os.getenv("TEST_DB_PORT", "54322")
            user = os.getenv("APP_DB_USER", "gustav_app")
            password = os.getenv("APP_DB_PASSWORD", "CHANGE_ME_DEV")
            dsn = f"postgresql://{user}:{password}@{host}:{port}/postgres"
        ok = False
        if dsn:
            try:
                with psycopg.connect(dsn, connect_timeout=3):  # type: ignore[arg-type]
                    ok = True
            except Exception:
                ok = False
        if ok:
            learning.set_repo(learning.DBLearningRepo())  # type: ignore[attr-defined]
    except Exception:
        pass
    yield


@pytest.fixture(autouse=True)
def _reset_learning_route_globals_between_tests():
    """Restore mutable Learning endpoint globals before each test."""

    try:
        from fastapi.routing import APIRoute
        import importlib
        learning = importlib.import_module("backend.web.routes.learning")

        helper_names = (
            "_get_repo",
            "_download_storage_object_via_presign",
            "_download_bytes_with_limit",
            "_load_storage_bytes_for_validation",
        )
        for main_name in ("backend.web.main",):
            main = importlib.import_module(main_name)
            for route in getattr(main.app, "routes", []):
                if not isinstance(route, APIRoute):
                    continue
                if not str(getattr(route, "path", "")).startswith("/api/learning"):
                    continue
                route_globals = getattr(route.endpoint, "__globals__", None)
                if not isinstance(route_globals, dict):
                    continue
                for helper_name in helper_names:
                    if helper_name in route_globals and hasattr(learning, helper_name):
                        route_globals[helper_name] = getattr(learning, helper_name)
    except Exception:
        pass
    yield


@pytest.fixture(autouse=True)
def _reset_teaching_route_globals_between_tests():
    """Restore mutable Teaching endpoint globals before each test."""

    try:
        from fastapi.routing import APIRoute
        import importlib
        teaching = importlib.import_module("backend.web.routes.teaching")

        helper_names = ("_get_repo", "_get_materials_service")
        for main_name in ("backend.web.main",):
            main = importlib.import_module(main_name)
            for route in getattr(main.app, "routes", []):
                if not isinstance(route, APIRoute):
                    continue
                if not str(getattr(route, "path", "")).startswith("/api/teaching"):
                    continue
                route_globals = getattr(route.endpoint, "__globals__", None)
                if not isinstance(route_globals, dict):
                    continue
                for helper_name in helper_names:
                    if helper_name in route_globals and hasattr(teaching, helper_name):
                        route_globals[helper_name] = getattr(teaching, helper_name)
    except Exception:
        pass
    yield


@pytest.fixture(autouse=True)
def _reset_auth_state_store():
    """
    Reset the global OIDC state store before each pytest case.

    Why:
        Auth tests share the `backend.web.main.RUNTIME.state_store` singleton; without a reset,
        PKCE state/nonce entries leak across tests and trigger 400 callbacks.
    Parameters:
        (autouse fixture) – no caller-supplied parameters; executes for every test.
    Behavior:
        - Re-imports `backend.web.main` if necessary.
        - Replaces their Runtime state store with a fresh in-memory `StateStore`.
    Permissions:
        Internal test helper; no runtime permissions required.
    """
    try:
        from backend.identity_access.stores import StateStore
    except Exception:
        yield
        return

    modules = []
    for name in ("backend.web.main",):
        mod = sys.modules.get(name)
        if mod is None:
            try:
                mod = importlib.import_module(name)  # type: ignore[assignment]
            except Exception:
                continue
        modules.append(mod)

    # Use a single shared instance for the package-oriented runtime module.
    shared_state = StateStore()
    for mod in modules:
        runtime = getattr(mod, "RUNTIME", None)
        if runtime is not None:
            runtime.state_store = shared_state
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
        "REQUIRE_STORAGE_VERIFY",
        "GUSTAV_TRUST_PROXY",
        "STRICT_CSRF_SUBMISSIONS",
    ):
        monkeypatch.delenv(var, raising=False)
    yield


@pytest.fixture(autouse=True)
def _reset_session_store_and_oidc(monkeypatch: pytest.MonkeyPatch):
    """Reset Runtime session store and OIDC client to defaults per test.

    Why:
        Some tests monkeypatch these and do not restore. Suite runs then fail
        when subsequent tests rely on defaults.
    """
    try:
        main = importlib.import_module("backend.web.main")
        from backend.identity_access.oidc import OIDCClient  # type: ignore
    except Exception:
        yield
        return

    shared_session = install_session_store(monkeypatch, main)
    try:
        bwm = importlib.import_module("backend.web.main")  # type: ignore
        install_session_store(monkeypatch, bwm, shared_session)
    except Exception:
        pass
    try:
        # Recreate a fresh OIDC client bound to current config
        # Reset OIDC config to defaults to avoid cross-test pollution
        try:
            from backend.web.auth_runtime import load_oidc_config

            cfg = load_oidc_config()
            runtime = getattr(main, "RUNTIME", None)
            if runtime is not None:
                runtime.oidc_config = cfg
        except Exception:
            pass
        fresh = OIDCClient(main.RUNTIME.oidc_config)
        runtime = getattr(main, "RUNTIME", None)
        if runtime is not None:
            runtime.oidc_client = fresh
        try:
            bwm = importlib.import_module("backend.web.main")  # type: ignore
            runtime = getattr(bwm, "RUNTIME", None)
            if runtime is not None:
                runtime.oidc_config = main.RUNTIME.oidc_config
                runtime.oidc_client = fresh
        except Exception:
            pass
    except Exception:
        pass
    yield


@pytest.fixture(autouse=True)
def _reset_learning_requests_alias(monkeypatch: pytest.MonkeyPatch):
    """Ensure backend.web.routes.learning.requests points to the real requests module by default.

    Why:
        Upload-proxy tests monkeypatch this attribute; a lingering stub can
        produce 502s in unrelated tests. This fixture rebinds it for each test.
    """
    try:
        import importlib
        import requests as real_requests  # type: ignore
        # Bind the canonical Learning module to the real requests library.
        learning = importlib.import_module("backend.web.routes.learning")
        monkeypatch.setattr(learning, "requests", real_requests, raising=False)
    except Exception:
        pass
    yield


@pytest.fixture(autouse=True)
def _reset_route_storage_adapters_between_tests():
    """Restore route-level storage adapters to Null adapters before each test.

    Why:
        Many API tests patch `backend.web.routes.learning.STORAGE_ADAPTER` or
        `backend.web.routes.teaching.STORAGE_ADAPTER` directly. If a test reloads a route
        module or forgets cleanup, later tests can accidentally run against a
        stale fake adapter and produce order-dependent failures.
    """
    try:
        import importlib
        from backend.teaching.storage import NullStorageAdapter  # type: ignore

        for alias in ("backend.web.routes.learning", "backend.web.routes.teaching"):
            try:
                mod = importlib.import_module(alias)
                if hasattr(mod, "set_storage_adapter"):
                    mod.set_storage_adapter(NullStorageAdapter(), override=False)  # type: ignore[attr-defined]
                elif hasattr(mod, "STORAGE_ADAPTER"):
                    setattr(mod, "STORAGE_ADAPTER", NullStorageAdapter())
            except Exception:
                continue
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
    """Ensure backend.web.routes.learning.CreateSubmissionUseCase points to the real class per test.

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
        for alias in ("backend.web.routes.learning",):
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
    """Reset runtime settings environment override between tests.

    Why:
        Some tests temporarily force `prod` semantics via
        `backend.web.main.RUNTIME.settings.override_environment("prod")`. If a test aborts early
        or misses cleanup, the override can leak into unrelated tests in a full
        run. This autouse fixture restores the default (env-driven) behavior
        before each test to keep CSRF/cookie decisions deterministic.
    """
    try:
        import importlib, sys as _sys
        # Reset override on the package-oriented runtime module if present.
        for name in ("backend.web.main",):
            mod = _sys.modules.get(name) or importlib.import_module(name)
            runtime = getattr(mod, "RUNTIME", None)
            settings = getattr(runtime, "settings", None)
            if hasattr(settings, "override_environment"):
                settings.override_environment(None)
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
