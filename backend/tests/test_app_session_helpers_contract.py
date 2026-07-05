"""Contracts for app-session helper ownership."""

from __future__ import annotations

import importlib
from pathlib import Path
from types import SimpleNamespace


PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_SOURCE = PROJECT_ROOT / "backend" / "web" / "routes" / "app.py"
HELPERS_SOURCE = PROJECT_ROOT / "backend" / "web" / "routes" / "app_session_helpers.py"


def test_app_session_helpers_live_outside_app_hotspot() -> None:
    app_routes = importlib.import_module("backend.web.routes.app")
    helpers = importlib.import_module("backend.web.routes.app_session_helpers")
    app_source = APP_SOURCE.read_text(encoding="utf-8")
    helpers_source = HELPERS_SOURCE.read_text(encoding="utf-8")

    assert "def _runtime_from_request(" not in app_source
    assert "def _bff_session_store(" not in app_source
    assert "def _session_store(" not in app_source
    assert "def _runtime_settings(" not in app_source
    assert "def _require_internal_bff_secret(" not in app_source
    assert "def _bff_session_payload(" not in app_source
    assert "def runtime_from_request(" in helpers_source
    assert "def bff_session_store(" in helpers_source
    assert "def session_store(" in helpers_source
    assert "def runtime_settings(" in helpers_source
    assert "def require_internal_bff_secret(" in helpers_source
    assert "def bff_session_payload(" in helpers_source
    assert app_routes._runtime_from_request is helpers.runtime_from_request
    assert app_routes._bff_session_store is helpers.bff_session_store
    assert app_routes._session_store is helpers.session_store
    assert app_routes._runtime_settings is helpers.runtime_settings
    assert app_routes._require_internal_bff_secret is helpers.require_internal_bff_secret
    assert app_routes._bff_session_payload is helpers.bff_session_payload


def test_app_session_helpers_keep_private_header_and_payload_rules(monkeypatch) -> None:
    helpers = importlib.import_module("backend.web.routes.app_session_helpers")

    assert helpers.private_headers() == {"Cache-Control": "private, no-store"}
    assert helpers.spaces_for_role("student") == ["learning"]
    assert helpers.spaces_for_role("teacher") == ["teaching", "diagnostics", "live"]
    assert helpers.start_target_for_role("student") == "/learning"
    assert helpers.start_target_for_role("teacher") == "/teaching"
    assert helpers.user_payload({"sub": "s1", "name": "Lena", "role": "student", "roles": ["student"]}) == {
        "sub": "s1",
        "name": "Lena",
        "role": "student",
        "roles": ["student"],
    }

    monkeypatch.setenv("BFF_INTERNAL_SHARED_SECRET", "shared")
    request = SimpleNamespace(headers={"x-gustav-internal-secret": "shared"})
    assert helpers.require_internal_bff_secret(request) is True
    bad_request = SimpleNamespace(headers={"x-gustav-internal-secret": "wrong"})
    assert helpers.require_internal_bff_secret(bad_request) is False


def test_app_session_helpers_resolve_runtime_stores() -> None:
    helpers = importlib.import_module("backend.web.routes.app_session_helpers")
    runtime = SimpleNamespace(
        bff_session_store=object(),
        session_store=object(),
        settings=SimpleNamespace(environment="test"),
        oidc_config=object(),
    )
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(runtime=runtime)))

    assert helpers.runtime_from_request(request) is runtime
    assert helpers.bff_session_store(request) is runtime.bff_session_store
    assert helpers.session_store(request) is runtime.session_store
    assert helpers.runtime_settings(request) is runtime.settings
    assert helpers.oidc_config(request) is runtime.oidc_config
