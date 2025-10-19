"""
Display name precedence tests for /auth/callback.

Precedence:
- gustav_display_name > name > local part of email

Note: We mock token verification to focus on mapping logic.
"""

from __future__ import annotations

import pytest
import httpx
from httpx import ASGITransport
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))
import main  # type: ignore


pytestmark = pytest.mark.anyio("asyncio")


def _install_fake_oidc(monkeypatch: pytest.MonkeyPatch):
    class FakeOIDC:
        def __init__(self):
            self.cfg = main.OIDC_CFG

        def exchange_code_for_tokens(self, *, code: str, code_verifier: str):
            return {"id_token": "fake-id-token"}

    monkeypatch.setattr(main, "OIDC", FakeOIDC())


@pytest.mark.anyio
async def test_display_name_prefers_custom_claim(monkeypatch: pytest.MonkeyPatch):
    _install_fake_oidc(monkeypatch)

    def claims(_: str, __: object):
        return {
            "email": "student@example.com",
            "name": "Fallback Name",
            "gustav_display_name": "Custom Claim Name",
            "realm_access": {"roles": ["student"]},
            "email_verified": True,
        }

    monkeypatch.setattr(main, "verify_id_token", claims)

    rec = main.STATE_STORE.create(code_verifier="v")
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        r = await client.get(f"/auth/callback?code=any&state={rec.state}", follow_redirects=False)
    assert r.status_code in (302, 303)
    sc = r.headers.get("set-cookie", "")
    sid = sc.split("gustav_session=")[1].split(";")[0]
    session = main.SESSION_STORE.get(sid)
    assert session is not None
    assert session.name == "Custom Claim Name"


@pytest.mark.anyio
async def test_display_name_uses_standard_name_if_custom_missing(monkeypatch: pytest.MonkeyPatch):
    _install_fake_oidc(monkeypatch)

    def claims(_: str, __: object):
        return {
            "email": "student@example.com",
            "name": "Standard Name",
            "realm_access": {"roles": ["student"]},
            "email_verified": True,
        }

    monkeypatch.setattr(main, "verify_id_token", claims)

    rec = main.STATE_STORE.create(code_verifier="v")
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        r = await client.get(f"/auth/callback?code=any&state={rec.state}", follow_redirects=False)
    assert r.status_code in (302, 303)
    sc = r.headers.get("set-cookie", "")
    sid = sc.split("gustav_session=")[1].split(";")[0]
    session = main.SESSION_STORE.get(sid)
    assert session is not None
    assert session.name == "Standard Name"


@pytest.mark.anyio
async def test_display_name_falls_back_to_localpart(monkeypatch: pytest.MonkeyPatch):
    _install_fake_oidc(monkeypatch)

    def claims(_: str, __: object):
        return {
            "email": "localpart@example.com",
            # no name, no gustav_display_name
            "realm_access": {"roles": ["student"]},
            "email_verified": True,
        }

    monkeypatch.setattr(main, "verify_id_token", claims)

    rec = main.STATE_STORE.create(code_verifier="v")
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        r = await client.get(f"/auth/callback?code=any&state={rec.state}", follow_redirects=False)
    assert r.status_code in (302, 303)
    sc = r.headers.get("set-cookie", "")
    sid = sc.split("gustav_session=")[1].split(";")[0]
    session = main.SESSION_STORE.get(sid)
    assert session is not None
    assert session.name == "localpart"

