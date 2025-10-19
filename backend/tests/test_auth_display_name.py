"""
Tests for display name resolution precedence in /auth/callback.

Precedence:
- gustav_display_name > name > local part of email
"""

from __future__ import annotations

import httpx
import pytest
from httpx import ASGITransport
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
sys.path.insert(0, str(WEB_DIR))
import main  # type: ignore


pytestmark = pytest.mark.anyio("asyncio")


def _make_id_token(claim_overrides: dict | None = None) -> str:
    """Reuse helper from test_auth_contract by importing there.

    We duplicate a minimal wrapper to avoid tight coupling to test internals
    when running this file standalone (the import below is safe in our suite).
    """
    from backend.tests.test_auth_contract import _make_id_token as _mk  # type: ignore

    return _mk(claim_overrides=claim_overrides)


async def _call_with_token(monkeypatch: pytest.MonkeyPatch, id_token: str, expected_status: int = 302) -> httpx.Response:
    from backend.tests.test_auth_contract import _call_auth_callback_with_token  # type: ignore

    return await _call_auth_callback_with_token(monkeypatch, id_token, expected_status=expected_status)


@pytest.mark.anyio
async def test_display_name_prefers_custom_claim(monkeypatch: pytest.MonkeyPatch):
    token = _make_id_token({
        "email": "student@example.com",
        "name": "Fallback Name",
        "gustav_display_name": "Custom Claim Name",
    })
    resp = await _call_with_token(monkeypatch, token, expected_status=302)
    # Extract session id and assert stored name
    cookie = resp.headers.get("set-cookie", "")
    assert "gustav_session=" in cookie
    sid = cookie.split("gustav_session=")[1].split(";")[0]
    rec = main.SESSION_STORE.get(sid)
    assert rec is not None
    assert getattr(rec, "name", None) == "Custom Claim Name"


@pytest.mark.anyio
async def test_display_name_uses_standard_name_if_custom_missing(monkeypatch: pytest.MonkeyPatch):
    token = _make_id_token({
        "email": "student@example.com",
        "name": "Standard Name",
    })
    resp = await _call_with_token(monkeypatch, token, expected_status=302)
    cookie = resp.headers.get("set-cookie", "")
    sid = cookie.split("gustav_session=")[1].split(";")[0]
    rec = main.SESSION_STORE.get(sid)
    assert rec is not None
    assert getattr(rec, "name", None) == "Standard Name"


@pytest.mark.anyio
async def test_display_name_falls_back_to_localpart(monkeypatch: pytest.MonkeyPatch):
    token = _make_id_token({
        "email": "localpart@example.com",
        # no name, no gustav_display_name
    })
    resp = await _call_with_token(monkeypatch, token, expected_status=302)
    cookie = resp.headers.get("set-cookie", "")
    sid = cookie.split("gustav_session=")[1].split(";")[0]
    rec = main.SESSION_STORE.get(sid)
    assert rec is not None
    assert getattr(rec, "name", None) == "localpart"

