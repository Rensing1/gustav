"""
Auth: /auth/register dynamic redirect_uri tests (mirror of login behavior)

Prüft, dass die Redirect-URI dynamisch den aktuellen Host übernimmt, sofern
dieser der Whitelist (WEB_BASE bzw. OIDC redirect_uri) entspricht, und
ansonsten auf die konfigurierte redirect_uri zurückfällt.
"""

from __future__ import annotations

from pathlib import Path
import sys

import pytest
import httpx
from httpx import ASGITransport


REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
sys.path.insert(0, str(WEB_DIR))
import main  # type: ignore
from identity_access.oidc import OIDCConfig


pytestmark = pytest.mark.anyio("asyncio")


@pytest.mark.anyio
async def test_register_dynamic_redirect_respects_whitelist(monkeypatch: pytest.MonkeyPatch):
    from urllib.parse import urlparse, parse_qs

    test_cfg = OIDCConfig(
        base_url="http://kc.example:8080",
        realm="gustav",
        client_id="gustav-web",
        redirect_uri="http://app.localhost:8100/auth/callback",
    )
    monkeypatch.setattr(main, "OIDC_CFG", test_cfg)
    monkeypatch.setenv("WEB_BASE", "http://app.localhost:8100")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://app.localhost:8100") as client:
        resp = await client.get("/auth/register", follow_redirects=False, headers={"Host": "app.localhost:8100"})

    assert resp.status_code == 302
    loc = resp.headers.get("location", "")
    u = urlparse(loc)
    qs = parse_qs(u.query)
    assert qs.get("redirect_uri") == ["http://app.localhost:8100/auth/callback"]


@pytest.mark.anyio
async def test_register_dynamic_redirect_falls_back_on_mismatch(monkeypatch: pytest.MonkeyPatch):
    from urllib.parse import urlparse, parse_qs

    static_redirect = "http://app.localhost:8100/auth/callback"
    test_cfg = OIDCConfig(
        base_url="http://kc.example:8080",
        realm="gustav",
        client_id="gustav-web",
        redirect_uri=static_redirect,
    )
    monkeypatch.setattr(main, "OIDC_CFG", test_cfg)
    monkeypatch.setenv("WEB_BASE", "http://app.localhost:8100")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://evil.localhost:8100") as client:
        resp = await client.get("/auth/register", follow_redirects=False, headers={"Host": "evil.localhost:8100"})

    assert resp.status_code == 302
    loc = resp.headers.get("location", "")
    u = urlparse(loc)
    qs = parse_qs(u.query)
    assert qs.get("redirect_uri") == [static_redirect]

