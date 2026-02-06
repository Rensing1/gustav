"""
SSR CSRF token contract for session-bound signed tokens.

Why:
    SSR forms must remain valid across worker/process boundaries and should not
    rely on a per-process in-memory token map. Tokens must also expire.
"""

from __future__ import annotations

from pathlib import Path
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))

import main  # type: ignore


def _clear_legacy_csrf_map() -> None:
    """Best-effort clear of legacy stateful CSRF map for transition tests."""
    bucket = getattr(main, "_CSRF_BY_SESSION", None)
    if isinstance(bucket, dict):
        bucket.clear()


def test_ssr_csrf_token_survives_legacy_memory_map_reset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_CSRF_TOKEN_SECRET", "test-csrf-secret")
    monkeypatch.setenv("APP_CSRF_TTL_SECONDS", "3600")
    monkeypatch.setattr(main.time, "time", lambda: 1_700_000_000.0)

    sid = "session-signed-1"
    _clear_legacy_csrf_map()
    token = main._get_or_create_csrf_token(sid)
    _clear_legacy_csrf_map()

    assert token
    assert main._validate_csrf(sid, token) is True


def test_ssr_csrf_token_expires_by_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_CSRF_TOKEN_SECRET", "test-csrf-secret")
    monkeypatch.setenv("APP_CSRF_TTL_SECONDS", "1")

    sid = "session-signed-2"
    _clear_legacy_csrf_map()
    monkeypatch.setattr(main.time, "time", lambda: 2_000.0)
    token = main._get_or_create_csrf_token(sid)
    assert main._validate_csrf(sid, token) is True

    # TTL is bounded (min 60s), so advance beyond that boundary.
    monkeypatch.setattr(main.time, "time", lambda: 2_062.0)
    assert main._validate_csrf(sid, token) is False
