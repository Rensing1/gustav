"""
Phase 2 hardening: Nonce, Cookie TTL, expires_at (Green)

Covered:
- Login authorization URL includes `nonce` parameter
- Callback rejects when ID token nonce mismatches the stored login nonce
- In PROD, session cookie includes Max-Age equal to server session TTL (default 86400)
- /api/me includes expires_at (UTC ISO-8601) and no-store header
"""

from __future__ import annotations

import logging
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
from runtime_auth_helpers import install_oidc_client, install_session_store
from backend.web.auth_session import app_session_ttl_seconds


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
            self.cfg = main.RUNTIME.oidc_config

        def exchange_code_for_tokens(self, *, code: str, code_verifier: str):
            return {"id_token": "fake-valid-id-token"}

    install_oidc_client(monkeypatch, main, FakeOIDC())

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
    assert r_cb.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_callback_sets_cookie_max_age_matches_session_ttl_prod(monkeypatch: pytest.MonkeyPatch):
    # Arrange: run in prod to assert Secure/Strict and Max-Age
    main.RUNTIME.settings.override_environment("prod")

    class FakeOIDC:
        def __init__(self):
            self.cfg = main.RUNTIME.oidc_config

        def exchange_code_for_tokens(self, *, code: str, code_verifier: str):
            return {"id_token": "fake-valid-id-token"}

    install_oidc_client(monkeypatch, main, FakeOIDC())

    try:
        async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
            r_login = await client.get("/auth/login", follow_redirects=False)
            qs = parse_qs(urlparse(r_login.headers.get("location", "")).query)
            state = qs.get("state", [None])[0]
            # Provide matching nonce in verification claims to satisfy nonce check
            rec = getattr(main.RUNTIME.state_store, "_data", {}).get(state)
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
        # Expect Max-Age default (86400) and strict/secure flags in prod (RED)
        assert re.search(r"Max-Age=86400", sc, re.I), sc
        assert "SameSite=lax" in sc
        assert "Secure" in sc
    finally:
        main.RUNTIME.settings.override_environment(None)


@pytest.mark.anyio
async def test_callback_cookie_max_age_respects_app_session_ttl_env(monkeypatch: pytest.MonkeyPatch):
    """When APP_SESSION_TTL_SECONDS is set, the session cookie Max-Age must match it (prod only)."""
    monkeypatch.setenv("APP_SESSION_TTL_SECONDS", "7200")
    main.RUNTIME.settings.override_environment("prod")

    class FakeOIDC:
        def __init__(self):
            self.cfg = main.RUNTIME.oidc_config

        def exchange_code_for_tokens(self, *, code: str, code_verifier: str):
            return {"id_token": "fake-valid-id-token"}

    install_oidc_client(monkeypatch, main, FakeOIDC())

    try:
        async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
            r_login = await client.get("/auth/login", follow_redirects=False)
            qs = parse_qs(urlparse(r_login.headers.get("location", "")).query)
            state = qs.get("state", [None])[0]
            assert state, "state must be present for callback"
            rec = getattr(main.RUNTIME.state_store, "_data", {}).get(state)
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
        assert re.search(r"Max-Age=7200", sc, re.I), sc
    finally:
        main.RUNTIME.settings.override_environment(None)


@pytest.mark.anyio
async def test_me_includes_expires_at_and_no_store(monkeypatch: pytest.MonkeyPatch):
    # Create a fake session and call /api/me
    store = install_session_store(monkeypatch, main)
    sess = store.create(sub="user-123", name="Max Musterschüler", roles=["student"])
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set("gustav_session", sess.session_id)
        r = await client.get("/api/me")
    assert r.status_code == 200
    assert r.headers.get("Cache-Control") == "private, no-store"
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


@pytest.mark.anyio
async def test_login_redirect_uri_uses_configured_scheme_when_proxy_hides_https(monkeypatch: pytest.MonkeyPatch):
    """If the app sits behind a TLS proxy, the internal ASGI scheme may be http.

    In that case, the authorization request must still use the configured
    (browser-facing) redirect_uri scheme; otherwise Keycloak will reject the
    token exchange with a redirect_uri mismatch.
    """
    monkeypatch.setenv("GUSTAV_TRUST_PROXY", "false")
    monkeypatch.setenv("WEB_BASE", "https://app.localhost")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://app.localhost") as client:
        r = await client.get("/auth/login", follow_redirects=False)

    assert r.status_code in (302, 303)
    loc = r.headers.get("location", "")
    qs = parse_qs(urlparse(loc).query)
    assert qs.get("redirect_uri") == ["https://app.localhost/auth/callback"]


def test_app_session_ttl_seconds_defaults_and_clamps(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture):
    # Default when unset
    monkeypatch.delenv("APP_SESSION_TTL_SECONDS", raising=False)
    assert app_session_ttl_seconds() == 86400

    # Clamp to [15 minutes, 7 days]
    monkeypatch.setenv("APP_SESSION_TTL_SECONDS", "1")
    assert app_session_ttl_seconds() == 15 * 60

    monkeypatch.setenv("APP_SESSION_TTL_SECONDS", str(8 * 24 * 60 * 60))
    assert app_session_ttl_seconds() == 7 * 24 * 60 * 60

    # Invalid values fall back and log a warning
    caplog.set_level(logging.WARNING, logger="gustav.identity_access")
    monkeypatch.setenv("APP_SESSION_TTL_SECONDS", "not-an-int")
    assert app_session_ttl_seconds() == 86400
    assert any("Invalid APP_SESSION_TTL_SECONDS" in rec.message for rec in caplog.records)
