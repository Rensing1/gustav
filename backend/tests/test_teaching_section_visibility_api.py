"""
Teaching API — Section visibility toggles within course modules (contract-first, TDD).

Defines desired behaviour for the endpoint that lets a course owner release or
hide individual sections for their students. Tests intentionally fail until the
API, repo, and migration logic implement the contract (red phase).
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
    return httpx.AsyncClient(
        transport=ASGITransport(app=main.app),
        base_url="http://test",
        headers={"Origin": "http://test"},
    )


async def _create_course(client: httpx.AsyncClient, title: str = "Mathematik 10A") -> str:
    resp = await client.post("/api/teaching/courses", json={"title": title})
    assert resp.status_code == 201
    return resp.json()["id"]


async def _create_unit(client: httpx.AsyncClient, title: str = "Funktionen") -> dict:
    resp = await client.post("/api/teaching/units", json={"title": title})
    assert resp.status_code == 201
    return resp.json()


async def _create_section(client: httpx.AsyncClient, unit_id: str, title: str = "Einführung") -> dict:
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


def _visibility_path(course_id: str, module_id: str, section_id: str) -> str:
    return f"/api/teaching/courses/{course_id}/modules/{module_id}/sections/{section_id}/visibility"


@pytest.mark.anyio
async def test_section_visibility_requires_teacher_owner():
    main.SESSION_STORE = SessionStore()
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    # Unauthenticated request → 401 before any other validation
    async with (await _client()) as client:
        resp = await client.patch(
            "/api/teaching/courses/00000000-0000-0000-0000-000000000000/"
            "modules/00000000-0000-0000-0000-000000000000/"
            "sections/00000000-0000-0000-0000-000000000000/visibility",
            json={"visible": True},
        )
        assert resp.status_code == 401

    owner_sub = "teacher-section-release-owner"
    owner = main.SESSION_STORE.create(sub=owner_sub, name="Frau Owner", roles=["teacher"])
    student = main.SESSION_STORE.create(sub="student-section-release", name="Max", roles=["student"])
    other_teacher = main.SESSION_STORE.create(
        sub="teacher-section-release-other", name="Herr Fremd", roles=["teacher"]
    )

    async with (await _client()) as client:
        # Owner creates course, unit, section, module
        client.cookies.set("gustav_session", owner.session_id)
        course_id = await _create_course(client, title="Physik 9B")
        unit = await _create_unit(client, title="Elektrizität")
        section = await _create_section(client, unit["id"], title="Stromkreise")
        module = await _attach_unit_to_course(client, course_id, unit["id"], context_notes="Vorbereitungsphase")

        path = _visibility_path(course_id, module["id"], section["id"])

        # Student cannot toggle visibility → 403
        client.cookies.set("gustav_session", student.session_id)
        student_resp = await client.patch(path, json={"visible": True})
        assert student_resp.status_code == 403

        # Non-owner teacher cannot toggle → 403
        client.cookies.set("gustav_session", other_teacher.session_id)
        other_resp = await client.patch(path, json={"visible": True})
        assert other_resp.status_code == 403


@pytest.mark.anyio
async def test_section_visibility_toggle_and_error_conditions():
    main.SESSION_STORE = SessionStore()
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    owner_sub = "teacher-section-release-toggle"
    owner = main.SESSION_STORE.create(sub=owner_sub, name="Frau Toggle", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", owner.session_id)

        course_id = await _create_course(client, title="Biologie 8C")
        unit = await _create_unit(client, title="Zellbiologie")
        section = await _create_section(client, unit["id"], title="Zellmembran")
        module = await _attach_unit_to_course(client, course_id, unit["id"])

        path = _visibility_path(course_id, module["id"], section["id"])

        # Happy path: release the section
        release_resp = await client.patch(path, json={"visible": True})
        assert release_resp.status_code == 200
        release_body = release_resp.json()
        assert release_body["course_module_id"] == module["id"]
        assert release_body["section_id"] == section["id"]
        assert release_body["visible"] is True
        assert release_body["released_by"] == owner_sub
        assert release_body["released_at"] is not None

        # Toggle back to hidden
        hide_resp = await client.patch(path, json={"visible": False})
        assert hide_resp.status_code == 200
        hide_body = hide_resp.json()
        assert hide_body["visible"] is False
        assert hide_body["released_by"] == owner_sub
        assert hide_body["released_at"] is None

        # Missing visible field → 400
        missing_field = await client.patch(path, json={})
        assert missing_field.status_code == 400
        assert missing_field.json().get("detail") == "missing_visible"

        # Invalid type for visible → 400
        invalid_type = await client.patch(path, json={"visible": "yes"})
        assert invalid_type.status_code == 400
        assert invalid_type.json().get("detail") == "invalid_visible_type"

        # Section not belonging to module → 404
        other_unit = await _create_unit(client, title="Ökologie")
        other_section = await _create_section(client, other_unit["id"], title="Kreisläufe")
        mismatch = await client.patch(
            _visibility_path(course_id, module["id"], other_section["id"]),
            json={"visible": True},
        )
        assert mismatch.status_code == 404
        assert mismatch.json().get("detail") in {"section_not_in_module", "not_found"}

        # Invalid UUID in path → 400
        bad_uuid = await client.patch(
            f"/api/teaching/courses/{course_id}/modules/{module['id']}/sections/not-a-uuid/visibility",
            json={"visible": True},
        )
        assert bad_uuid.status_code == 400
        assert bad_uuid.json().get("detail") == "invalid_section_id"


@pytest.mark.anyio
async def test_section_visibility_invalid_ids_and_not_found_details():
    """Validate 400 for invalid UUIDs and 404 detail codes for missing module."""
    main.SESSION_STORE = SessionStore()
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    owner = main.SESSION_STORE.create(sub="teacher-section-release-ids", name="Ids", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", owner.session_id)
        # Invalid course_id → 400
        resp1 = await client.patch(
            "/api/teaching/courses/not-a-uuid/modules/00000000-0000-0000-0000-000000000000/sections/00000000-0000-0000-0000-000000000000/visibility",
            json={"visible": True},
        )
        assert resp1.status_code == 400
        assert resp1.json().get("detail") == "invalid_course_id"

        # Valid course/module setup
        course_id = await _create_course(client)
        unit = await _create_unit(client)
        section = await _create_section(client, unit["id"])  # noqa: F841 - used later
        module = await _attach_unit_to_course(client, course_id, unit["id"])  # noqa: F841 - used later

        # Invalid module_id UUID → 400
        resp2 = await client.patch(
            f"/api/teaching/courses/{course_id}/modules/not-a-uuid/sections/{section['id']}/visibility",
            json={"visible": True},
        )
        assert resp2.status_code == 400
        assert resp2.json().get("detail") == "invalid_module_id"

        # Unknown module UUID (well-formed) → 404 with detail
        unknown_module = "00000000-0000-0000-0000-000000000001"
        resp3 = await client.patch(
            f"/api/teaching/courses/{course_id}/modules/{unknown_module}/sections/{section['id']}/visibility",
            json={"visible": True},
        )
        assert resp3.status_code == 404
        # Should include a specific detail when available
        assert resp3.json().get("error") == "not_found"
        # Accept either specific DB code or generic fallback depending on backend
        assert resp3.json().get("detail") in {"module_not_found", None}
