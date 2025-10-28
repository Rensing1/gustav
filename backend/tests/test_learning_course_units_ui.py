"""
SSR (Student) — Course page lists units with links to unit detail page.

Validates that students can navigate from a course detail page at
`/learning/courses/{course_id}` to the unit content page at
`/learning/courses/{course_id}/units/{unit_id}`. Ensures link presence and
private, no-store cache headers.
"""
from __future__ import annotations

import pytest
import httpx
from httpx import ASGITransport

from utils.db import require_db_or_skip as _require_db_or_skip

import main  # type: ignore  # noqa: E402
from identity_access.stores import SessionStore  # type: ignore  # noqa: E402

pytestmark = pytest.mark.anyio("asyncio")


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test")


async def _create_course(client: httpx.AsyncClient, title: str = "Mathe") -> str:
    r = await client.post("/api/teaching/courses", json={"title": title})
    assert r.status_code == 201
    return r.json()["id"]


async def _create_unit(client: httpx.AsyncClient, title: str) -> dict:
    r = await client.post("/api/teaching/units", json={"title": title})
    assert r.status_code == 201
    return r.json()


async def _attach_unit(client: httpx.AsyncClient, course_id: str, unit_id: str) -> dict:
    r = await client.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": unit_id})
    assert r.status_code == 201
    return r.json()


async def _add_member(client: httpx.AsyncClient, course_id: str, student_sub: str) -> None:
    r = await client.post(f"/api/teaching/courses/{course_id}/members", json={"student_sub": student_sub})
    assert r.status_code in (201, 204)


@pytest.mark.anyio
async def test_course_units_list_contains_links_to_unit_detail():
    _require_db_or_skip()
    # Ensure DB-backed repos for the Learning routes
    import routes.learning as learning  # noqa: E402
    try:
        from backend.learning.repo_db import DBLearningRepo  # type: ignore
        assert isinstance(learning.REPO, DBLearningRepo)
    except Exception:
        pytest.skip("DB-backed repo required")

    # Setup sessions
    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-course-unit-link", name="Lehrkraft", roles=["teacher"])
    student = main.SESSION_STORE.create(sub="s-course-unit-link", name="Schüler", roles=["student"])

    async with (await _client()) as c:
        # Create course and unit, attach, and add student member
        c.cookies.set("gustav_session", teacher.session_id)
        course_id = await _create_course(c, "Kurs Links")
        unit = await _create_unit(c, "Unit Verlinkung")
        await _attach_unit(c, course_id, unit["id"])
        await _add_member(c, course_id, student.sub)

        # Student opens the course detail page
        c.cookies.set("gustav_session", student.session_id)
        r = await c.get(f"/learning/courses/{course_id}")
        assert r.status_code == 200
        assert r.headers.get("Cache-Control") == "private, no-store"

        html = r.text
        # Expect a link to the unit detail page
        expected_href = f"/learning/courses/{course_id}/units/{unit['id']}"
        assert expected_href in html

        # Follow the unit link and expect the unit sections page
        r2 = await c.get(expected_href)
        assert r2.status_code == 200
        assert r2.headers.get("Cache-Control") == "private, no-store"

