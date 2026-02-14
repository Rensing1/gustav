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


@pytest.mark.anyio
async def test_members_search_reuses_member_sub_cache_within_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="teacher-filter-cache", name="Owner", roles=["teacher"])

    existing_cache = getattr(main, "_MEMBER_SUBS_CACHE", None)
    if isinstance(existing_cache, dict):
        existing_cache.clear()

    calls = {"roster_fetch": 0}

    async def fake_fetch_members(course_id: str, sid: str | None) -> list[dict]:
        calls["roster_fetch"] += 1
        return [{"sub": "stud-14", "name": "Outside Fourteen"}]

    def fake_search_users_by_name(*, role: str, q: str, limit: int) -> list[dict]:
        assert role == "student"
        return [
            {"sub": "stud-14", "name": "Outside Fourteen"},
            {"sub": "stud-new", "name": "Fresh Student"},
        ][:limit]

    monkeypatch.setattr(main, "_fetch_all_course_members_for_ssr", fake_fetch_members)
    monkeypatch.setattr(main, "_member_subs_cache_ttl_seconds", lambda: 60.0, raising=False)
    monkeypatch.setattr(users_routes, "search_users_by_name", fake_search_users_by_name)

    course_id = "cache-course-1"
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        r1 = await c.get(f"/courses/{course_id}/members/search?q=st")
        r2 = await c.get(f"/courses/{course_id}/members/search?q=st")
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert "Fresh Student" in r1.text
        assert "Fresh Student" in r2.text

    assert calls["roster_fetch"] == 1


@pytest.mark.anyio
async def test_fetch_all_members_fails_closed_when_a_page_returns_non_200(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Resp:
        def __init__(self, status_code: int, payload):
            self.status_code = status_code
            self._payload = payload

        def json(self):
            return self._payload

    class _StubClient:
        def __init__(self) -> None:
            class _Cookies:
                def set(self, _name: str, _value: str) -> None:
                    return None

            self.cookies = _Cookies()

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, _url: str, params: dict | None = None):
            p = params or {}
            if int(p.get("offset", 0)) == 0:
                # Full first page forces another paging request.
                payload = [{"sub": f"stud-{i:02d}", "name": f"Stud {i:02d}"} for i in range(50)]
                return _Resp(200, payload)
            return _Resp(503, {"error": "upstream_unavailable"})

    async def fake_apply(rows: list[dict]) -> list[dict]:
        return rows

    monkeypatch.setattr(main, "_internal_api_client", lambda: _StubClient())
    monkeypatch.setattr(main, "_apply_member_login_labels", fake_apply)

    out = await main._fetch_all_course_members_for_ssr("course-fail-closed", "sid-1")
    assert out == []
