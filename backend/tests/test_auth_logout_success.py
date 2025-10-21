"""
Smoke test for the logout success page.

Checks that GET /auth/logout/success returns 200 HTML and includes a link
back to /auth/login. Keeps the test minimal and contract-focused.
"""
from __future__ import annotations

import pytest
import httpx
from httpx import ASGITransport
from pathlib import Path
import sys


pytestmark = pytest.mark.anyio("asyncio")


REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))
import main  # type: ignore


@pytest.mark.anyio
async def test_logout_success_renders_and_links_to_login():
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        resp = await client.get("/auth/logout/success")
    assert resp.status_code == 200
    body = resp.text
    assert "href=\"/auth/login\"" in body, "Page should link back to /auth/login"
