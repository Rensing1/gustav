"""
SSR UI — Candidate filtering must use the full course roster.

BDD
- Given a course with more than 10 members
- And directory search returns a user already enrolled outside the first 10
- When the owner searches on /courses/{id}/members/search
- Then the enrolled user is not rendered as a candidate.
"""
from __future__ import annotations

from pathlib import Path
import sys

import httpx
from httpx import ASGITransport
import pytest

from utils.db import require_db_or_skip as _require_db_or_skip


pytestmark = pytest.mark.anyio("asyncio")

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))

import main  # type: ignore
from identity_access.stores import SessionStore  # type: ignore
from routes import users as users_routes  # type: ignore


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=ASGITransport(app=main.app),
        base_url="http://test",
        headers={"Origin": "http://test"},
    )


@pytest.mark.anyio
async def test_members_search_excludes_existing_member_outside_first_ten(monkeypatch: pytest.MonkeyPatch) -> None:
    _require_db_or_skip()
    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="teacher-filter-full", name="Owner", roles=["teacher"])

    def fake_search_users_by_name(*, role: str, q: str, limit: int) -> list[dict]:
        assert role == "student"
        assert len(q) >= 2
        return [
            {"sub": "stud-14", "name": "Outside Fourteen"},
            {"sub": "stud-new", "name": "Fresh Student"},
        ][:limit]

    monkeypatch.setattr(users_routes, "search_users_by_name", fake_search_users_by_name)

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        created = await c.post("/api/teaching/courses", json={"title": "Filter Full Roster"})
        assert created.status_code == 201, created.text
        course_id = str(created.json()["id"])

        for i in range(15):
            add = await c.post(
                f"/api/teaching/courses/{course_id}/members",
                json={"student_sub": f"stud-{i:02d}"},
            )
            assert add.status_code in (200, 201, 204), add.text

        resp = await c.get(f"/courses/{course_id}/members/search?q=stud")
        assert resp.status_code == 200
        html = resp.text

    assert "Outside Fourteen" not in html
    assert "Fresh Student" in html
