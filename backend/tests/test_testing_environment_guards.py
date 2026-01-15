"""
Regression tests for test-environment hardening.

Goals:
- Unit/in-process pytest runs must not auto-load `.env`.
- Integration suites may load `.env`, but only when explicitly enabled via
  RUN_* flags *and* marker selection (e.g. `pytest -m e2e`).
- Global OIDC state store (main.STATE_STORE) needs a clean instance per test.
"""

from __future__ import annotations

import importlib
import sys
import types

import pytest


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
def reload_backend_e2e_conftest(monkeypatch: pytest.MonkeyPatch):
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

        importlib.import_module(module_name)
        return load_calls["count"]

    yield _reload
    monkeypatch.delenv("RUN_E2E", raising=False)
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


def test_state_store_reset_fixture_creates_session_state():
    # Sanity: a test can create login state via STATE_STORE.
    import backend.web.main as main

    rec = main.STATE_STORE.create(code_verifier="verifier")
    assert rec.state, "STATE_STORE should allow creating records inside a test"


def test_state_store_reset_fixture_provides_fresh_store():
    import backend.web.main as main

    # The autouse fixture should ensure the store has no leftover data.
    data = getattr(main.STATE_STORE, "_data", {})
    assert not data, "STATE_STORE must be cleared between tests to avoid 400 callbacks"
