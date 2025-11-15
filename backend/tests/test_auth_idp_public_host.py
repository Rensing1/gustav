"""
Auth login should use the public Keycloak base URL host when present.

We validate that /auth/login builds a redirect with the netloc from
KC_PUBLIC_BASE_URL (browser-facing), independent of the internal KC_BASE_URL.
"""
from __future__ import annotations

import pytest
import httpx
from httpx import ASGITransport
from urllib.parse import urlparse


pytestmark = pytest.mark.anyio("asyncio")


async def test_login_redirect_uses_public_kc_host(monkeypatch: pytest.MonkeyPatch):
    # Import lazily to apply monkeypatches after module import in tests
    import backend.web.main as main  # type: ignore

    # Configure OIDC client directly with distinct internal/public bases
    from identity_access.oidc import OIDCConfig, OIDCClient
    cfg = OIDCConfig(base_url="http://keycloak:8080", realm="gustav", client_id="gustav-web", redirect_uri="https://app.localhost/auth/callback", public_base_url="https://id.example")
    monkeypatch.setattr(main, "OIDC_CFG", cfg, raising=False)
    monkeypatch.setattr(main, "OIDC", OIDCClient(cfg), raising=False)

    # Use the existing app with updated OIDC globals
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        resp = await client.get("/auth/login", follow_redirects=False)

    assert resp.status_code in (302, 303)
    loc = resp.headers.get("location", "")
    assert loc, "Location header missing"
    netloc = urlparse(loc).netloc
    assert netloc == "id.example"
