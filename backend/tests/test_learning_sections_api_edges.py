"""
Learning API — Sections edges (ordering tie-break and pagination behavior)

Scenarios:
- Tie-break when multiple released sections share the same position across units:
  order must be stable by section id asc.
- Offset beyond total results: returns 404 and uses private, no-store cache header.
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
    return httpx.AsyncClient(
        transport=ASGITransport(app=main.app),
        base_url="http://test",
        headers={"Origin": "http://test"},
    )


async def _create_course(client: httpx.AsyncClient, title: str = "Mathe") -> str:
    r = await client.post("/api/teaching/courses", json={"title": title})
    assert r.status_code == 201
    return r.json()["id"]


async def _create_unit(client: httpx.AsyncClient, title: str) -> dict:
    r = await client.post("/api/teaching/units", json={"title": title})
    assert r.status_code == 201
    return r.json()


async def _create_section(client: httpx.AsyncClient, unit_id: str, title: str) -> dict:
    r = await client.post(f"/api/teaching/units/{unit_id}/sections", json={"title": title})
    assert r.status_code == 201
    return r.json()


async def _attach_unit(client: httpx.AsyncClient, course_id: str, unit_id: str) -> dict:
    r = await client.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": unit_id})
    assert r.status_code == 201
    return r.json()


async def _add_member(client: httpx.AsyncClient, course_id: str, student_sub: str) -> None:
    r = await client.post(f"/api/teaching/courses/{course_id}/members", json={"student_sub": student_sub})
    assert r.status_code in (201, 204)


def _visibility_path(course_id: str, module_id: str, section_id: str) -> str:
    return f"/api/teaching/courses/{course_id}/modules/{module_id}/sections/{section_id}/visibility"


@pytest.mark.anyio
async def test_sections_ordering_tie_break_by_section_id_across_units():
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402
    import routes.learning as learning  # noqa: E402
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        assert isinstance(teaching.REPO, DBTeachingRepo)
        from backend.learning.repo_db import DBLearningRepo  # type: ignore
        assert isinstance(learning.REPO, DBLearningRepo)
    except Exception:
        pytest.skip("DB-backed repos required")

    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-sections-edge", name="Lehrkraft", roles=["teacher"])
    student = main.SESSION_STORE.create(sub="s-sections-edge", name="Schüler", roles=["student"])

    async with (await _client()) as c:
        # Owner creates course, two units; each has one section at position 1
        c.cookies.set("gustav_session", teacher.session_id)
        course_id = await _create_course(c, "Kurs")
        u1 = await _create_unit(c, "Unit A")
        u2 = await _create_unit(c, "Unit B")
        s1 = await _create_section(c, u1["id"], "Abschnitt A1")
        s2 = await _create_section(c, u2["id"], "Abschnitt B1")
        m1 = await _attach_unit(c, course_id, u1["id"])  # position 1
        m2 = await _attach_unit(c, course_id, u2["id"])  # position 2

        # Release both sections
        await c.patch(_visibility_path(course_id, m1["id"], s1["id"]), json={"visible": True})
        await c.patch(_visibility_path(course_id, m2["id"], s2["id"]), json={"visible": True})

        # Add student membership
        await _add_member(c, course_id, student.sub)

        # Student lists sections
        c.cookies.set("gustav_session", student.session_id)
        r = await c.get(f"/api/learning/courses/{course_id}/sections", params={"limit": 50, "offset": 0})
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list) and len(items) >= 2
        # Both have position 1 in their respective units; ensure tie-break by id asc
        ids = [it["section"]["id"] for it in items]
        # Keep only the two sections we created
        ids = [sid for sid in ids if sid in {s1["id"], s2["id"]}]
        assert ids == sorted(ids)


@pytest.mark.anyio
async def test_sections_pagination_offset_beyond_total_returns_404():
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402
    import routes.learning as learning  # noqa: E402
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        assert isinstance(teaching.REPO, DBTeachingRepo)
        from backend.learning.repo_db import DBLearningRepo  # type: ignore
        assert isinstance(learning.REPO, DBLearningRepo)
    except Exception:
        pytest.skip("DB-backed repos required")

    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-sections-page", name="Lehrkraft", roles=["teacher"])
    student = main.SESSION_STORE.create(sub="s-sections-page", name="Schüler", roles=["student"])

    async with (await _client()) as c:
        c.cookies.set("gustav_session", teacher.session_id)
        course_id = await _create_course(c, "Kurs Paginierung")
        u = await _create_unit(c, "Unit X")
        s = await _create_section(c, u["id"], "Abschnitt X1")
        m = await _attach_unit(c, course_id, u["id"])
        await c.patch(_visibility_path(course_id, m["id"], s["id"]), json={"visible": True})
        await _add_member(c, course_id, student.sub)

        # Large offset beyond available rows
        c.cookies.set("gustav_session", student.session_id)
        r = await c.get(
            f"/api/learning/courses/{course_id}/sections",
            params={"limit": 1, "offset": 999},
        )
        assert r.status_code == 404
        assert r.headers.get("Cache-Control") == "private, no-store"
