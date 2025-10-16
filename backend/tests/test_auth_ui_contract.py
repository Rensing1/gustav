"""
Auth UI contract tests (RED phase for Phase 1 UI forms)

These tests validate the new HTML form endpoints for login/register/forgot
as described in api/openapi.yml and docs/plan/auth_ui.md. In Phase 1, the
HTML path is feature-flagged and expected in DEV/CI. We monkeypatch the flag
so behavior is deterministic for tests. External IdP calls must be mocked
in later GREEN steps; here we only assert routing, CSRF handling, and shapes.
"""

import pytest
import httpx
from httpx import ASGITransport
from pathlib import Path
import sys

# Ensure we can import the FastAPI app
REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
sys.path.insert(0, str(WEB_DIR))
import main  # type: ignore

pytestmark = pytest.mark.anyio("asyncio")


async def _client():
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test")


@pytest.mark.anyio
async def test_login_get_returns_html_with_csrf_when_flag_enabled(monkeypatch: pytest.MonkeyPatch):
    """GET /auth/login should return 200 HTML + CSRF cookie when UI flag is enabled."""
    monkeypatch.setattr(main, "AUTH_USE_DIRECT_GRANT", True, raising=False)

    async with (await _client()) as client:
        resp = await client.get("/auth/login", follow_redirects=False)

    assert resp.status_code == 200, "Expected HTML form when flag is enabled"
    ct = resp.headers.get("content-type", "")
    assert ct.startswith("text/html"), f"Unexpected content-type: {ct}"
    set_cookie = resp.headers.get("set-cookie", "")
    assert "gustav_csrf=" in set_cookie, "CSRF cookie not set"
    body = resp.text
    assert "<form" in body and "name=\"csrf_token\"" in body


@pytest.mark.anyio
async def test_login_post_requires_csrf(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(main, "AUTH_USE_DIRECT_GRANT", True, raising=False)
    async with (await _client()) as client:
        # Missing csrf_token -> 403
        resp = await client.post("/auth/login", data={"email": "a@b.de", "password": "x"}, follow_redirects=False)
    assert resp.status_code == 403


@pytest.mark.anyio
async def test_register_post_requires_csrf(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(main, "AUTH_USE_DIRECT_GRANT", True, raising=False)
    async with (await _client()) as client:
        resp = await client.post(
            "/auth/register",
            data={"email": "new@example.com", "password": "Passw0rd!"},
            follow_redirects=False,
        )
    assert resp.status_code == 403


@pytest.mark.anyio
async def test_forgot_post_requires_csrf(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(main, "AUTH_USE_DIRECT_GRANT", True, raising=False)
    async with (await _client()) as client:
        resp = await client.post(
            "/auth/forgot",
            data={"email": "someone@example.com"},
            follow_redirects=False,
        )
    assert resp.status_code == 403

