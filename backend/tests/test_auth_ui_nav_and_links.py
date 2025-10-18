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
async def test_sidebar_logout_link_to_auth_logout():
    """Authenticated GET / renders sidebar with logout control linking to /auth/logout."""
    # Create a fake authenticated session in the server store
    sess = main.SESSION_STORE.create(email="user@example.com", roles=["student"], email_verified=True)
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set("gustav_session", sess.session_id)
        r = await client.get("/", follow_redirects=False)

    assert r.status_code == 200
    html = r.text
    assert "sidebar-logout" in html, "Logout control missing in sidebar"
    assert 'href="/auth/logout"' in html, "Logout should link to /auth/logout"
    assert 'hx-' not in html or 'hx-post="/auth/logout"' not in html, "Logout should be a normal link (no HTMX)"
    # Sidebar should show email and German role
    assert "user@example.com" in html
    assert "Schüler" in html


# Direct-Grant SSR pages were removed; the remaining GET endpoints redirect to Keycloak.
@pytest.mark.anyio
async def test_auth_endpoints_redirect_to_idp():
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        for path in ["/auth/login", "/auth/register", "/auth/forgot"]:
            r = await client.get(path, follow_redirects=False)
            assert r.status_code in (302, 303)
            assert "location" in r.headers
