"""
API Cache-Control for write endpoints (POST/PATCH).

Scenarios (RED):
- POST /api/teaching/units returns 201 with Cache-Control: private, no-store
- PATCH /api/teaching/units/{id} returns 200 with Cache-Control: private, no-store
"""

from __future__ import annotations

from pathlib import Path
import sys

import pytest
import httpx
from httpx import ASGITransport


pytestmark = pytest.mark.anyio("asyncio")


REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))
import main  # type: ignore  # noqa: E402
import routes.teaching as teaching  # type: ignore  # noqa: E402
from identity_access.stores import SessionStore  # type: ignore  # noqa: E402


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test")


@pytest.mark.anyio
async def test_create_unit_201_has_private_no_store():
    # Use in-memory repo to stay DB-independent
    teaching.set_repo(teaching._Repo())  # type: ignore[attr-defined]
    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-cache-write-1", name="Teach", roles=["teacher"])  # type: ignore

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        r = await c.post("/api/teaching/units", json={"title": "Cache-Harden"})

    assert r.status_code == 201
    cc = r.headers.get("Cache-Control", "")
    assert "private" in cc and "no-store" in cc


@pytest.mark.anyio
async def test_update_unit_200_has_private_no_store():
    teaching.set_repo(teaching._Repo())  # type: ignore[attr-defined]
    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-cache-write-2", name="Teach", roles=["teacher"])  # type: ignore

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        create = await c.post("/api/teaching/units", json={"title": "Alt"})
        uid = create.json()["id"]
        r = await c.patch(f"/api/teaching/units/{uid}", json={"title": "Neu"})

    assert r.status_code == 200
    cc = r.headers.get("Cache-Control", "")
    assert "private" in cc and "no-store" in cc
