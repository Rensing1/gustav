"""
Non-HTMX Auth redirects — ensure 302 Location and cache headers.

Covers /auth/login and /auth/register without HX-Request, verifying:
- 302 status
- Location contains required params (state; kc_action=register)
- Security headers: Cache-Control: private, no-store; Vary: HX-Request
"""

from __future__ import annotations

from urllib.parse import urlparse, parse_qs

import pytest
import httpx
from httpx import ASGITransport


from backend.web.auth_only_app import create_app_auth_only
from backend.identity_access.stores import StateStore
from backend.identity_access.oidc import OIDCConfig


pytestmark = pytest.mark.anyio("asyncio")


@pytest.mark.anyio
async def test_login_redirect_302_has_location_and_cache_headers(monkeypatch: pytest.MonkeyPatch):
    cfg = OIDCConfig(
        base_url="http://kc.localhost:8080",
        realm="gustav",
        client_id="gustav-web",
        redirect_uri="http://app.localhost:8100/auth/callback",
    )
    state_store = StateStore()
    monkeypatch.setenv("WEB_BASE", "http://app.localhost:8100")

    test_app = create_app_auth_only(oidc_config=cfg, state_store=state_store)
    async with httpx.AsyncClient(transport=ASGITransport(app=test_app), base_url="http://app.localhost:8100") as client:
        r = await client.get("/auth/login", follow_redirects=False)

    assert r.status_code == 302
    assert r.headers.get("Cache-Control") == "private, no-store"
    assert r.headers.get("Vary") == "HX-Request"

    loc = r.headers.get("Location")
    assert loc, "302 must include Location"
    parsed = urlparse(loc)
    qs = parse_qs(parsed.query)
    assert qs.get("state", [None])[0], "Authorization URL must include state"


@pytest.mark.anyio
async def test_register_redirect_302_has_location_and_kc_action(monkeypatch: pytest.MonkeyPatch):
    cfg = OIDCConfig(
        base_url="http://kc.localhost:8080",
        realm="gustav",
        client_id="gustav-web",
        redirect_uri="http://app.localhost:8100/auth/callback",
    )
    state_store = StateStore()
    monkeypatch.setenv("WEB_BASE", "http://app.localhost:8100")

    test_app = create_app_auth_only(oidc_config=cfg, state_store=state_store)
    async with httpx.AsyncClient(transport=ASGITransport(app=test_app), base_url="http://app.localhost:8100") as client:
        r = await client.get("/auth/register", follow_redirects=False)

    assert r.status_code == 302
    assert r.headers.get("Cache-Control") == "private, no-store"
    assert r.headers.get("Vary") == "HX-Request"

    loc = r.headers.get("Location")
    assert loc and "kc_action=register" in loc
    # sanity: should also include state param
    parsed = urlparse(loc)
    qs = parse_qs(parsed.query)
    assert qs.get("state", [None])[0]
