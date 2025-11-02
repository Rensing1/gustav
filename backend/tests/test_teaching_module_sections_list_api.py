"""
Teaching API — List sections for a module with visibility (contract-first).

Defines the behaviour for a new endpoint that returns the ordered list of
sections for the unit attached to a specific course module, enriched with the
current visibility state for that module (owner-only).

TDD: This test is written before the handler exists and should fail (red) until
the API is implemented according to the OpenAPI contract.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest
import httpx
from httpx import ASGITransport

pytestmark = pytest.mark.anyio("asyncio")

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
if str(WEB_DIR) not in os.sys.path:
    os.sys.path.insert(0, str(WEB_DIR))
import main  # type: ignore  # noqa: E402
from identity_access.stores import SessionStore  # type: ignore  # noqa: E402

from utils.db import require_db_or_skip as _require_db_or_skip


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test")


async def _create_course(client: httpx.AsyncClient, title: str = "Mathematik 10A") -> str:
    resp = await client.post("/api/teaching/courses", json={"title": title})
    assert resp.status_code == 201
    return resp.json()["id"]


async def _create_unit(client: httpx.AsyncClient, title: str = "Funktionen") -> dict:
    resp = await client.post("/api/teaching/units", json={"title": title})
    assert resp.status_code == 201
    return resp.json()


async def _create_section(client: httpx.AsyncClient, unit_id: str, title: str) -> dict:
    resp = await client.post(f"/api/teaching/units/{unit_id}/sections", json={"title": title})
    assert resp.status_code == 201
    return resp.json()


async def _attach_unit_to_course(
    client: httpx.AsyncClient, course_id: str, unit_id: str, context_notes: str | None = None
) -> dict:
    payload: dict[str, object] = {"unit_id": unit_id}
    if context_notes is not None:
        payload["context_notes"] = context_notes
    resp = await client.post(f"/api/teaching/courses/{course_id}/modules", json=payload)
    assert resp.status_code == 201
    return resp.json()


def _list_path(course_id: str, module_id: str) -> str:
    return f"/api/teaching/courses/{course_id}/modules/{module_id}/sections"


def _visibility_path(course_id: str, module_id: str, section_id: str) -> str:
    return f"/api/teaching/courses/{course_id}/modules/{module_id}/sections/{section_id}/visibility"


@pytest.mark.anyio
async def test_list_sections_with_visibility_owner_happy_path():
    main.SESSION_STORE = SessionStore()
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    owner = main.SESSION_STORE.create(sub="teacher-list-sections-owner", name="Frau Liste", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", owner.session_id)

        # Arrange: course, unit, sections, attach as module
        course_id = await _create_course(client, title="Physik 9B")
        unit = await _create_unit(client, title="Elektrizität")
        s1 = await _create_section(client, unit["id"], title="Einführung")
        s2 = await _create_section(client, unit["id"], title="Ohmsches Gesetz")
        s3 = await _create_section(client, unit["id"], title="Schaltkreise")
        module = await _attach_unit_to_course(client, course_id, unit["id"], context_notes="Unterricht")

        # Toggle visibility for s2 to true; others remain hidden
        vr = await client.patch(
            _visibility_path(course_id, module["id"], s2["id"]),
            json={"visible": True},
            headers={"Origin": "http://test"},
        )
        assert vr.status_code == 200

        # Act: list sections for module with visibility
        resp = await client.get(_list_path(course_id, module["id"]))
        assert resp.status_code == 200
        # Owner-scoped GET varies by Origin to avoid cache confusion
        assert resp.headers.get("Vary") == "Origin"
        data = resp.json()
        assert isinstance(data, list)
        assert [item["title"] for item in data] == ["Einführung", "Ohmsches Gesetz", "Schaltkreise"]
        # Check required fields and visibility mapping
        by_id = {row["id"]: row for row in data}
        assert by_id[s1["id"]] == {
            "id": s1["id"],
            "unit_id": unit["id"],
            "title": "Einführung",
            "position": 1,
            "visible": False,
            "released_at": None,
        }
        assert by_id[s2["id"]]["visible"] is True
        assert by_id[s2["id"]]["released_at"] is not None
        assert by_id[s3["id"]]["visible"] is False
        assert by_id[s3["id"]]["released_at"] is None


@pytest.mark.anyio
async def test_list_sections_requires_owner_and_valid_ids():
    main.SESSION_STORE = SessionStore()
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    owner = main.SESSION_STORE.create(sub="teacher-list-sections-owner2", name="Owner", roles=["teacher"])
    other_teacher = main.SESSION_STORE.create(sub="teacher-list-sections-other", name="Other", roles=["teacher"])
    student = main.SESSION_STORE.create(sub="student-list-sections", name="Max", roles=["student"])

    async with (await _client()) as client:
        # Unauthenticated → 401
        resp401 = await client.get(_list_path("00000000-0000-0000-0000-000000000000", "00000000-0000-0000-0000-000000000000"))
        assert resp401.status_code == 401
        assert resp401.headers.get("Vary") == "Origin"

        # Set up real module
        client.cookies.set("gustav_session", owner.session_id)
        course_id = await _create_course(client)
        unit = await _create_unit(client)
        await _create_section(client, unit["id"], title="A")
        module = await _attach_unit_to_course(client, course_id, unit["id"])  # noqa: F841

        # Invalid UUIDs → 400
        bad_course = await client.get(_list_path("not-a-uuid", module["id"]))
        assert bad_course.status_code == 400
        assert bad_course.headers.get("Vary") == "Origin"
        assert bad_course.json().get("detail") == "invalid_course_id"
        bad_module = await client.get(_list_path(course_id, "not-a-uuid"))
        assert bad_module.status_code == 400
        assert bad_module.headers.get("Vary") == "Origin"
        assert bad_module.json().get("detail") == "invalid_module_id"

        # Non-owner teacher → 403
        client.cookies.set("gustav_session", other_teacher.session_id)
        resp403 = await client.get(_list_path(course_id, module["id"]))
        assert resp403.status_code == 403
        assert resp403.headers.get("Vary") == "Origin"

        # Student → 403
        client.cookies.set("gustav_session", student.session_id)
        resp403b = await client.get(_list_path(course_id, module["id"]))
        assert resp403b.status_code == 403
        assert resp403b.headers.get("Vary") == "Origin"

        # Unknown module id (well-formed) → 404
        client.cookies.set("gustav_session", owner.session_id)
        resp404 = await client.get(_list_path(course_id, "00000000-0000-0000-0000-000000000001"))
        assert resp404.status_code == 404
        assert resp404.headers.get("Vary") == "Origin"
