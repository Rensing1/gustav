"""
Regression tests for test-environment hardening.

Goals:
- Unit/integration pytest runs must not auto-load .env (unless RUN_E2E=1).
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

    Returns a callable: (run_e2e_value) -> load_dotenv_call_count.
    """

    def _reload(run_e2e_value: str | None) -> int:
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

        importlib.import_module(module_name)
        return load_calls["count"]

    yield _reload
    monkeypatch.delenv("RUN_E2E", raising=False)
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
    calls = reload_backend_conftest(run_e2e_value=None)
    assert calls == 0, "load_dotenv should be skipped for unit/integration pytest runs"
    calls_zero = reload_backend_conftest(run_e2e_value="0")
    assert calls_zero == 0, "load_dotenv should remain disabled when RUN_E2E != '1'"


def test_dotenv_loaded_when_run_e2e_enabled(reload_backend_conftest):
    calls = reload_backend_conftest(run_e2e_value="1")
    assert calls == 1, "RUN_E2E=1 should trigger dotenv loading for E2E"


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
