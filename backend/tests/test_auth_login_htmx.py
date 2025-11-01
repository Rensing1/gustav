"""
Auth HTMX flow guard: ensure /auth/login responds with HX-Redirect.

Regression test for the sidebar login action which issues HTMX requests.
"""

from __future__ import annotations

from pathlib import Path
import sys
from types import ModuleType
from urllib.parse import urlparse, parse_qs

import pytest
import httpx
from httpx import ASGITransport


REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))

# Build a minimal auth-only app to avoid DB dependencies in routes/learning.py
from fastapi import FastAPI  # noqa: E402
from routes.auth import auth_router  # type: ignore  # noqa: E402
from identity_access.stores import StateStore  # noqa: E402
from identity_access.oidc import OIDCConfig  # noqa: E402


def make_auth_only_app() -> FastAPI:
    app = FastAPI()
    app.include_router(auth_router)
    return app


def install_main_stub(cfg: OIDCConfig) -> ModuleType:
    """Install a stub 'main' module to satisfy routes.auth late import.

    Provides OIDC_CFG and STATE_STORE compatible with production main.py.
    """
    stub = ModuleType("main")
    stub.OIDC_CFG = cfg
    stub.STATE_STORE = StateStore()
    # Defaults used by routes.auth logout (not exercised here)
    stub.SESSION_COOKIE_NAME = "gustav_session"
    class _Settings:
        environment = "dev"
    stub.SETTINGS = _Settings()
    sys.modules["main"] = stub
    return stub


pytestmark = pytest.mark.anyio("asyncio")


@pytest.mark.anyio
async def test_login_htmx_sets_hx_redirect_and_keeps_state(monkeypatch: pytest.MonkeyPatch):
    # Arrange: deterministic OIDC config and clean state store
    cfg = OIDCConfig(
        base_url="http://kc.localhost:8080",
        realm="gustav",
        client_id="gustav-web",
        redirect_uri="http://app.localhost:8100/auth/callback",
    )
    stub = install_main_stub(cfg)
    monkeypatch.setenv("WEB_BASE", "http://app.localhost:8100")

    # Ensure the store starts empty for assertion clarity
    stub.STATE_STORE._data.clear()  # type: ignore[attr-defined]

    test_app = make_auth_only_app()
    async with httpx.AsyncClient(
        transport=ASGITransport(app=test_app),
        base_url="http://app.localhost:8100",
    ) as client:
        response = await client.get(
            "/auth/login",
            headers={
                "HX-Request": "true",
                "Host": "app.localhost:8100",
            },
            follow_redirects=False,
        )

    # Expect HTMX-compatible response instead of a raw 302
    assert response.status_code == 204
    redirect_target = response.headers.get("HX-Redirect")
    assert redirect_target, "HX-Redirect header missing"

    parsed = urlparse(redirect_target)
    assert parsed.scheme in {"http", "https"}
    qs = parse_qs(parsed.query)
    state_param = qs.get("state", [None])[0]
    assert state_param, "Authorization URL must contain state parameter"

    # State must remain in the store until the callback consumes it
    assert state_param in stub.STATE_STORE._data  # type: ignore[attr-defined]


@pytest.mark.anyio
async def test_register_htmx_sets_hx_redirect(monkeypatch: pytest.MonkeyPatch):
    # Arrange: deterministic OIDC config
    cfg = OIDCConfig(
        base_url="http://kc.localhost:8080",
        realm="gustav",
        client_id="gustav-web",
        redirect_uri="http://app.localhost:8100/auth/callback",
    )
    install_main_stub(cfg)
    monkeypatch.setenv("WEB_BASE", "http://app.localhost:8100")

    test_app = make_auth_only_app()
    async with httpx.AsyncClient(
        transport=ASGITransport(app=test_app),
        base_url="http://app.localhost:8100",
    ) as client:
        r = await client.get(
            "/auth/register",
            headers={"HX-Request": "true", "Host": "app.localhost:8100"},
            follow_redirects=False,
        )

    assert r.status_code == 204
    assert r.headers.get("HX-Redirect")
    assert r.headers.get("Vary") == "HX-Request"


@pytest.mark.anyio
async def test_login_dynamic_redirect_host_guard(monkeypatch: pytest.MonkeyPatch):
    # Arrange: allowed base is app.localhost:8100
    cfg = OIDCConfig(
        base_url="http://kc.localhost:8080",
        realm="gustav",
        client_id="gustav-web",
        redirect_uri="http://app.localhost:8100/auth/callback",
    )
    install_main_stub(cfg)
    monkeypatch.setenv("WEB_BASE", "http://app.localhost:8100")

    test_app = make_auth_only_app()
    # Case 1: matching host -> dynamic redirect_uri is used
    async with httpx.AsyncClient(
        transport=ASGITransport(app=test_app),
        base_url="http://app.localhost:8100",
    ) as client:
        r1 = await client.get("/auth/login", headers={"HX-Request": "true"}, follow_redirects=False)
    assert r1.status_code == 204
    auth_url_1 = r1.headers["HX-Redirect"]
    assert "redirect_uri=http%3A%2F%2Fapp.localhost%3A8100%2Fauth%2Fcallback" in auth_url_1

    # Case 2: different host -> fallback to configured redirect_uri
    async with httpx.AsyncClient(
        transport=ASGITransport(app=test_app),
        base_url="http://app.localhost:9999",
    ) as client:
        r2 = await client.get("/auth/login", headers={"HX-Request": "true"}, follow_redirects=False)
    assert r2.status_code == 204
    auth_url_2 = r2.headers["HX-Redirect"]
    # Fallback must equal the configured redirect_uri, not the incoming host
    assert "redirect_uri=http%3A%2F%2Fapp.localhost%3A8100%2Fauth%2Fcallback" in auth_url_2
