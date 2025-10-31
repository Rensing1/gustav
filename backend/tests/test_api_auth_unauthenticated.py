"""
API auth enforcement — ensure 401 JSON for unauthenticated /api/* requests.

Drives middleware behavior for unauthenticated access to protected API routes.
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


async def _client():
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test")


@pytest.mark.anyio
async def test_api_unauthenticated_returns_401_json():
    async with (await _client()) as client:
        # no cookie set → 401
        r1 = await client.get("/api/teaching/courses")
        assert r1.status_code == 401
        assert r1.headers.get("Cache-Control") == "private, no-store"
        assert r1.json().get("error") == "unauthenticated"

        r2 = await client.get("/api/users/search?q=ma&role=student")
        assert r2.status_code == 401
        assert r2.json().get("error") == "unauthenticated"
