"""
Learning API — Unit-specific sections endpoint

Scenarios (Contract-first):
- 200 + empty list when no sections released for the unit
- 404 when unit does not belong to the course (or not found)
- 400 on invalid UUID in path and private, no-store headers
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
async def test_unit_sections_returns_unit_id_for_released_section():
    """When a section is released, response section includes unit_id per contract."""
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
    teacher = main.SESSION_STORE.create(sub="t-unit-unitid", name="Lehrkraft", roles=["teacher"])  # type: ignore
    student = main.SESSION_STORE.create(sub="s-unit-unitid", name="Schüler", roles=["student"])  # type: ignore

    async with (await _client()) as c:
        c.cookies.set("gustav_session", teacher.session_id)
        course_id = await _create_course(c, "Kurs UnitID")
        unit = await _create_unit(c, "Unit U1")
        section = await _create_section(c, unit["id"], "Abschnitt S1")
        module = await _attach_unit(c, course_id, unit["id"])
        # Release the section
        await c.patch(_visibility_path(course_id, module["id"], section["id"]), json={"visible": True})
        # Enroll student
        await _add_member(c, course_id, student.sub)

        c.cookies.set("gustav_session", student.session_id)
        r = await c.get(
            f"/api/learning/courses/{course_id}/units/{unit['id']}/sections",
            params={"limit": 5, "offset": 0},
        )
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list) and len(items) >= 1
        sec = items[0]["section"]
        assert "unit_id" in sec and isinstance(sec["unit_id"], str)
        assert sec["unit_id"] == unit["id"]

@pytest.mark.anyio
async def test_unit_sections_returns_200_and_empty_list_when_none_released():
    """New endpoint returns 200 with [] when no sections are released for the unit."""
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
    teacher = main.SESSION_STORE.create(sub="t-unit-empty", name="Lehrkraft", roles=["teacher"])
    student = main.SESSION_STORE.create(sub="s-unit-empty", name="Schüler", roles=["student"])

    async with (await _client()) as c:
        c.cookies.set("gustav_session", teacher.session_id)
        course_id = await _create_course(c, "Kurs")
        unit = await _create_unit(c, "Unit A")
        # one section exists but is NOT released
        await _create_section(c, unit["id"], "Abschnitt A1")
        await _attach_unit(c, course_id, unit["id"])
        await _add_member(c, course_id, student.sub)

        c.cookies.set("gustav_session", student.session_id)
        r = await c.get(
            f"/api/learning/courses/{course_id}/units/{unit['id']}/sections",
            params={"include": "materials,tasks", "limit": 50, "offset": 0},
        )
        assert r.status_code == 200
        assert r.headers.get("Cache-Control") == "private, no-store"
        items = r.json()
        assert isinstance(items, list)
        assert items == []


@pytest.mark.anyio
async def test_unit_sections_404_when_unit_not_in_course():
    """404 when the requested unit does not belong to the course (no leak on existence)."""
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
    teacher = main.SESSION_STORE.create(sub="t-unit-404", name="Lehrkraft", roles=["teacher"])
    student = main.SESSION_STORE.create(sub="s-unit-404", name="Schüler", roles=["student"])

    async with (await _client()) as c:
        c.cookies.set("gustav_session", teacher.session_id)
        course_id = await _create_course(c, "Kurs")
        # course has unit A attached
        unit_a = await _create_unit(c, "Unit A")
        await _attach_unit(c, course_id, unit_a["id"])
        # unit B exists but is not attached to the course
        unit_b = await _create_unit(c, "Unit B")
        await _add_member(c, course_id, student.sub)

        c.cookies.set("gustav_session", student.session_id)
        r = await c.get(
            f"/api/learning/courses/{course_id}/units/{unit_b['id']}/sections",
            params={"limit": 10, "offset": 0},
        )
        assert r.status_code == 404
        assert r.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_unit_sections_invalid_uuid_uses_contract_detail_and_cache_header():
    """Invalid UUID in path returns 400 detail=invalid_uuid with private cache header."""
    main.SESSION_STORE = SessionStore()
    student = main.SESSION_STORE.create(sub="s-unit-uuid", name="Schüler", roles=["student"])  # type: ignore

    async with (await _client()) as c:
        c.cookies.set("gustav_session", student.session_id)
        r = await c.get(
            "/api/learning/courses/not-a-uuid/units/not-a-uuid/sections",
            params={"limit": 5, "offset": 0},
        )
    assert r.status_code == 400
    body = r.json()
    assert body.get("detail") == "invalid_uuid"
    assert r.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_unit_sections_403_when_student_not_member():
    """403 when caller is not enrolled in the course."""
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
    teacher = main.SESSION_STORE.create(sub="t-unit-403", name="Lehrkraft", roles=["teacher"])  # type: ignore
    stranger = main.SESSION_STORE.create(sub="s-unit-403", name="Schüler", roles=["student"])  # type: ignore

    async with (await _client()) as c:
        # Prepare course/unit/section and release it but do not enroll the student
        c.cookies.set("gustav_session", teacher.session_id)
        course_id = await _create_course(c, "Kurs 403")
        unit = await _create_unit(c, "Unit 403")
        section = await _create_section(c, unit["id"], "Abschnitt 403")
        module = await _attach_unit(c, course_id, unit["id"])
        await c.patch(_visibility_path(course_id, module["id"], section["id"]), json={"visible": True})

        # Non-member student tries to list
        c.cookies.set("gustav_session", stranger.session_id)
        r = await c.get(
            f"/api/learning/courses/{course_id}/units/{unit['id']}/sections",
            params={"include": "materials,tasks", "limit": 10, "offset": 0},
        )
        assert r.status_code == 403
        assert r.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_unit_sections_400_on_invalid_include_param():
    """400 when include contains unsupported tokens."""
    main.SESSION_STORE = SessionStore()
    student = main.SESSION_STORE.create(sub="s-unit-inc", name="Schüler", roles=["student"])  # type: ignore

    async with (await _client()) as c:
        c.cookies.set("gustav_session", student.session_id)
        r = await c.get(
            "/api/learning/courses/11111111-1111-1111-1111-111111111111/units/22222222-2222-2222-2222-222222222222/sections",
            params={"include": "materials,comments"},
        )
    assert r.status_code == 400
    body = r.json()
    assert body.get("detail") == "invalid_include"
    assert r.headers.get("Cache-Control") == "private, no-store"
