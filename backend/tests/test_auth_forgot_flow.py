"""
Auth: /auth/forgot password reset flow tests.

Why:
    Ensure that the /auth/forgot endpoint:
    - Always returns a 302 redirect with Cache-Control: private, no-store.
    - Builds the Keycloak reset URL from the configured base/realm.
    - Forwards login_hint as a query parameter without validating existence.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse, parse_qs
import sys

import pytest
import httpx
from httpx import ASGITransport


REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))
import main  # type: ignore
from identity_access.oidc import OIDCConfig  # type: ignore


pytestmark = pytest.mark.anyio("asyncio")


@pytest.mark.anyio
async def test_forgot_redirect_has_cache_header_and_location(monkeypatch: pytest.MonkeyPatch):
    """Basic contract: 302 + Cache-Control: private, no-store + Location."""
    cfg = OIDCConfig(
        base_url="http://kc.example:8080",
        realm="gustav",
        client_id="gustav-web",
        redirect_uri="http://app.localhost:8100/auth/callback",
    )
    monkeypatch.setattr(main, "OIDC_CFG", cfg, raising=False)

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        resp = await client.get("/auth/forgot", follow_redirects=False)

    assert resp.status_code == 302
    assert resp.headers.get("Cache-Control") == "private, no-store"
    loc = resp.headers.get("Location")
    assert loc
    url = urlparse(loc)
    assert url.path.endswith("/realms/gustav/login-actions/reset-credentials")


@pytest.mark.anyio
async def test_forgot_redirect_forwards_login_hint(monkeypatch: pytest.MonkeyPatch):
    """login_hint should be forwarded as-is for Keycloak to handle."""
    cfg = OIDCConfig(
        base_url="http://kc.example:8080",
        realm="school",
        client_id="gustav-web",
        redirect_uri="http://app.localhost:8100/auth/callback",
    )
    monkeypatch.setattr(main, "OIDC_CFG", cfg, raising=False)

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        resp = await client.get("/auth/forgot?login_hint=student%40example.com", follow_redirects=False)

    assert resp.status_code == 302
    loc = resp.headers.get("Location", "")
    url = urlparse(loc)
    assert url.path.endswith("/realms/school/login-actions/reset-credentials")
    qs = parse_qs(url.query)
    assert qs.get("login_hint") == ["student@example.com"]

