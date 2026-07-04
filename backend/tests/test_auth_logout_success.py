"""
Smoke test for the logout success page.

Checks that GET /auth/logout/success returns 200 HTML and includes a link
back to /auth/login. Keeps the test minimal and contract-focused.
"""
from __future__ import annotations

import importlib

import pytest
import httpx
from httpx import ASGITransport


pytestmark = pytest.mark.anyio("asyncio")


main = importlib.import_module("backend.web.main")


@pytest.mark.anyio
async def test_logout_success_renders_and_links_to_login():
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        resp = await client.get("/auth/logout/success")
    assert resp.status_code == 200
    body = resp.text
    assert "href=\"/auth/login\"" in body, "Page should link back to /auth/login"
