"""Contracts for app-session TTL and cookie helpers."""

from __future__ import annotations

import logging
from pathlib import Path
from http.cookies import SimpleCookie

from starlette.responses import Response

from backend.web.auth_session import (
    SESSION_COOKIE_NAME,
    app_session_ttl_seconds,
    session_cookie_options,
    set_session_cookie,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_app_session_ttl_seconds_defaults_clamps_and_warns(monkeypatch, caplog) -> None:
    """Session TTL bounds protect classroom continuity without infinite sessions."""

    monkeypatch.delenv("APP_SESSION_TTL_SECONDS", raising=False)
    assert app_session_ttl_seconds() == 24 * 60 * 60

    monkeypatch.setenv("APP_SESSION_TTL_SECONDS", "1")
    assert app_session_ttl_seconds() == 15 * 60

    monkeypatch.setenv("APP_SESSION_TTL_SECONDS", str(8 * 24 * 60 * 60))
    assert app_session_ttl_seconds() == 7 * 24 * 60 * 60

    caplog.set_level(logging.WARNING, logger="gustav.identity_access")
    monkeypatch.setenv("APP_SESSION_TTL_SECONDS", "not-an-int")
    assert app_session_ttl_seconds() == 24 * 60 * 60
    assert any("Invalid APP_SESSION_TTL_SECONDS" in rec.message for rec in caplog.records)


def test_session_cookie_options_follow_environment_policy() -> None:
    """Cookie flags stay centralized and environment-aware."""

    assert session_cookie_options("prod") == {"secure": True, "samesite": "lax"}
    assert session_cookie_options("dev") == {"secure": True, "samesite": "lax"}


def test_set_session_cookie_writes_opaque_httponly_cookie() -> None:
    """Only the opaque session id goes to the browser."""

    response = Response()

    set_session_cookie(response, "session-id", environment="prod", max_age=7200)

    cookie = SimpleCookie(response.headers["set-cookie"])
    morsel = cookie[SESSION_COOKIE_NAME]
    assert morsel.value == "session-id"
    assert morsel["httponly"]
    assert morsel["secure"]
    assert morsel["samesite"].lower() == "lax"
    assert morsel["max-age"] == "7200"
    assert morsel["path"] == "/"


def test_main_delegates_session_cookie_logic_to_auth_session_module() -> None:
    """The app entry module should not own session TTL or cookie flag logic."""

    main_source = (REPO_ROOT / "backend/web/main.py").read_text(encoding="utf-8")
    auth_bridge_source = (REPO_ROOT / "backend/web/auth_bridge.py").read_text(encoding="utf-8")

    for retired_helper in (
        "def _app_session_ttl_seconds",
        "def _session_cookie_options",
        "def _set_session_cookie",
        "from backend.web.auth_utils import cookie_opts",
    ):
        assert retired_helper not in main_source

    assert "from backend.web.auth_session import SESSION_COOKIE_NAME" in main_source
    assert "from backend.web.auth_session import app_session_ttl_seconds, set_session_cookie" in auth_bridge_source
    assert "app_session_ttl_seconds(" in auth_bridge_source
    assert "set_session_cookie(" in auth_bridge_source
