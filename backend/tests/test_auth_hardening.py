"""
Auth hardening tests (TDD: RED)

Covers:
- Client-supplied `state` is ignored (server-generated only)
- External redirects are rejected; fallback to "/"
- Callback 400 responses set Cache-Control: no-store
- SSR role display uses fixed priority (admin > teacher > student)
- Logout includes id_token_hint when available
"""

import sys
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import pytest
import httpx
from httpx import ASGITransport

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
sys.path.insert(0, str(WEB_DIR))
import main  # type: ignore


pytestmark = pytest.mark.anyio("asyncio")


@pytest.mark.anyio
async def test_login_ignores_client_state(monkeypatch: pytest.MonkeyPatch):
    """GET /auth/login must not propagate client-provided `state` value to IdP URL."""
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        r = await client.get("/auth/login?state=attacker", follow_redirects=False)
    assert r.status_code in (302, 303)
    loc = r.headers.get("location", "")
    qs = parse_qs(urlparse(loc).query)
    # Server must not reflect attacker-provided state
    assert qs.get("state") and qs.get("state")[0] != "attacker"


@pytest.mark.anyio
async def test_login_rejects_external_redirects(monkeypatch: pytest.MonkeyPatch):
    """Providing an external redirect must be ignored; callback redirects to '/'"""
    # Patch token exchange and verification to avoid external dependencies
    class FakeOIDC:
        def __init__(self):
            self.cfg = main.OIDC_CFG

        def exchange_code_for_tokens(self, *, code: str, code_verifier: str):
            return {"id_token": "fake-id-token"}

    monkeypatch.setattr(main, "OIDC", FakeOIDC())
    monkeypatch.setattr(main, "verify_id_token", lambda id_token, cfg: {
        "email": "user@example.com",
        "realm_access": {"roles": ["student"]},
        "email_verified": True,
    })

    # Start login with external redirect attempt
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        r_login = await client.get("/auth/login?redirect=https://evil.com", follow_redirects=False)
        assert r_login.status_code in (302, 303)
        qs = parse_qs(urlparse(r_login.headers.get("location", "")).query)
        state = qs.get("state", [None])[0]
        assert state, "state must be present in authorization URL"

        # Simulate IdP callback
        r_cb = await client.get(f"/auth/callback?code=valid&state={state}", follow_redirects=False)
        assert r_cb.status_code in (302, 303)
        # Must fall back to in-app root
        assert r_cb.headers.get("location") == "/"


@pytest.mark.anyio
async def test_callback_errors_set_no_store_header():
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        # Missing code/state
        r = await client.get("/auth/callback")
    assert r.status_code == 400
    assert r.headers.get("Cache-Control") == "no-store"


@pytest.mark.anyio
async def test_role_priority_for_ssr_display(monkeypatch: pytest.MonkeyPatch):
    """SSR sidebar must display primary role by fixed priority (admin>teacher>student)."""
    # Create a session with roles in an order that would be ambiguous without priority
    sess = main.SESSION_STORE.create(email="t@example.com", roles=["student", "teacher"], email_verified=True)
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set("gustav_session", sess.session_id)
        r = await client.get("/", follow_redirects=False)
    assert r.status_code == 200
    html = r.text
    # Expect German label for teacher (higher priority than student)
    assert "Lehrer" in html


@pytest.mark.anyio
async def test_logout_uses_id_token_hint_when_available(monkeypatch: pytest.MonkeyPatch):
    """If session contains an id_token, /auth/logout should include id_token_hint param."""
    class FakeOIDC:
        def __init__(self):
            self.cfg = main.OIDC_CFG

        def exchange_code_for_tokens(self, *, code: str, code_verifier: str):
            return {"id_token": "fake-id-token-123"}

    monkeypatch.setattr(main, "OIDC", FakeOIDC())
    monkeypatch.setattr(main, "verify_id_token", lambda id_token, cfg: {
        "email": "user@example.com",
        "realm_access": {"roles": ["student"]},
        "email_verified": True,
    })

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        # Create server-side session via callback first
        # Seed a valid state
        rec = main.STATE_STORE.create(code_verifier="v")
        r_cb = await client.get(f"/auth/callback?code=valid&state={rec.state}", follow_redirects=False)
        assert r_cb.status_code in (302, 303)
        # Use the established session to call logout
        # httpx client kept cookies from redirect response
        r_lo = await client.get("/auth/logout", follow_redirects=False)
    assert r_lo.status_code in (302, 303)
    loc = r_lo.headers.get("location", "")
    assert "id_token_hint=" in loc

