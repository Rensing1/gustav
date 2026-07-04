"""Auth: /auth/password redirect flow tests."""

from __future__ import annotations

import importlib
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from httpx import ASGITransport


main = importlib.import_module("backend.web.main")
from backend.identity_access.oidc import OIDCConfig
from backend.identity_access.stores import StateStore


pytestmark = pytest.mark.anyio("asyncio")


def _install_auth_runtime(monkeypatch: pytest.MonkeyPatch, *, cfg: OIDCConfig, state_store: StateStore) -> None:
    monkeypatch.setattr(main.RUNTIME, "oidc_config", cfg)
    monkeypatch.setattr(main.RUNTIME, "state_store", state_store)


@pytest.mark.anyio
async def test_password_redirect_starts_update_password_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    state_store = StateStore()
    cfg = OIDCConfig(
        base_url="http://kc.example:8080",
        realm="gustav",
        client_id="gustav-web",
        redirect_uri="http://app.localhost:8100/auth/callback",
    )
    _install_auth_runtime(monkeypatch, cfg=cfg, state_store=state_store)

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.get("/auth/password", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers.get("Cache-Control") == "private, no-store"
    location = response.headers.get("Location", "")
    query = parse_qs(urlparse(location).query)
    assert query.get("kc_action") == ["UPDATE_PASSWORD"]


@pytest.mark.anyio
async def test_password_redirect_uses_app_runtime_state_store_and_oidc_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_store = StateStore()
    runtime_cfg = OIDCConfig(
        base_url="http://runtime-kc:8080",
        realm="runtime-school",
        client_id="runtime-client",
        redirect_uri="https://runtime-app.example/auth/callback",
        public_base_url="https://runtime-kc.example",
    )
    monkeypatch.setattr(main.RUNTIME, "state_store", runtime_store)
    monkeypatch.setattr(main.RUNTIME, "oidc_config", runtime_cfg)

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.get("/auth/password", follow_redirects=False)

    assert response.status_code == 302
    location = response.headers.get("Location", "")
    parsed = urlparse(location)
    assert f"{parsed.scheme}://{parsed.netloc}" == "https://runtime-kc.example"
    assert parsed.path.startswith("/realms/runtime-school/")
    query = parse_qs(parsed.query)
    state_values = query.get("state") or []
    assert len(state_values) == 1
    assert state_values[0] in getattr(runtime_store, "_data", {})
    assert query.get("client_id") == ["runtime-client"]
    assert query.get("kc_action") == ["UPDATE_PASSWORD"]
