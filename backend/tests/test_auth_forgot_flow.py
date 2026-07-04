"""
Auth: /auth/forgot password reset flow tests.

Why:
    Ensure that the /auth/forgot endpoint:
    - Always returns a 302 redirect with Cache-Control: private, no-store.
    - Builds the Keycloak reset URL from the configured base/realm.
    - Forwards login_hint as a query parameter without validating existence.
"""

from __future__ import annotations

import importlib
from urllib.parse import urlparse, parse_qs

import pytest
import httpx
from httpx import ASGITransport


main = importlib.import_module("backend.web.main")
from backend.identity_access.oidc import OIDCConfig


pytestmark = pytest.mark.anyio("asyncio")


def _install_oidc_config(monkeypatch: pytest.MonkeyPatch, cfg: OIDCConfig) -> None:
    monkeypatch.setattr(main.RUNTIME, "oidc_config", cfg)


@pytest.mark.anyio
async def test_forgot_redirect_has_cache_header_and_location(monkeypatch: pytest.MonkeyPatch):
    """Basic contract: 302 + Cache-Control: private, no-store + Location."""
    cfg = OIDCConfig(
        base_url="http://kc.example:8080",
        realm="gustav",
        client_id="gustav-web",
        redirect_uri="http://app.localhost:8100/auth/callback",
    )
    _install_oidc_config(monkeypatch, cfg)

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
    _install_oidc_config(monkeypatch, cfg)

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        resp = await client.get("/auth/forgot?login_hint=student%40example.com", follow_redirects=False)

    assert resp.status_code == 302
    loc = resp.headers.get("Location", "")
    url = urlparse(loc)
    assert url.path.endswith("/realms/school/login-actions/reset-credentials")
    qs = parse_qs(url.query)
    assert qs.get("login_hint") == ["student@example.com"]


@pytest.mark.anyio
async def test_forgot_redirect_uses_app_runtime_oidc_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_cfg = OIDCConfig(
        base_url="http://runtime-kc:8080",
        realm="runtime-school",
        client_id="gustav-web",
        redirect_uri="http://runtime-app.localhost:8100/auth/callback",
        public_base_url="https://runtime-kc.example",
    )
    monkeypatch.setattr(main.RUNTIME, "oidc_config", runtime_cfg)

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        resp = await client.get("/auth/forgot", follow_redirects=False)

    assert resp.status_code == 302
    loc = resp.headers.get("Location", "")
    url = urlparse(loc)
    assert f"{url.scheme}://{url.netloc}" == "https://runtime-kc.example"
    assert url.path.endswith("/realms/runtime-school/login-actions/reset-credentials")
