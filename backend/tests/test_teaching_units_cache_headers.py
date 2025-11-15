"""
Teaching API cache headers — ensure privacy on list endpoints.

Checks that 200 responses include "Cache-Control: private, no-store" for:
- GET /api/teaching/units
- GET /api/teaching/units/{unit_id}/sections
"""

from __future__ import annotations

import httpx
from httpx import ASGITransport
from pathlib import Path
import sys
import pytest


pytestmark = pytest.mark.anyio("asyncio")

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))
import main  # type: ignore
from identity_access.stores import SessionStore  # type: ignore


async def _client():
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test", headers={"Origin": "http://test"})


@pytest.mark.anyio
async def test_units_list_sets_private_no_store():
    # Arrange: ensure memory session store
    if not isinstance(main.SESSION_STORE, SessionStore):  # pragma: no cover - defensive
        main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-cache-1", name="Teach", roles=["teacher"])  # type: ignore
    # Act
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        r = await c.get("/api/teaching/units", params={"limit": 5, "offset": 0})
    # Assert
    assert r.status_code == 200
    cc = r.headers.get("Cache-Control", "")
    assert "no-store" in cc and "private" in cc


@pytest.mark.anyio
async def test_sections_list_sets_private_no_store():
    if not isinstance(main.SESSION_STORE, SessionStore):  # pragma: no cover - defensive
        main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-cache-2", name="Teach", roles=["teacher"])  # type: ignore
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        # Create a unit to get a UUID
        r_unit = await c.post("/api/teaching/units", json={"title": "Cache-Test-Unit"})
        assert r_unit.status_code == 201
        unit_id = r_unit.json()["id"]
        r = await c.get(f"/api/teaching/units/{unit_id}/sections")
    assert r.status_code == 200
    cc = r.headers.get("Cache-Control", "")
    assert "no-store" in cc and "private" in cc
