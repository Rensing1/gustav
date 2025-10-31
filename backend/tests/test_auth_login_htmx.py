"""
Auth HTMX flow guard: ensure /auth/login responds with HX-Redirect.

Regression test for the sidebar login action which issues HTMX requests.
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

import main  # type: ignore  # noqa: E402
from identity_access.oidc import OIDCConfig  # noqa: E402


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
    monkeypatch.setattr(main, "OIDC_CFG", cfg)
    monkeypatch.setenv("WEB_BASE", "http://app.localhost:8100")

    # Ensure the store starts empty for assertion clarity
    main.STATE_STORE._data.clear()  # type: ignore[attr-defined]

    async with httpx.AsyncClient(
        transport=ASGITransport(app=main.app),
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
    assert state_param in main.STATE_STORE._data  # type: ignore[attr-defined]
