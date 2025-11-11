"""
Teaching API — Members default pagination limit is 10

Why:
    The members listing endpoint should return at most 10 entries when the
    client omits the `limit` parameter, to keep the UI compact by default.

BDD
- Given a course with more than 10 members
- When the owner calls GET /api/teaching/courses/{id}/members without `limit`
- Then the API returns exactly 10 items (ordered by join time asc).
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
from identity_access.stores import SessionStore  # type: ignore
from utils.db import require_db_or_skip as _require_db_or_skip


async def _client():
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test", headers={"Origin": "http://test"})


@pytest.mark.anyio
async def test_members_api_default_limit_is_10():
    _require_db_or_skip()
    # Fresh in-memory session store for isolation
    main.SESSION_STORE = SessionStore()

    # Arrange: teacher owner and a course with >10 members
    t = main.SESSION_STORE.create(sub="teacher-limit-10", name="Owner", roles=["teacher"])
    async with (await _client()) as client:
        client.cookies.set(main.SESSION_COOKIE_NAME, t.session_id)
        # Create course
        r = await client.post("/api/teaching/courses", json={"title": "Bio 9"})
        assert r.status_code == 201
        cid = r.json()["id"]
        # Add 15 members
        for i in range(15):
            sid = f"student-{i:02d}"
            resp = await client.post(f"/api/teaching/courses/{cid}/members", json={"student_sub": sid})
            assert resp.status_code in (200, 201, 204)

        # Act: list members with no explicit limit
        lst = await client.get(f"/api/teaching/courses/{cid}/members")
        assert lst.status_code == 200
        items = lst.json()

    # Assert: exactly 10 returned by default
    assert isinstance(items, list)
    assert len(items) == 10
