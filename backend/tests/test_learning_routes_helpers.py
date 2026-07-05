"""
Learning routes — internal helper tests.

Focus:
    - _current_environment: resolves environment from app settings or env vars.
    - _encode_proxy_headers / _decode_proxy_headers: roundtrip and error paths.
"""
from __future__ import annotations

import base64
import importlib
import json
from pathlib import Path
import sys
import types

import pytest

learning = importlib.import_module("backend.web.routes.learning")
PROJECT_ROOT = Path(__file__).resolve().parents[2]
LEARNING_SOURCE = PROJECT_ROOT / "backend" / "web" / "routes" / "learning.py"
UPLOAD_CONFIG_SOURCE = PROJECT_ROOT / "backend" / "web" / "routes" / "learning_upload_config.py"


def test_upload_config_helpers_live_outside_learning_hotspot() -> None:
    upload_config = importlib.import_module("backend.web.routes.learning_upload_config")
    learning_source = LEARNING_SOURCE.read_text(encoding="utf-8")
    upload_config_source = UPLOAD_CONFIG_SOURCE.read_text(encoding="utf-8")

    assert "def _upload_intent_ttl_seconds(" not in learning_source
    assert "def _dev_upload_stub_enabled(" not in learning_source
    assert "def _upload_proxy_enabled(" not in learning_source
    assert "def _upload_proxy_timeout_seconds(" not in learning_source
    assert "def upload_intent_ttl_seconds(" in upload_config_source
    assert "def dev_upload_stub_enabled(" in upload_config_source
    assert "def upload_proxy_enabled(" in upload_config_source
    assert "def upload_proxy_timeout_seconds(" in upload_config_source
    assert learning._upload_intent_ttl_seconds is upload_config.upload_intent_ttl_seconds
    assert learning._dev_upload_stub_enabled is upload_config.dev_upload_stub_enabled
    assert learning._upload_proxy_enabled is upload_config.upload_proxy_enabled
    assert learning._upload_proxy_timeout_seconds is upload_config.upload_proxy_timeout_seconds


def test_upload_config_helpers_keep_clamp_and_boolean_rules(monkeypatch: pytest.MonkeyPatch) -> None:
    upload_config = importlib.import_module("backend.web.routes.learning_upload_config")

    monkeypatch.setenv("LEARNING_UPLOAD_INTENT_TTL_SECONDS", "30")
    assert upload_config.upload_intent_ttl_seconds() == 60
    monkeypatch.setenv("LEARNING_UPLOAD_INTENT_TTL_SECONDS", str(48 * 60 * 60))
    assert upload_config.upload_intent_ttl_seconds() == 24 * 60 * 60
    monkeypatch.setenv("LEARNING_UPLOAD_INTENT_TTL_SECONDS", "bad")
    assert upload_config.upload_intent_ttl_seconds() == 600

    monkeypatch.setenv("LEARNING_UPLOAD_PROXY_TIMEOUT_SECONDS", "2")
    assert upload_config.upload_proxy_timeout_seconds() == 5.0
    monkeypatch.setenv("LEARNING_UPLOAD_PROXY_TIMEOUT_SECONDS", "500")
    assert upload_config.upload_proxy_timeout_seconds() == 120.0
    monkeypatch.setenv("LEARNING_UPLOAD_PROXY_TIMEOUT_SECONDS", "bad")
    assert upload_config.upload_proxy_timeout_seconds() == 30.0

    monkeypatch.setenv("ENABLE_DEV_UPLOAD_STUB", "true")
    monkeypatch.setenv("ENABLE_STORAGE_UPLOAD_PROXY", " TRUE ")
    assert upload_config.dev_upload_stub_enabled() is True
    assert upload_config.upload_proxy_enabled() is True


def test_encode_proxy_headers_none_and_empty():
    # None or empty mappings must not produce a token.
    assert learning._encode_proxy_headers(None) is None  # type: ignore[arg-type]
    assert learning._encode_proxy_headers({}) is None


def test_encode_and_decode_proxy_headers_roundtrip_simple_dict():
    headers = {"X-Upsert": "true", "Content-Type": "image/png"}

    token = learning._encode_proxy_headers(headers)
    assert isinstance(token, str)

    decoded = learning._decode_proxy_headers(token)
    assert decoded == headers


def test_encode_proxy_headers_filters_invalid_entries():
    headers = {
        None: "ignored",  # type: ignore[key-var]
        "": "ignored",
        "WithNone": None,
        "X-Valid": "ok",
    }

    token = learning._encode_proxy_headers(headers)  # type: ignore[arg-type]
    assert isinstance(token, str)

    decoded = learning._decode_proxy_headers(token)
    assert decoded == {"X-Valid": "ok"}


def test_encode_proxy_headers_accepts_sequence_of_pairs():
    headers_sequence = [("X-A", "1"), ("X-B", "2")]

    token = learning._encode_proxy_headers(headers_sequence)  # type: ignore[arg-type]
    assert isinstance(token, str)

    decoded = learning._decode_proxy_headers(token)
    assert decoded == {"X-A": "1", "X-B": "2"}


def test_encode_proxy_headers_invalid_mapping_returns_none():
    # Objects that cannot be converted via dict(...) must fail gracefully.
    token = learning._encode_proxy_headers(42)  # type: ignore[arg-type]
    assert token is None


def test_decode_proxy_headers_none_or_empty():
    assert learning._decode_proxy_headers(None) == {}  # type: ignore[arg-type]
    assert learning._decode_proxy_headers("") == {}


def test_decode_proxy_headers_invalid_token_returns_empty():
    # Non-base64 input must not raise, but return an empty mapping.
    decoded = learning._decode_proxy_headers("not-a-valid-base64-token")
    assert decoded == {}


def test_decode_proxy_headers_non_dict_json_returns_empty():
    payload = json.dumps(["x", "y"]).encode("utf-8")
    token = base64.urlsafe_b64encode(payload).decode("ascii")

    decoded = learning._decode_proxy_headers(token)
    assert decoded == {}


def test_decode_proxy_headers_ignores_non_string_values():
    payload = json.dumps({"X": 1, "Y": "ok"}).encode("utf-8")
    token = base64.urlsafe_b64encode(payload).decode("ascii")

    decoded = learning._decode_proxy_headers(token)
    assert decoded == {"Y": "ok"}


def test_current_environment_prefers_settings_over_env(monkeypatch: pytest.MonkeyPatch):
    main = importlib.import_module("backend.web.main")

    # Ensure app settings override the environment variable.
    main.RUNTIME.settings.override_environment("prod")  # type: ignore[attr-defined]
    monkeypatch.setenv("GUSTAV_ENV", "dev")

    env = learning._current_environment()
    assert env == "prod"


def test_current_environment_prefers_loaded_module_when_imports_fail(monkeypatch: pytest.MonkeyPatch):
    """If modules are already loaded, import failures must not drop overrides."""

    class DummySettings:
        def __init__(self) -> None:
            self._env = "dev"
            self._env_override: str | None = None

        @property
        def environment(self) -> str:
            return self._env

        def override_environment(self, env: str | None) -> None:
            self._env_override = env
            self._env = (env or "dev")

    dummy_settings = DummySettings()
    dummy_settings.override_environment("prod")
    dummy_main = types.SimpleNamespace(RUNTIME=types.SimpleNamespace(settings=dummy_settings))

    monkeypatch.setitem(sys.modules, "backend.web.main", dummy_main)

    real_import_module = importlib.import_module

    def fake_import_module(name: str):
        if name in ("backend.web.main",):
            raise ImportError("simulated module loader failure")
        return real_import_module(name)

    monkeypatch.setattr(importlib, "import_module", fake_import_module)
    monkeypatch.delenv("GUSTAV_ENV", raising=False)

    env = learning._current_environment()
    assert env == "prod"


def test_current_environment_falls_back_to_env_when_backend_main_import_fails(monkeypatch: pytest.MonkeyPatch):
    """If backend.web.main import fails, use GUSTAV_ENV instead of a flat main alias."""

    real_import_module = importlib.import_module

    def fake_import_module(name: str):
        if name == "backend.web.main":
            raise ImportError("simulated backend.web.main failure")
        return real_import_module(name)

    monkeypatch.setattr(importlib, "import_module", fake_import_module)
    monkeypatch.setenv("GUSTAV_ENV", "prod")

    env = learning._current_environment()
    assert env == "prod"


def test_current_environment_falls_back_to_env_when_no_module(monkeypatch: pytest.MonkeyPatch):
    """If backend.web.main is not importable, use GUSTAV_ENV."""
    real_import_module = importlib.import_module

    def fake_import_module(name: str):
        if name in ("backend.web.main",):
            raise ImportError("simulated failure")
        return real_import_module(name)

    monkeypatch.setattr(importlib, "import_module", fake_import_module)
    monkeypatch.setenv("GUSTAV_ENV", "prod")

    env = learning._current_environment()
    assert env == "prod"
