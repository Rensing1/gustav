"""
Phase 2 hardening: Nonce, Cookie TTL, expires_at (Green)

Covered:
- Login authorization URL includes `nonce` parameter
- Callback rejects when ID token nonce mismatches the stored login nonce
- In PROD, session cookie includes Max-Age equal to server session TTL (default 3600)
- /api/me includes expires_at (UTC ISO-8601) and no-store header
"""

from __future__ import annotations

import re
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
async def test_login_includes_nonce_param():
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        r = await client.get("/auth/login", follow_redirects=False)
    assert r.status_code in (302, 303)
    loc = r.headers.get("location", "")
    qs = parse_qs(urlparse(loc).query)
    assert "nonce" in qs, "Authorization URL should include nonce (RED)"
    assert qs["nonce"][0], "nonce must be non-empty"


@pytest.mark.anyio
async def test_callback_rejects_when_id_token_nonce_mismatch(monkeypatch: pytest.MonkeyPatch):
    # Arrange: Force OIDC to return a token; force verification to return claims with wrong nonce
    class FakeOIDC:
        def __init__(self):
            self.cfg = main.OIDC_CFG

        def exchange_code_for_tokens(self, *, code: str, code_verifier: str):
            return {"id_token": "fake-valid-id-token"}

    monkeypatch.setattr(main, "OIDC", FakeOIDC())

    def fake_verify(id_token: str, cfg: object):
        return {
            "email": "user@example.com",
            "realm_access": {"roles": ["student"]},
            "email_verified": True,
            "nonce": "other-nonce",
        }

    monkeypatch.setattr(main, "verify_id_token", fake_verify)

    # Act: start login to get a state, then complete callback with mismatching nonce claims
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        r_login = await client.get("/auth/login", follow_redirects=False)
        qs = parse_qs(urlparse(r_login.headers.get("location", "")).query)
        state = qs.get("state", [None])[0]
        assert state, "state must be present for callback"
        r_cb = await client.get(f"/auth/callback?code=valid&state={state}")
    # Assert: should be 400 once nonce checking is implemented
    assert r_cb.status_code == 400, "Callback should reject nonce mismatch (RED)"
    assert r_cb.headers.get("Cache-Control") == "no-store"


@pytest.mark.anyio
async def test_callback_sets_cookie_max_age_matches_session_ttl_prod(monkeypatch: pytest.MonkeyPatch):
    # Arrange: run in prod to assert Secure/Strict and Max-Age
    main.SETTINGS.override_environment("prod")

    class FakeOIDC:
        def __init__(self):
            self.cfg = main.OIDC_CFG

        def exchange_code_for_tokens(self, *, code: str, code_verifier: str):
            return {"id_token": "fake-valid-id-token"}

    monkeypatch.setattr(main, "OIDC", FakeOIDC())

    try:
        async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
            r_login = await client.get("/auth/login", follow_redirects=False)
            qs = parse_qs(urlparse(r_login.headers.get("location", "")).query)
            state = qs.get("state", [None])[0]
            # Provide matching nonce in verification claims to satisfy nonce check
            rec = getattr(main.STATE_STORE, "_data", {}).get(state)
            expected_nonce = getattr(rec, "nonce", None)

            def fake_verify(id_token: str, cfg: object):
                return {
                    "email": "user@example.com",
                    "realm_access": {"roles": ["student"]},
                    "email_verified": True,
                    "nonce": expected_nonce,
                }

            monkeypatch.setattr(main, "verify_id_token", fake_verify)
            r_cb = await client.get(f"/auth/callback?code=valid&state={state}", follow_redirects=False)
        assert r_cb.status_code in (302, 303)
        sc = r_cb.headers.get("set-cookie", "")
        # Expect Max-Age=3600 and strict/secure flags in prod (RED)
        assert re.search(r"Max-Age=3600", sc, re.I), sc
        assert "SameSite=strict" in sc
        assert "Secure" in sc
    finally:
        main.SETTINGS.override_environment(None)


@pytest.mark.anyio
async def test_me_includes_expires_at_and_no_store():
    # Create a fake session and call /api/me
    sess = main.SESSION_STORE.create(sub="user-123", name="Max Musterschüler", roles=["student"])
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set("gustav_session", sess.session_id)
        r = await client.get("/api/me")
    assert r.status_code == 200
    assert r.headers.get("Cache-Control") == "no-store"
    body = r.json()
    # expires_at must be present and ISO-8601 like
    assert "expires_at" in body, "RED: endpoint should include expires_at"
    assert isinstance(body["expires_at"], str)
    assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", body["expires_at"]) or "+" in body["expires_at"], body["expires_at"]


@pytest.mark.anyio
async def test_register_includes_nonce_param():
    """Authorization URL for /auth/register must contain a nonce parameter."""
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        r = await client.get("/auth/register", follow_redirects=False)
    assert r.status_code in (302, 303)
    loc = r.headers.get("location", "")
    qs = parse_qs(urlparse(loc).query)
    assert "nonce" in qs and qs["nonce"][0], "Expected nonce in /auth/register authorization URL"
