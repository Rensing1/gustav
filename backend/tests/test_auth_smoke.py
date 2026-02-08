"""
Minimal smoke test to ensure auth-only login redirect responds.

Uses the same async ASGI test path as the rest of the suite to avoid
sync TestClient deadlocks under newer anyio/httpx combinations.
"""

from pathlib import Path
import sys

import httpx
import pytest
from httpx import ASGITransport

# Import the auth-only app factory directly to avoid broader imports
REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
sys.path.insert(0, str(WEB_DIR))

from main import create_app_auth_only  # type: ignore


pytestmark = pytest.mark.anyio("asyncio")


@pytest.mark.anyio
async def test_auth_login_redirects():
    app = create_app_auth_only()
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/auth/login", follow_redirects=False)
    assert resp.status_code == 302
    assert "location" in resp.headers
