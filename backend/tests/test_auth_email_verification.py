"""
Auth callback: Email verification awareness tests.

Why:
    GUSTAV no longer enforces email verification itself. The IdP (Keycloak)
    remains the source of truth. These tests ensure that `/auth/callback`
    accepts both verified and unverified emails and never blocks login based
    on the `email_verified` claim.
"""

from __future__ import annotations

from pathlib import Path
import sys

import pytest
import httpx
from httpx import ASGITransport


REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))
import main  # type: ignore


pytestmark = pytest.mark.anyio("asyncio")


def _install_fake_oidc(monkeypatch: pytest.MonkeyPatch):
    """Install a minimal OIDC stub that always returns a fake id_token."""

    class FakeOIDC:
        def __init__(self):
            self.cfg = main.OIDC_CFG

        def exchange_code_for_tokens(self, *, code: str, code_verifier: str):
            return {"id_token": "fake-id-token"}

    monkeypatch.setattr(main, "OIDC", FakeOIDC())


@pytest.mark.anyio
async def test_callback_accepts_verified_email(monkeypatch: pytest.MonkeyPatch):
    """Verified emails must always be able to log in."""
    _install_fake_oidc(monkeypatch)

    def claims(id_token: str, cfg: object, cache=None):
        return {
            "sub": "user-1",
            "email": "student@gymalf.de",
            "realm_access": {"roles": ["student"]},
            "email_verified": True,
        }

    monkeypatch.setattr(main, "verify_id_token", claims)

    from identity_access.stores import StateStore, SessionStore

    monkeypatch.setattr(main, "STATE_STORE", StateStore())
    monkeypatch.setattr(main, "SESSION_STORE", SessionStore())
    rec = main.STATE_STORE.create(code_verifier="v")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        r = await client.get(f"/auth/callback?code=any&state={rec.state}", follow_redirects=False)

    assert r.status_code in (302, 303)
    sc = r.headers.get("set-cookie", "")
    assert "gustav_session=" in sc


@pytest.mark.anyio
async def test_callback_allows_unverified_email(monkeypatch: pytest.MonkeyPatch):
    """Unverified emails must not be blocked by GUSTAV."""
    _install_fake_oidc(monkeypatch)

    def claims(id_token: str, cfg: object, cache=None):
        return {
            "sub": "user-2",
            "email": "student@gymalf.de",
            "realm_access": {"roles": ["student"]},
            "email_verified": False,
        }

    monkeypatch.setattr(main, "verify_id_token", claims)

    from identity_access.stores import StateStore, SessionStore

    monkeypatch.setattr(main, "STATE_STORE", StateStore())
    monkeypatch.setattr(main, "SESSION_STORE", SessionStore())
    rec = main.STATE_STORE.create(code_verifier="v")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        r = await client.get(f"/auth/callback?code=any&state={rec.state}", follow_redirects=False)

    assert r.status_code in (302, 303)
    sc = r.headers.get("set-cookie", "")
    assert "gustav_session=" in sc


@pytest.mark.anyio
async def test_callback_treats_missing_claim_as_verified(monkeypatch: pytest.MonkeyPatch):
    """Missing email_verified claim must not break login (backwards compatible)."""
    _install_fake_oidc(monkeypatch)

    def claims(id_token: str, cfg: object, cache=None):
        # No email_verified claim on purpose
        return {
            "sub": "user-4",
            "email": "student@gymalf.de",
            "realm_access": {"roles": ["student"]},
        }

    monkeypatch.setattr(main, "verify_id_token", claims)

    from identity_access.stores import StateStore, SessionStore

    monkeypatch.setattr(main, "STATE_STORE", StateStore())
    monkeypatch.setattr(main, "SESSION_STORE", SessionStore())
    rec = main.STATE_STORE.create(code_verifier="v")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        r = await client.get(f"/auth/callback?code=any&state={rec.state}", follow_redirects=False)

    assert r.status_code in (302, 303)
    sc = r.headers.get("set-cookie", "")
    assert "gustav_session=" in sc
