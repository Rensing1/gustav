"""
SSR (Student) — Unit detail page shows released content without section titles.

Validates that the student unit page renders materials/tasks grouped by
sections, separated by a single horizontal rule between sections, and does not
include the section titles in the HTML.
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
    # Strict CSRF (dev = prod): provide Origin for write calls.
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


async def _add_material_md(client: httpx.AsyncClient, unit_id: str, section_id: str, title: str, body: str) -> dict:
    r = await client.post(
        f"/api/teaching/units/{unit_id}/sections/{section_id}/materials",
        json={"title": title, "body_md": body},
    )
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
async def test_student_unit_page_renders_without_section_titles_and_with_hr():
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
    teacher = main.SESSION_STORE.create(sub="t-student-unit", name="Lehrkraft", roles=["teacher"])
    student = main.SESSION_STORE.create(sub="s-student-unit", name="Schüler", roles=["student"])

    async with (await _client()) as c:
        # Teacher creates course, unit, two sections with materials
        c.cookies.set("gustav_session", teacher.session_id)
        course_id = await _create_course(c, "Kurs UI")
        unit = await _create_unit(c, "Unit UI")
        s1 = await _create_section(c, unit["id"], "Einführung")
        s2 = await _create_section(c, unit["id"], "Vertiefung")
        await _add_material_md(c, unit["id"], s1["id"], "Willkommen", "Hallo Welt")
        await _add_material_md(c, unit["id"], s2["id"], "Weiter", "Mehr Inhalt")
        module = await _attach_unit(c, course_id, unit["id"])

        # Release both sections
        await c.patch(_visibility_path(course_id, module["id"], s1["id"]), json={"visible": True})
        await c.patch(_visibility_path(course_id, module["id"], s2["id"]), json={"visible": True})

        # Student membership
        await _add_member(c, course_id, student.sub)

        # Student opens unit page
        c.cookies.set("gustav_session", student.session_id)
        r = await c.get(f"/learning/courses/{course_id}/units/{unit["id"]}")
        assert r.status_code == 200
        assert r.headers.get("Cache-Control") == "private, no-store"
        html = r.text
        # Section titles must not appear
        assert "Einführung" not in html
        assert "Vertiefung" not in html
        # Materials should be present
        assert "Willkommen" in html and "Weiter" in html
        # Exactly one <hr> between two sections
        assert html.count("<hr") == 1
