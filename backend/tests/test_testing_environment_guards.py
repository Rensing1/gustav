"""
Regression tests for test-environment hardening.

Goals:
- Unit/in-process pytest runs must not auto-load `.env`.
- Integration suites may load `.env`, but only when explicitly enabled via
  RUN_* flags *and* marker selection (e.g. `pytest -m e2e`).
- Global OIDC state store (main.RUNTIME.state_store) needs a clean instance per test.
"""

from __future__ import annotations

import importlib
import os
import sys
import types
from pathlib import Path

import pytest


pytestmark = pytest.mark.db_write


@pytest.fixture
def reload_backend_conftest(monkeypatch: pytest.MonkeyPatch):
    """
    Helper to reload `backend.tests.conftest` with controlled environment flags.

    Returns a callable: (run_e2e_value) -> (module, load_dotenv_calls).
    """

    def _reload(run_e2e_value: str | None) -> tuple[types.ModuleType, dict[str, int]]:
        module_name = "backend.tests.conftest"
        # Drop previously imported module so the guarded load logic re-runs.
        sys.modules.pop(module_name, None)
        # Ensure we import the package fresh as well (pytest may cache the package).
        sys.modules.pop("backend.tests", None)

        # Fake dotenv module that counts load_dotenv invocations.
        load_calls = {"count": 0}

        def _fake_load_dotenv(*args, **kwargs):
            load_calls["count"] += 1

        monkeypatch.setitem(sys.modules, "dotenv", types.SimpleNamespace(load_dotenv=_fake_load_dotenv))

        if run_e2e_value is None:
            monkeypatch.delenv("RUN_E2E", raising=False)
        else:
            monkeypatch.setenv("RUN_E2E", run_e2e_value)

        mod = importlib.import_module(module_name)
        return mod, load_calls

    yield _reload
    monkeypatch.delenv("RUN_E2E", raising=False)
    sys.modules.pop("dotenv", None)
    importlib.import_module("backend.tests.conftest")


@pytest.fixture
def reload_backend_conftest_openai(monkeypatch: pytest.MonkeyPatch):
    """
    Helper to reload `backend.tests.conftest` with controlled RUN_OPENAI_E2E flag.

    Returns a callable: (run_openai_value) -> (module, load_dotenv_calls).
    """

    def _reload(run_openai_value: str | None) -> tuple[types.ModuleType, dict[str, int]]:
        module_name = "backend.tests.conftest"
        sys.modules.pop(module_name, None)
        sys.modules.pop("backend.tests", None)

        load_calls = {"count": 0}

        def _fake_load_dotenv(*args, **kwargs):
            load_calls["count"] += 1

        monkeypatch.setitem(sys.modules, "dotenv", types.SimpleNamespace(load_dotenv=_fake_load_dotenv))

        # Ensure other integration flags are not accidentally active.
        monkeypatch.delenv("RUN_E2E", raising=False)
        monkeypatch.delenv("RUN_SUPABASE_E2E", raising=False)

        if run_openai_value is None:
            monkeypatch.delenv("RUN_OPENAI_E2E", raising=False)
        else:
            monkeypatch.setenv("RUN_OPENAI_E2E", run_openai_value)

        mod = importlib.import_module(module_name)
        return mod, load_calls

    yield _reload
    monkeypatch.delenv("RUN_OPENAI_E2E", raising=False)
    sys.modules.pop("dotenv", None)
    importlib.import_module("backend.tests.conftest")


@pytest.fixture
def reload_backend_e2e_conftest(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """
    Reload `backend.tests_e2e.conftest` and record load_dotenv invocations.
    """

    def _reload(run_e2e_value: str | None) -> int:
        module_name = "backend.tests_e2e.conftest"
        sys.modules.pop(module_name, None)
        sys.modules.pop("backend.tests_e2e", None)

        load_calls = {"count": 0}

        def _fake_load_dotenv(*args, **kwargs):
            load_calls["count"] += 1

        monkeypatch.setitem(sys.modules, "dotenv", types.SimpleNamespace(load_dotenv=_fake_load_dotenv))

        if run_e2e_value is None:
            monkeypatch.delenv("RUN_E2E", raising=False)
        else:
            monkeypatch.setenv("RUN_E2E", run_e2e_value)
        if run_e2e_value == "1":
            ca_bundle = tmp_path / "caddy-root.crt"
            ca_bundle.write_text("test-ca", encoding="utf-8")
            monkeypatch.setenv("E2E_VERIFY_TLS", "1")
            monkeypatch.setenv("REQUESTS_CA_BUNDLE", str(ca_bundle))

        importlib.import_module(module_name)
        return load_calls["count"]

    yield _reload
    monkeypatch.delenv("RUN_E2E", raising=False)
    monkeypatch.delenv("E2E_VERIFY_TLS", raising=False)
    monkeypatch.delenv("REQUESTS_CA_BUNDLE", raising=False)
    sys.modules.pop("dotenv", None)
    importlib.import_module("backend.tests_e2e.conftest")


def test_dotenv_not_loaded_when_run_e2e_disabled(reload_backend_conftest):
    mod, calls = reload_backend_conftest(run_e2e_value=None)
    assert calls["count"] == 0, "load_dotenv should be skipped for the unit/in-process suite"
    mod.pytest_configure(types.SimpleNamespace(option=types.SimpleNamespace(markexpr="e2e")))
    assert calls["count"] == 0, "Marker selection alone must not load `.env` without RUN_* flags"

    mod_zero, calls_zero = reload_backend_conftest(run_e2e_value="0")
    assert calls_zero["count"] == 0, "load_dotenv should remain disabled when RUN_E2E != '1'"
    mod_zero.pytest_configure(types.SimpleNamespace(option=types.SimpleNamespace(markexpr="e2e")))
    assert calls_zero["count"] == 0


def test_run_e2e_requires_marker_selection(reload_backend_conftest):
    mod, calls = reload_backend_conftest(run_e2e_value="1")
    with pytest.raises(pytest.UsageError):
        mod.pytest_configure(types.SimpleNamespace(option=types.SimpleNamespace(markexpr="")))
    assert calls["count"] == 0, "Guard should reject accidental full-suite runs with RUN_E2E=1"


def test_dotenv_loaded_when_run_e2e_enabled_and_marked(reload_backend_conftest):
    mod, calls = reload_backend_conftest(run_e2e_value="1")
    mod.pytest_configure(types.SimpleNamespace(option=types.SimpleNamespace(markexpr="e2e")))
    assert calls["count"] == 1, "RUN_E2E=1 + marker selection should trigger dotenv loading"


def test_dotenv_not_loaded_when_run_openai_disabled(reload_backend_conftest_openai):
    mod, calls = reload_backend_conftest_openai(run_openai_value=None)
    assert calls["count"] == 0
    mod.pytest_configure(types.SimpleNamespace(option=types.SimpleNamespace(markexpr="openai_integration")))
    assert calls["count"] == 0

    mod_zero, calls_zero = reload_backend_conftest_openai(run_openai_value="0")
    assert calls_zero["count"] == 0
    mod_zero.pytest_configure(types.SimpleNamespace(option=types.SimpleNamespace(markexpr="openai_integration")))
    assert calls_zero["count"] == 0


def test_run_openai_requires_marker_selection(reload_backend_conftest_openai):
    mod, calls = reload_backend_conftest_openai(run_openai_value="1")
    with pytest.raises(pytest.UsageError):
        mod.pytest_configure(types.SimpleNamespace(option=types.SimpleNamespace(markexpr="")))
    assert calls["count"] == 0


def test_dotenv_loaded_when_run_openai_enabled_and_marked(reload_backend_conftest_openai):
    mod, calls = reload_backend_conftest_openai(run_openai_value="1")
    mod.pytest_configure(types.SimpleNamespace(option=types.SimpleNamespace(markexpr="openai_integration")))
    assert calls["count"] == 1


def test_e2e_conftest_gate_respects_run_e2e_flag(reload_backend_e2e_conftest):
    calls = reload_backend_e2e_conftest(run_e2e_value=None)
    assert calls == 0, "E2E conftest must skip dotenv when RUN_E2E is unset"
    calls_zero = reload_backend_e2e_conftest(run_e2e_value="0")
    assert calls_zero == 0, "E2E conftest must skip dotenv when RUN_E2E=0"
    calls_one = reload_backend_e2e_conftest(run_e2e_value="1")
    assert calls_one == 1, "E2E conftest must load dotenv once when RUN_E2E=1"


def test_e2e_conftest_derives_email_domain_from_allowed_registration_domains(
    monkeypatch: pytest.MonkeyPatch,
    reload_backend_e2e_conftest,
):
    monkeypatch.delenv("E2E_EMAIL_DOMAIN", raising=False)
    monkeypatch.setenv("ALLOWED_REGISTRATION_DOMAINS", "@school.example,@other.example")

    calls = reload_backend_e2e_conftest(run_e2e_value="1")

    assert calls == 1
    assert os.getenv("E2E_EMAIL_DOMAIN") == "school.example"


def test_e2e_conftest_keeps_explicit_email_domain_override(
    monkeypatch: pytest.MonkeyPatch,
    reload_backend_e2e_conftest,
):
    monkeypatch.setenv("E2E_EMAIL_DOMAIN", "custom.example")
    monkeypatch.setenv("ALLOWED_REGISTRATION_DOMAINS", "@school.example")

    calls = reload_backend_e2e_conftest(run_e2e_value="1")

    assert calls == 1
    assert os.getenv("E2E_EMAIL_DOMAIN") == "custom.example"


class _CollectedItem:
    def __init__(self, path: Path, *, marked_legacy: bool = False) -> None:
        self.fspath = str(path)
        self.path = path
        self.keywords: dict[str, bool] = {"legacy_migration": True} if marked_legacy else {}
        self.markers: list[object] = []

    def add_marker(self, marker: object) -> None:
        self.markers.append(marker)


def _marker_names(item: _CollectedItem) -> set[str]:
    names: set[str] = set()
    for marker in item.markers:
        mark = getattr(marker, "mark", marker)
        name = getattr(mark, "name", None)
        if name:
            names.add(str(name))
    return names


def test_legacy_migration_marker_is_default_skip_source(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import backend.tests.conftest as mod

    monkeypatch.delenv("RUN_LEGACY_MIGRATION_TESTS", raising=False)
    neutral_path = tmp_path / "test_neutral_name.py"
    neutral_path.write_text("def test_placeholder():\n    assert True\n", encoding="utf-8")
    item = _CollectedItem(neutral_path, marked_legacy=True)

    mod.pytest_collection_modifyitems(None, [item])

    assert "skip" in _marker_names(item)


def test_legacy_migration_tests_can_be_enabled_explicitly(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import backend.tests.conftest as mod

    monkeypatch.setenv("RUN_LEGACY_MIGRATION_TESTS", "1")
    neutral_path = tmp_path / "test_neutral_name.py"
    neutral_path.write_text("def test_placeholder():\n    assert True\n", encoding="utf-8")
    item = _CollectedItem(neutral_path, marked_legacy=True)

    mod.pytest_collection_modifyitems(None, [item])

    assert "skip" not in _marker_names(item)


def test_unmarked_global_public_truncate_is_rejected(tmp_path: Path) -> None:
    import backend.tests.conftest as mod

    destructive_path = tmp_path / "test_destructive.py"
    destructive_sql = "truncate table " + "public.courses cascade"
    destructive_path.write_text(
        f'SQL = "{destructive_sql}"\n'
        "def test_placeholder():\n"
        "    assert SQL\n",
        encoding="utf-8",
    )
    item = _CollectedItem(destructive_path)

    with pytest.raises(pytest.UsageError, match="legacy_migration"):
        mod.pytest_collection_modifyitems(None, [item])


def test_service_dsn_prefers_supabase_admin_when_available(monkeypatch: pytest.MonkeyPatch):
    """Service DSN defaults should prefer supabase_admin over postgres."""
    module_name = "backend.tests.conftest"
    sys.modules.pop(module_name, None)
    sys.modules.pop("backend.tests", None)

    class _Conn:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def _connect(dsn: str, connect_timeout: int = 5):  # noqa: ARG001
        if dsn.startswith("postgresql://supabase_admin:postgres@127.0.0.1:54322/postgres"):
            return _Conn()
        if dsn.startswith("postgresql://postgres:postgres@127.0.0.1:54322/postgres"):
            return _Conn()
        if dsn.startswith("postgresql://gustav_app:CHANGE_ME_DEV@127.0.0.1:54322/postgres"):
            return _Conn()
        raise RuntimeError("unreachable")

    monkeypatch.setitem(sys.modules, "psycopg", types.SimpleNamespace(connect=_connect))
    for key in ("SERVICE_ROLE_DSN", "RLS_TEST_SERVICE_DSN", "SESSION_TEST_DSN", "RLS_TEST_DSN", "DATABASE_URL"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("APP_DB_USER", "gustav_app")
    monkeypatch.setenv("APP_DB_PASSWORD", "CHANGE_ME_DEV")

    importlib.import_module(module_name)
    service_dsn = os.getenv("SERVICE_ROLE_DSN", "")
    assert service_dsn.startswith("postgresql://supabase_admin:postgres@127.0.0.1:54322/postgres")


def test_service_dsn_falls_back_to_postgres_when_supabase_admin_unreachable(monkeypatch: pytest.MonkeyPatch):
    """Keep compatibility with setups where postgres remains the service DSN."""
    module_name = "backend.tests.conftest"
    sys.modules.pop(module_name, None)
    sys.modules.pop("backend.tests", None)

    class _Conn:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def _connect(dsn: str, connect_timeout: int = 5):  # noqa: ARG001
        if dsn.startswith("postgresql://supabase_admin:postgres@127.0.0.1:54322/postgres"):
            raise RuntimeError("supabase_admin unavailable")
        if dsn.startswith("postgresql://postgres:postgres@127.0.0.1:54322/postgres"):
            return _Conn()
        if dsn.startswith("postgresql://gustav_app:CHANGE_ME_DEV@127.0.0.1:54322/postgres"):
            return _Conn()
        raise RuntimeError("unreachable")

    monkeypatch.setitem(sys.modules, "psycopg", types.SimpleNamespace(connect=_connect))
    for key in ("SERVICE_ROLE_DSN", "RLS_TEST_SERVICE_DSN", "SESSION_TEST_DSN", "RLS_TEST_DSN", "DATABASE_URL"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("APP_DB_USER", "gustav_app")
    monkeypatch.setenv("APP_DB_PASSWORD", "CHANGE_ME_DEV")

    importlib.import_module(module_name)
    service_dsn = os.getenv("SERVICE_ROLE_DSN", "")
    assert service_dsn.startswith("postgresql://postgres:postgres@127.0.0.1:54322/postgres")


def test_state_store_reset_fixture_creates_session_state():
    # Sanity: a test can create login state via Runtime state storage.
    import backend.web.main as main

    rec = main.RUNTIME.state_store.create(code_verifier="verifier")
    assert rec.state, "Runtime state store should allow creating records inside a test"
    getattr(main.RUNTIME.state_store, "_data", {}).clear()


def test_state_store_reset_fixture_provides_fresh_store():
    import backend.web.main as main

    # The autouse fixture should ensure the store has no leftover data.
    data = getattr(main.RUNTIME.state_store, "_data", {})
    assert not data, "Runtime state store must be cleared between tests to avoid 400 callbacks"
