"""
Register flow: Nonce is required (Phase 2 hardening)

Covers:
- Authorization URL for /auth/register includes a nonce parameter
- Callback rejects when ID token nonce does not match the stored nonce
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse, parse_qs

import pytest
import httpx
from httpx import ASGITransport

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
import sys
sys.path.insert(0, str(WEB_DIR))
import main  # type: ignore


@pytest.fixture
def anyio_backend():
    # Force asyncio backend to avoid trio in restricted environments
    return "asyncio"


@pytest.mark.anyio
async def test_register_includes_nonce_param():
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        r = await client.get("/auth/register", follow_redirects=False)
    assert r.status_code in (302, 303)
    loc = r.headers.get("location", "")
    qs = parse_qs(urlparse(loc).query)
    assert "nonce" in qs, "Authorization URL should include nonce for /auth/register"
    assert qs["nonce"][0], "nonce must be non-empty"
    # Registration action param should be present as well
    assert "kc_action=register" in loc


@pytest.mark.anyio
async def test_register_callback_rejects_when_id_token_nonce_mismatch(monkeypatch: pytest.MonkeyPatch):
    """Callback should reject if the ID token nonce does not match the stored login/register nonce."""

    class FakeOIDC:
        def __init__(self):
            self.cfg = main.OIDC_CFG

        def exchange_code_for_tokens(self, *, code: str, code_verifier: str):
            return {"id_token": "fake-valid-id-token"}

    monkeypatch.setattr(main, "OIDC", FakeOIDC())

    def fake_verify(id_token: str, cfg: object):
        # Return claims with a wrong nonce on purpose
        return {
            "email": "user@example.com",
            "realm_access": {"roles": ["student"]},
            "email_verified": True,
            "nonce": "other-nonce",
        }

    monkeypatch.setattr(main, "verify_id_token", fake_verify)

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        # Start register flow
        r_register = await client.get("/auth/register", follow_redirects=False)
        qs = parse_qs(urlparse(r_register.headers.get("location", "")).query)
        state = qs.get("state", [None])[0]
        assert state, "state must be present for callback"
        # Complete callback with mismatching nonce
        r_cb = await client.get(f"/auth/callback?code=valid&state={state}")
    assert r_cb.status_code == 400
    assert r_cb.headers.get("Cache-Control") == "private, no-store"
    assert r_cb.json().get("error") in {"invalid_id_token", "invalid_nonce"}
