"""
Unit tests for the logout app base helper.

Scope:
- Extract base from typical REDIRECT_URI ending with /auth/callback
- Fallback behavior on invalid input
"""

from __future__ import annotations

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
sys.path.insert(0, str(WEB_DIR))

from routes.auth import _default_app_base  # type: ignore
import os
import contextlib


def _clear_env_vars(names: list[str]):
    """Temporarily clear selected environment variables for isolation."""
    class _Context:
        def __enter__(self):
            self.prev = {k: os.environ.get(k) for k in names}
            for k in names:
                if k in os.environ:
                    del os.environ[k]
            return self

        def __exit__(self, exc_type, exc, tb):
            for k, v in self.prev.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
            return False

    return _Context()


def test_default_app_base_strips_callback_suffix():
    base = _default_app_base("http://app.localhost:8100/auth/callback")
    assert base == "http://app.localhost:8100"


def test_default_app_base_returns_local_default_on_garbage():
    # Ensure env fallbacks do not influence this unit test
    with _clear_env_vars(["APP_BASE", "WEB_BASE", "REDIRECT_URI", "KC_PUBLIC_BASE_URL"]):
        base = _default_app_base(12345)  # type: ignore[arg-type]
    assert base == "https://app.localhost"
