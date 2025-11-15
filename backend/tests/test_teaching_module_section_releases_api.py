"""
Teaching API — Module section releases (owner-only)

Scenarios:
- 200 for owner with list of releases (can be empty) and private cache header.
- 403 for non-owner teacher.
- 400 for invalid UUIDs in path.
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


def _releases_path(course_id: str, module_id: str) -> str:
    return f"/api/teaching/courses/{course_id}/modules/{module_id}/sections/releases"


@pytest.mark.anyio
async def test_list_releases_owner_only_and_cache_header():
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required")

    main.SESSION_STORE = SessionStore()
    owner = main.SESSION_STORE.create(sub="t-owner-rel", name="Owner", roles=["teacher"])  # type: ignore
    other = main.SESSION_STORE.create(sub="t-other-rel", name="Other", roles=["teacher"])  # type: ignore

    async with (await _client()) as c:
        # Owner creates course/unit/module and releases a section
        c.cookies.set("gustav_session", owner.session_id)
        course_id = await _create_course(c, "Kurs")
        unit = await _create_unit(c, "Unit")
        section = await _create_section(c, unit["id"], "A1")
        module = await _attach_unit(c, course_id, unit["id"])

        # Owner lists releases (should be empty initially)
        r0 = await c.get(_releases_path(course_id, module["id"]))
        assert r0.status_code == 200
        assert r0.headers.get("Cache-Control") == "private, no-store"
        assert isinstance(r0.json(), list)

        # Release the section and list again
        toggle = await c.patch(
            f"/api/teaching/courses/{course_id}/modules/{module['id']}/sections/{section['id']}/visibility",
            json={"visible": True},
        )
        assert toggle.status_code == 200

        r1 = await c.get(_releases_path(course_id, module["id"]))
        assert r1.status_code == 200
        items = r1.json()
        assert any(it.get("section_id") == section["id"] and it.get("visible") for it in items)

        # Non-owner is forbidden
        c.cookies.set("gustav_session", other.session_id)
        r_forbidden = await c.get(_releases_path(course_id, module["id"]))
        assert r_forbidden.status_code == 403
        assert r_forbidden.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_list_releases_invalid_uuids():
    async with (await _client()) as c:
        main.SESSION_STORE = SessionStore()
        teacher = main.SESSION_STORE.create(sub="t-bad", name="T", roles=["teacher"])  # type: ignore
        c.cookies.set("gustav_session", teacher.session_id)
        r = await c.get("/api/teaching/courses/not-a-uuid/modules/not-a-uuid/sections/releases")
        assert r.status_code == 400
        assert r.headers.get("Cache-Control") == "private, no-store"
