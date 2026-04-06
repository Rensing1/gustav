"""Auth: /auth/password redirect flow tests."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs, urlparse
import sys

import httpx
import pytest
from httpx import ASGITransport


REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))

import main  # type: ignore
from identity_access.oidc import OIDCConfig  # type: ignore


pytestmark = pytest.mark.anyio("asyncio")


@pytest.mark.anyio
async def test_password_redirect_starts_update_password_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = OIDCConfig(
        base_url="http://kc.example:8080",
        realm="gustav",
        client_id="gustav-web",
        redirect_uri="http://app.localhost:8100/auth/callback",
    )
    monkeypatch.setattr(main, "OIDC_CFG", cfg, raising=False)

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.get("/auth/password", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers.get("Cache-Control") == "private, no-store"
    location = response.headers.get("Location", "")
    query = parse_qs(urlparse(location).query)
    assert query.get("kc_action") == ["UPDATE_PASSWORD"]

