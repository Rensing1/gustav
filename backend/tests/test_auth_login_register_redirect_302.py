"""
Non-HTMX Auth redirects — ensure 302 Location and cache headers.

Covers /auth/login and /auth/register without HX-Request, verifying:
- 302 status
- Location contains required params (state; kc_action=register)
- Security headers: Cache-Control: private, no-store; Vary: HX-Request
"""

from __future__ import annotations

from pathlib import Path
import sys
from urllib.parse import urlparse, parse_qs

import pytest
import httpx
from httpx import ASGITransport


REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))

from fastapi import FastAPI  # noqa: E402
from routes.auth import auth_router  # type: ignore  # noqa: E402
from identity_access.stores import StateStore  # noqa: E402
from identity_access.oidc import OIDCConfig  # noqa: E402


def make_auth_only_app() -> FastAPI:
    app = FastAPI()
    app.include_router(auth_router)
    return app


def install_main_stub(cfg: OIDCConfig, monkeypatch: pytest.MonkeyPatch):
    import types
    stub = types.ModuleType("main")
    stub.OIDC_CFG = cfg
    stub.STATE_STORE = StateStore()
    stub.SESSION_COOKIE_NAME = "gustav_session"
    class _Settings:
        environment = "dev"
    stub.SETTINGS = _Settings()
    monkeypatch.setitem(sys.modules, "main", stub)
    return stub


pytestmark = pytest.mark.anyio("asyncio")


@pytest.mark.anyio
async def test_login_redirect_302_has_location_and_cache_headers(monkeypatch: pytest.MonkeyPatch):
    cfg = OIDCConfig(
        base_url="http://kc.localhost:8080",
        realm="gustav",
        client_id="gustav-web",
        redirect_uri="http://app.localhost:8100/auth/callback",
    )
    install_main_stub(cfg, monkeypatch)
    monkeypatch.setenv("WEB_BASE", "http://app.localhost:8100")

    test_app = make_auth_only_app()
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
    install_main_stub(cfg, monkeypatch)
    monkeypatch.setenv("WEB_BASE", "http://app.localhost:8100")

    test_app = make_auth_only_app()
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
