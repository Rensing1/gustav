"""
UI navigation and auth-page links tests (TDD: RED first)

Goals:
- Ensure the sidebar logout button posts to the correct route `/auth/logout`
  and performs client-side redirect to `/` via HTMX attribute.
- Ensure auth pages provide helpful links between flows:
  - Login page links to Register and Forgot Password pages
  - Register page links back to Login
"""

import importlib

import pytest
import httpx
from httpx import ASGITransport

main = importlib.import_module("backend.web.main")
pytestmark = pytest.mark.anyio("asyncio")


# Direct-Grant SSR pages were removed; the remaining GET endpoints redirect to Keycloak.
@pytest.mark.anyio
async def test_auth_endpoints_redirect_to_idp():
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        for path in ["/auth/login", "/auth/register", "/auth/forgot"]:
            r = await client.get(path, follow_redirects=False)
            assert r.status_code in (302, 303)
            assert "location" in r.headers
