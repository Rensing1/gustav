"""
SSR UI — Members search must query all students via /api/users/search

Bugfix regression test:
    Previously, the UI filtered only the first page from /api/users/list.
    This test ensures that typing a query triggers the search endpoint so that
    students outside the first page are discoverable.

BDD
- Given a course owner and an existing member (to verify exclusion)
- And the directory list first page does NOT include the target student
- And the search endpoint DOES return the target student for the given query
- When the owner types the query on the members page
- Then the candidate list contains the target student and excludes the existing member.
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
from routes import users as users_routes  # type: ignore
from utils.db import require_db_or_skip as _require_db_or_skip


async def _client():
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test", headers={"Origin": "http://test"})


@pytest.mark.anyio
async def test_members_search_queries_full_directory(monkeypatch: pytest.MonkeyPatch):
    _require_db_or_skip()
    # Reset session store for isolation
    main.SESSION_STORE = SessionStore()
    # Seed teacher + course + one existing member (to be excluded from candidates)
    t = main.SESSION_STORE.create(sub="teacher-search-global", name="Owner", roles=["teacher"])
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, t.session_id)
        r = await c.post("/api/teaching/courses", json={"title": "Chemie 10"})
        assert r.status_code == 201
        cid = r.json()["id"]
        add = await c.post(f"/api/teaching/courses/{cid}/members", json={"student_sub": "student-1"})
        assert add.status_code in (200, 201, 204)

        # Prepare directory behavior:
        # - list_users_by_role returns a page without our target student (simulates paging)
        # - search_users_by_name returns our target student when q contains 'Zelda'
        def fake_list_users_by_role(*, role: str, limit: int, offset: int) -> list[dict]:
            assert role == "student"
            return [
                {"sub": "student-1", "name": "Max Musterschüler"},
                {"sub": "student-2", "name": "Erika Mustermann"},
            ]  # target not present in list page

        def fake_search_users_by_name(*, role: str, q: str, limit: int) -> list[dict]:
            assert role == "student"
            if "zelda" in (q or "").lower():
                return [{"sub": "student-zelda-99", "name": "Zelda Zed"}]
            return []

        monkeypatch.setattr(users_routes, "list_users_by_role", fake_list_users_by_role)
        monkeypatch.setattr(users_routes, "search_users_by_name", fake_search_users_by_name)

        # Act: search with q='Zelda'
        resp = await c.get(f"/courses/{cid}/members/search?q=Zelda")
        assert resp.status_code == 200
        html = resp.text

    # Assert: existing member excluded; target from search endpoint included
    assert "Max Musterschüler" not in html
    assert "Zelda Zed" in html
