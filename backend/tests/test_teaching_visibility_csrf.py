"""
Teaching API — CSRF and Cache-Control for visibility updates

Scenarios:
- 403 with detail=csrf_violation on cross-origin PATCH
- 200 with private cache header on same-origin PATCH
- 400 invalid UUID still carries private cache header
"""
from __future__ import annotations

import pytest
import httpx
from httpx import ASGITransport

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


def _visibility_path(course_id: str, module_id: str, section_id: str) -> str:
    return f"/api/teaching/courses/{course_id}/modules/{module_id}/sections/{section_id}/visibility"


@pytest.mark.anyio
async def test_visibility_csrf_blocks_cross_origin():
    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-csrf-vis", name="Lehrkraft", roles=["teacher"])  # type: ignore

    async with (await _client()) as c:
        c.cookies.set("gustav_session", teacher.session_id)
        course_id = await _create_course(c, "Kurs")
        unit = await _create_unit(c, "Unit")
        section = await _create_section(c, unit["id"], "Abschnitt 1")
        module = await _attach_unit(c, course_id, unit["id"])

        r = await c.patch(
            _visibility_path(course_id, module["id"], section["id"]),
            json={"visible": True},
            headers={"Origin": "http://evil.local"},
        )
        assert r.status_code == 403
        body = r.json()
        assert body.get("error") == "forbidden"
        assert body.get("detail") == "csrf_violation"
        assert r.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_visibility_same_origin_ok_and_private_cache():
    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-same-vis", name="Lehrkraft", roles=["teacher"])  # type: ignore

    async with (await _client()) as c:
        c.cookies.set("gustav_session", teacher.session_id)
        course_id = await _create_course(c, "Kurs 2")
        unit = await _create_unit(c, "Unit 2")
        section = await _create_section(c, unit["id"], "Abschnitt 2")
        module = await _attach_unit(c, course_id, unit["id"])

        r = await c.patch(
            _visibility_path(course_id, module["id"], section["id"]),
            json={"visible": True},
            headers={"Origin": "http://test"},
        )
        assert r.status_code == 200
        assert r.headers.get("Cache-Control") == "private, no-store"
        data = r.json()
        assert data.get("section_id") == section["id"]
        assert data.get("visible") is True


@pytest.mark.anyio
async def test_visibility_invalid_uuid_private_cache_header():
    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-bad-vis", name="Lehrkraft", roles=["teacher"])  # type: ignore

    async with (await _client()) as c:
        c.cookies.set("gustav_session", teacher.session_id)
        r = await c.patch(
            "/api/teaching/courses/not-a-uuid/modules/not-a-uuid/sections/not-a-uuid/visibility",
            json={"visible": True},
            headers={"Origin": "http://test"},
        )
        assert r.status_code == 400
        assert r.json().get("error") == "bad_request"
        assert r.headers.get("Cache-Control") == "private, no-store"

