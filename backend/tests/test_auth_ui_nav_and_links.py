"""
UI navigation and auth-page links tests (TDD: RED first)

Goals:
- Ensure the sidebar logout button posts to the correct route `/auth/logout`
  and performs client-side redirect to `/` via HTMX attribute.
- Ensure auth pages provide helpful links between flows:
  - Login page links to Register and Forgot Password pages
  - Register page links back to Login
"""

import sys
from pathlib import Path

import pytest
import httpx
from httpx import ASGITransport

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
sys.path.insert(0, str(WEB_DIR))
import main  # type: ignore


pytestmark = pytest.mark.anyio("asyncio")


@pytest.mark.anyio
async def test_sidebar_logout_posts_to_auth_logout():
    """GET / should render navigation with a logout control posting to /auth/logout."""
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        r = await client.get("/", follow_redirects=False)

    assert r.status_code == 200
    html = r.text
    assert "sidebar-logout" in html, "Logout control missing in sidebar"
    assert 'hx-post="/auth/logout"' in html, "Logout should post to /auth/logout"
    assert 'hx-redirect="/"' in html, "Logout should redirect to / after success"


@pytest.mark.anyio
async def test_login_page_has_links_to_register_and_forgot(monkeypatch: pytest.MonkeyPatch):
    """GET /auth/login should show helpful links to /auth/register and /auth/forgot when UI flag is on."""
    monkeypatch.setattr(main, "AUTH_USE_DIRECT_GRANT", True, raising=False)
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        r = await client.get("/auth/login", follow_redirects=False)

    assert r.status_code == 200
    html = r.text
    assert "/auth/register" in html, "Expected link to registration"
    assert "/auth/forgot" in html, "Expected link to forgot password"


@pytest.mark.anyio
async def test_register_page_links_back_to_login(monkeypatch: pytest.MonkeyPatch):
    """GET /auth/register should include a link back to /auth/login for convenience."""
    monkeypatch.setattr(main, "AUTH_USE_DIRECT_GRANT", True, raising=False)
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        r = await client.get("/auth/register", follow_redirects=False)

    assert r.status_code == 200
    html = r.text
    assert "/auth/login" in html, "Expected link back to login"

