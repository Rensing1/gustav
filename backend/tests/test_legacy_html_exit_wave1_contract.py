"""Contracts for the first retired FastAPI HTML/HTMX route removal wave."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.routing import APIRoute
from httpx import ASGITransport

import backend.web.main as main
from backend.tests.runtime_auth_helpers import install_session_store


pytestmark = pytest.mark.anyio("asyncio")


REMOVED_LEGACY_ENTRY_ROUTES = {
    ("/courses", "GET"),
    ("/courses", "POST"),
    ("/courses/{course_id}/delete", "POST"),
    ("/courses/{course_id}/edit", "GET"),
    ("/courses/{course_id}/edit", "POST"),
    ("/courses/{course_id}/members", "GET"),
    ("/courses/{course_id}/members", "POST"),
    ("/courses/{course_id}/members/search", "GET"),
    ("/courses/{course_id}/members/{student_sub}/delete", "POST"),
    ("/courses/{course_id}/modules", "GET"),
    ("/courses/{course_id}/modules/create", "POST"),
    ("/courses/{course_id}/modules/reorder", "POST"),
    ("/courses/{course_id}/modules/{module_id}/delete", "POST"),
    ("/courses/{course_id}/modules/{module_id}/sections", "GET"),
    ("/courses/{course_id}/modules/{module_id}/sections/{section_id}/toggle", "POST"),
    ("/learning", "GET"),
    ("/learning/courses/{course_id}", "GET"),
    ("/learning/courses/{course_id}/tasks/{task_id}/history", "GET"),
    ("/learning/courses/{course_id}/tasks/{task_id}/history/poll", "GET"),
    ("/learning/courses/{course_id}/tasks/{task_id}/submit", "POST"),
    ("/learning/courses/{course_id}/units/{unit_id}", "GET"),
    ("/learning/courses/{course_id}/units/{unit_id}/modules/{module_id}/fragment", "GET"),
    ("/teaching/live", "GET"),
    ("/teaching/live/open", "GET"),
    ("/teaching/live/units", "GET"),
    ("/teaching/courses/{course_id}/students/{student_sub:path}/live", "GET"),
    ("/teaching/courses/{course_id}/units/{unit_id}/live", "GET"),
    ("/teaching/courses/{course_id}/units/{unit_id}/live/detail", "GET"),
    ("/teaching/courses/{course_id}/units/{unit_id}/live/matrix", "GET"),
    ("/teaching/courses/{course_id}/units/{unit_id}/live/matrix/delta", "GET"),
    ("/teaching/courses/{course_id}/units/{unit_id}/live/sections-panel", "GET"),
    ("/teaching/courses/{course_id}/modules/{module_id}/sections/{section_id}/visibility", "POST"),
    ("/units", "GET"),
    ("/units", "POST"),
    ("/units/{unit_id}", "GET"),
    ("/units/{unit_id}/edit", "GET"),
    ("/units/{unit_id}/edit", "POST"),
    ("/units/{unit_id}/modular-editor/module/{module_id}/delete", "GET"),
    ("/units/{unit_id}/modular-editor/module/{module_id}/delete", "POST"),
    ("/units/{unit_id}/modular-editor/module/{module_id}/edges/delete", "POST"),
    ("/units/{unit_id}/modular-editor/module/{module_id}/rename", "GET"),
    ("/units/{unit_id}/modular-editor/module/{module_id}/rename", "POST"),
    ("/units/{unit_id}/modular-editor/module/{module_id}/settings", "POST"),
    ("/units/{unit_id}/modular-editor/phase/new", "GET"),
    ("/units/{unit_id}/modular-editor/phase/new", "POST"),
    ("/units/{unit_id}/modular-editor/phase/{phase_id}/delete", "GET"),
    ("/units/{unit_id}/modular-editor/phase/{phase_id}/delete", "POST"),
    ("/units/{unit_id}/modular-editor/phase/{phase_id}/module/new", "GET"),
    ("/units/{unit_id}/modular-editor/phase/{phase_id}/module/new", "POST"),
    ("/units/{unit_id}/modular-editor/phase/{phase_id}/rename", "GET"),
    ("/units/{unit_id}/modular-editor/phase/{phase_id}/rename", "POST"),
    ("/units/{unit_id}/modules", "POST"),
    ("/units/{unit_id}/modules/{module_id}", "GET"),
    ("/units/{unit_id}/modules/{module_id}/panel", "GET"),
    ("/units/{unit_id}/phases", "GET"),
    ("/units/{unit_id}/phases", "POST"),
    ("/units/{unit_id}/phases/reorder", "POST"),
    ("/units/{unit_id}/sections", "POST"),
    ("/units/{unit_id}/sections/reorder", "POST"),
    ("/units/{unit_id}/sections/{section_id}", "GET"),
    ("/units/{unit_id}/sections/{section_id}/delete", "POST"),
    ("/units/{unit_id}/sections/{section_id}/materials/create", "POST"),
    ("/units/{unit_id}/sections/{section_id}/materials/finalize", "POST"),
    ("/units/{unit_id}/sections/{section_id}/materials/new", "GET"),
    ("/units/{unit_id}/sections/{section_id}/materials/reorder", "POST"),
    ("/units/{unit_id}/sections/{section_id}/materials/upload-intent", "POST"),
    ("/units/{unit_id}/sections/{section_id}/materials/{material_id}", "GET"),
    ("/units/{unit_id}/sections/{section_id}/materials/{material_id}/delete", "POST"),
    ("/units/{unit_id}/sections/{section_id}/materials/{material_id}/update", "POST"),
    ("/units/{unit_id}/sections/{section_id}/tasks/create", "POST"),
    ("/units/{unit_id}/sections/{section_id}/tasks/new", "GET"),
    ("/units/{unit_id}/sections/{section_id}/tasks/reorder", "POST"),
    ("/units/{unit_id}/sections/{section_id}/tasks/{task_id}", "GET"),
    ("/units/{unit_id}/sections/{section_id}/tasks/{task_id}/delete", "POST"),
    ("/units/{unit_id}/sections/{section_id}/tasks/{task_id}/update", "POST"),
}


def _session_for(store: Any, *, sub: str, roles: list[str]) -> str:
    rec = store.create(sub=sub, roles=roles, name=sub, ttl_seconds=60)
    return rec.session_id


async def _client_with_session(session_id: str) -> httpx.AsyncClient:
    client = httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test")
    client.cookies.set(main.SESSION_COOKIE_NAME, session_id)
    return client


def test_first_legacy_exit_wave_routes_are_not_registered_as_fastapi_handlers() -> None:
    """Retired product entries must not look like active local HTML routes."""

    operations = {
        (route.path, method)
        for route in main.app.routes
        if isinstance(route, APIRoute)
        for method in route.methods
    }

    assert REMOVED_LEGACY_ENTRY_ROUTES.isdisjoint(operations)


def test_removed_course_members_entries_leave_no_ssr_helpers_in_main() -> None:
    """Retired Course-Members HTML routes must not leave SSR helper islands."""

    source = (Path(__file__).resolve().parents[2] / "backend/web/main.py").read_text(encoding="utf-8")

    for retired_marker in (
        "def _email_localpart_identifier",
        "def _member_localpart_label",
        "def _resolve_member_login_labels",
        "def _teacher_visible_label",
        "def _load_teacher_login_labels",
        "def _load_teacher_live_login_labels",
        "def _load_teacher_display_names",
        "_MEMBER_SUBS_CACHE",
        "MEMBERS_SEARCH_RESULT_LIMIT",
        "MEMBERS_ROSTER_PAGE_SIZE",
        "def _member_subs_cache_",
        "def _fetch_all_course_member_subs_for_filter",
        "def _member_subs_for_search",
        "def _apply_member_login_labels",
        "def _apply_live_row_login_labels",
        "def _render_members_",
        "def _handle_member_change_api",
    ):
        assert retired_marker not in source


def test_removed_teacher_unit_entries_leave_no_ssr_helpers_in_main() -> None:
    """Retired teacher unit/course HTML routes must not leave SSR helper islands."""

    source = (Path(__file__).resolve().parents[2] / "backend/web/main.py").read_text(encoding="utf-8")

    for retired_marker in (
        "def _render_unit_list_partial",
        "def _render_units_page_html",
        "def _render_section_list_partial",
        "def _render_sections_page_html",
        "def _render_modular_unit_editor_graph_html",
        "def _render_modular_unit_editor_page_html",
        "def _render_material_list_partial",
        "def _render_task_list_partial",
        "def _render_module_list_partial",
        "def _render_available_units_partial",
        "def _render_section_detail_page_html",
        "def _render_module_detail_page_html",
        "def _extract_api_error_detail",
        "def _fetch_sections_for_unit",
        "def _fetch_unit_modules_for_unit",
        "def _fetch_unit_module_edges_for_unit",
        "def _get_unit_module_for_teacher",
        "def _fetch_unit_phases_for_unit",
        "def _render_unit_phases_list_partial",
        "def _render_unit_phases_page_html",
        "def _render_unit_edit_response",
        "from backend.web.components.forms.unit_edit_form import UnitEditForm",
        "from backend.web.components.forms.course_edit_form import CourseEditForm",
    ):
        assert retired_marker not in source


@pytest.mark.anyio
async def test_removed_learning_entry_still_returns_intentional_retirement_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = install_session_store(monkeypatch, main)
    student_session = _session_for(store, sub="student-legacy-wave1", roles=["student"])
    teacher_session = _session_for(store, sub="teacher-legacy-wave1", roles=["teacher"])

    async with await _client_with_session(student_session) as client:
        student_response = await client.get("/learning")
    async with await _client_with_session(teacher_session) as client:
        teacher_response = await client.get("/learning", follow_redirects=False)

    assert student_response.status_code == 410
    assert student_response.headers.get("Cache-Control") == "private, no-store"
    assert "legacy route" in student_response.text.lower()
    assert teacher_response.status_code == 303
    assert teacher_response.headers.get("location") == "/"


@pytest.mark.anyio
async def test_removed_learning_course_entries_still_return_intentional_retirement_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = install_session_store(monkeypatch, main)
    student_session = _session_for(store, sub="student-learning-course-wave1", roles=["student"])
    teacher_session = _session_for(store, sub="teacher-learning-course-wave1", roles=["teacher"])
    course_id = "11111111-1111-1111-1111-111111111111"
    unit_id = "22222222-2222-2222-2222-222222222222"
    module_id = "33333333-3333-3333-3333-333333333333"
    task_id = "44444444-4444-4444-4444-444444444444"

    async with await _client_with_session(student_session) as client:
        retired_responses = [
            await client.get(f"/learning/courses/{course_id}"),
            await client.get(f"/learning/courses/{course_id}/units/{unit_id}"),
            await client.get(f"/learning/courses/{course_id}/units/{unit_id}/modules/{module_id}/fragment"),
            await client.post(
                f"/learning/courses/{course_id}/tasks/{task_id}/submit",
                data={"mode": "text", "text_body": "Abgabe"},
                headers={"Origin": "http://test"},
            ),
            await client.get(f"/learning/courses/{course_id}/tasks/{task_id}/history"),
            await client.get(f"/learning/courses/{course_id}/tasks/{task_id}/history/poll"),
        ]
    async with await _client_with_session(teacher_session) as client:
        forbidden_response = await client.get(f"/learning/courses/{course_id}", follow_redirects=False)

    assert all(response.status_code == 410 for response in retired_responses)
    assert all(response.headers.get("Cache-Control") == "private, no-store" for response in retired_responses)
    assert forbidden_response.status_code == 303
    assert forbidden_response.headers.get("location") == "/"


@pytest.mark.anyio
async def test_removed_teaching_live_entries_still_return_intentional_retirement_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = install_session_store(monkeypatch, main)
    teacher_session = _session_for(store, sub="teacher-live-wave1", roles=["teacher"])
    student_session = _session_for(store, sub="student-live-wave1", roles=["student"])

    async with await _client_with_session(teacher_session) as client:
        retired_responses = [
            await client.get("/teaching/live"),
            await client.get("/teaching/live/open"),
            await client.get("/teaching/live/units"),
        ]
    async with await _client_with_session(student_session) as client:
        forbidden_response = await client.get("/teaching/live", follow_redirects=False)

    assert all(response.status_code == 410 for response in retired_responses)
    assert all(response.headers.get("Cache-Control") == "private, no-store" for response in retired_responses)
    assert forbidden_response.status_code == 303
    assert forbidden_response.headers.get("location") == "/"


@pytest.mark.anyio
async def test_removed_deep_teaching_live_entries_return_retirement_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = install_session_store(monkeypatch, main)
    teacher_session = _session_for(store, sub="teacher-deep-live-wave1", roles=["teacher"])
    student_session = _session_for(store, sub="student-deep-live-wave1", roles=["student"])
    course_id = "11111111-1111-1111-1111-111111111111"
    unit_id = "22222222-2222-2222-2222-222222222222"

    async with await _client_with_session(teacher_session) as client:
        retired_responses = [
            await client.get(f"/teaching/courses/{course_id}/students/student-1/live"),
            await client.get(f"/teaching/courses/{course_id}/units/{unit_id}/live"),
            await client.get(f"/teaching/courses/{course_id}/units/{unit_id}/live/detail"),
            await client.get(f"/teaching/courses/{course_id}/units/{unit_id}/live/matrix"),
            await client.get(
                f"/teaching/courses/{course_id}/units/{unit_id}/live/matrix/delta",
                params={"updated_since": "2026-03-23T10:00:00+00:00"},
            ),
            await client.get(f"/teaching/courses/{course_id}/units/{unit_id}/live/sections-panel"),
        ]
    async with await _client_with_session(student_session) as client:
        forbidden_response = await client.get(
            f"/teaching/courses/{course_id}/units/{unit_id}/live",
            follow_redirects=False,
        )

    assert all(response.status_code == 410 for response in retired_responses)
    assert all(response.headers.get("Cache-Control") == "private, no-store" for response in retired_responses)
    assert all("legacy route" in response.text.lower() for response in retired_responses)
    assert forbidden_response.status_code == 303
    assert forbidden_response.headers.get("location") == "/"


@pytest.mark.anyio
async def test_removed_teacher_top_level_entries_still_return_intentional_retirement_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = install_session_store(monkeypatch, main)
    teacher_session = _session_for(store, sub="teacher-top-level-wave1", roles=["teacher"])
    student_session = _session_for(store, sub="student-top-level-wave1", roles=["student"])

    async with await _client_with_session(teacher_session) as client:
        retired_responses = [
            await client.get("/courses"),
            await client.get("/units"),
        ]
    async with await _client_with_session(student_session) as client:
        forbidden_response = await client.get("/courses", follow_redirects=False)

    assert all(response.status_code == 410 for response in retired_responses)
    assert all(response.headers.get("Cache-Control") == "private, no-store" for response in retired_responses)
    assert forbidden_response.status_code == 303
    assert forbidden_response.headers.get("location") == "/"


@pytest.mark.anyio
async def test_removed_course_detail_entries_still_return_intentional_retirement_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = install_session_store(monkeypatch, main)
    teacher_session = _session_for(store, sub="teacher-course-detail-wave1", roles=["teacher"])
    student_session = _session_for(store, sub="student-course-detail-wave1", roles=["student"])
    course_id = "11111111-1111-1111-1111-111111111111"

    async with await _client_with_session(teacher_session) as client:
        retired_responses = [
            await client.get(f"/courses/{course_id}/edit"),
            await client.post(f"/courses/{course_id}/edit", data={"title": "Neu"}, headers={"Origin": "http://test"}),
            await client.post(f"/courses/{course_id}/delete", headers={"Origin": "http://test"}),
            await client.get(f"/courses/{course_id}/members/search"),
        ]
    async with await _client_with_session(student_session) as client:
        forbidden_response = await client.get(f"/courses/{course_id}/edit", follow_redirects=False)

    assert all(response.status_code == 410 for response in retired_responses)
    assert all(response.headers.get("Cache-Control") == "private, no-store" for response in retired_responses)
    assert forbidden_response.status_code == 303
    assert forbidden_response.headers.get("location") == "/"


@pytest.mark.anyio
async def test_removed_course_modules_and_members_entries_still_return_retirement_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = install_session_store(monkeypatch, main)
    teacher_session = _session_for(store, sub="teacher-course-modules-wave1", roles=["teacher"])
    student_session = _session_for(store, sub="student-course-modules-wave1", roles=["student"])
    course_id = "11111111-1111-1111-1111-111111111111"
    module_id = "22222222-2222-2222-2222-222222222222"
    section_id = "33333333-3333-3333-3333-333333333333"

    async with await _client_with_session(teacher_session) as client:
        retired_responses = [
            await client.post("/courses", data={"title": "Neu"}, headers={"Origin": "http://test"}),
            await client.get(f"/courses/{course_id}/modules"),
            await client.post(
                f"/courses/{course_id}/modules/create",
                data={"unit_id": module_id},
                headers={"Origin": "http://test"},
            ),
            await client.get(f"/courses/{course_id}/modules/{module_id}/sections"),
            await client.post(f"/courses/{course_id}/modules/reorder", headers={"Origin": "http://test"}),
            await client.post(f"/courses/{course_id}/modules/{module_id}/delete", headers={"Origin": "http://test"}),
            await client.post(
                f"/courses/{course_id}/modules/{module_id}/sections/{section_id}/toggle",
                headers={"Origin": "http://test"},
            ),
            await client.get(f"/courses/{course_id}/members"),
            await client.post(
                f"/courses/{course_id}/members",
                data={"student_sub": "student-wave1"},
                headers={"Origin": "http://test"},
            ),
            await client.post(
                f"/courses/{course_id}/members/student-wave1/delete",
                headers={"Origin": "http://test"},
            ),
        ]
    async with await _client_with_session(student_session) as client:
        forbidden_response = await client.get(f"/courses/{course_id}/modules", follow_redirects=False)

    assert all(response.status_code == 410 for response in retired_responses)
    assert all(response.headers.get("Cache-Control") == "private, no-store" for response in retired_responses)
    assert forbidden_response.status_code == 303
    assert forbidden_response.headers.get("location") == "/"


@pytest.mark.anyio
async def test_removed_unit_entry_and_phase_entries_still_return_retirement_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = install_session_store(monkeypatch, main)
    teacher_session = _session_for(store, sub="teacher-unit-wave1", roles=["teacher"])
    student_session = _session_for(store, sub="student-unit-wave1", roles=["student"])
    unit_id = "11111111-1111-1111-1111-111111111111"
    phase_id = "22222222-2222-2222-2222-222222222222"

    async with await _client_with_session(teacher_session) as client:
        retired_responses = [
            await client.post("/units", data={"title": "Neu"}, headers={"Origin": "http://test"}),
            await client.get(f"/units/{unit_id}"),
            await client.get(f"/units/{unit_id}/edit"),
            await client.post(f"/units/{unit_id}/edit", data={"title": "Neu"}, headers={"Origin": "http://test"}),
            await client.post(
                f"/units/{unit_id}/modules",
                data={"title": "M", "phase_id": phase_id},
                headers={"Origin": "http://test"},
            ),
            await client.get(f"/units/{unit_id}/phases"),
            await client.post(f"/units/{unit_id}/phases", data={"title": "P"}, headers={"Origin": "http://test"}),
            await client.post(f"/units/{unit_id}/phases/reorder", headers={"Origin": "http://test"}),
        ]
    async with await _client_with_session(student_session) as client:
        forbidden_response = await client.get(f"/units/{unit_id}", follow_redirects=False)

    assert all(response.status_code == 410 for response in retired_responses)
    assert all(response.headers.get("Cache-Control") == "private, no-store" for response in retired_responses)
    assert forbidden_response.status_code == 303
    assert forbidden_response.headers.get("location") == "/"


@pytest.mark.anyio
async def test_removed_unit_module_and_modular_editor_entries_return_retirement_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = install_session_store(monkeypatch, main)
    teacher_session = _session_for(store, sub="teacher-unit-modular-wave1", roles=["teacher"])
    student_session = _session_for(store, sub="student-unit-modular-wave1", roles=["student"])
    unit_id = "11111111-1111-1111-1111-111111111111"
    module_id = "22222222-2222-2222-2222-222222222222"
    phase_id = "33333333-3333-3333-3333-333333333333"

    async with await _client_with_session(teacher_session) as client:
        retired_responses = [
            await client.get(f"/units/{unit_id}/modules/{module_id}"),
            await client.get(f"/units/{unit_id}/modules/{module_id}/panel"),
            await client.post(
                f"/units/{unit_id}/modular-editor/module/{module_id}/edges/delete",
                data={"from_module_id": module_id, "to_module_id": module_id},
                headers={"Origin": "http://test"},
            ),
            await client.post(
                f"/units/{unit_id}/modular-editor/module/{module_id}/settings",
                data={"required_prereq_count": "0"},
                headers={"Origin": "http://test"},
            ),
            await client.get(f"/units/{unit_id}/modular-editor/phase/new"),
            await client.post(
                f"/units/{unit_id}/modular-editor/phase/new",
                data={"title": "Phase"},
                headers={"Origin": "http://test"},
            ),
            await client.get(f"/units/{unit_id}/modular-editor/phase/{phase_id}/module/new"),
            await client.post(
                f"/units/{unit_id}/modular-editor/phase/{phase_id}/module/new",
                data={"title": "Modul"},
                headers={"Origin": "http://test"},
            ),
            await client.get(f"/units/{unit_id}/modular-editor/module/{module_id}/rename"),
            await client.post(
                f"/units/{unit_id}/modular-editor/module/{module_id}/rename",
                data={"title": "Modul"},
                headers={"Origin": "http://test"},
            ),
            await client.get(f"/units/{unit_id}/modular-editor/phase/{phase_id}/rename"),
            await client.post(
                f"/units/{unit_id}/modular-editor/phase/{phase_id}/rename",
                data={"title": "Phase"},
                headers={"Origin": "http://test"},
            ),
            await client.get(f"/units/{unit_id}/modular-editor/module/{module_id}/delete"),
            await client.post(
                f"/units/{unit_id}/modular-editor/module/{module_id}/delete",
                headers={"Origin": "http://test"},
            ),
            await client.get(f"/units/{unit_id}/modular-editor/phase/{phase_id}/delete"),
            await client.post(
                f"/units/{unit_id}/modular-editor/phase/{phase_id}/delete",
                headers={"Origin": "http://test"},
            ),
        ]
    async with await _client_with_session(student_session) as client:
        forbidden_response = await client.get(f"/units/{unit_id}/modules/{module_id}", follow_redirects=False)

    assert all(response.status_code == 410 for response in retired_responses)
    assert all(response.headers.get("Cache-Control") == "private, no-store" for response in retired_responses)
    assert forbidden_response.status_code == 303
    assert forbidden_response.headers.get("location") == "/"


@pytest.mark.anyio
async def test_removed_unit_section_material_and_task_entries_return_retirement_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = install_session_store(monkeypatch, main)
    teacher_session = _session_for(store, sub="teacher-unit-sections-wave1", roles=["teacher"])
    student_session = _session_for(store, sub="student-unit-sections-wave1", roles=["student"])
    unit_id = "11111111-1111-1111-1111-111111111111"
    section_id = "22222222-2222-2222-2222-222222222222"
    material_id = "33333333-3333-3333-3333-333333333333"
    task_id = "44444444-4444-4444-4444-444444444444"

    async with await _client_with_session(teacher_session) as client:
        retired_responses = [
            await client.get(f"/units/{unit_id}/sections/{section_id}"),
            await client.post(
                f"/units/{unit_id}/sections",
                data={"title": "Abschnitt"},
                headers={"Origin": "http://test"},
            ),
            await client.post(f"/units/{unit_id}/sections/reorder", headers={"Origin": "http://test"}),
            await client.post(
                f"/units/{unit_id}/sections/{section_id}/delete",
                headers={"Origin": "http://test"},
            ),
            await client.get(f"/units/{unit_id}/sections/{section_id}/materials/new"),
            await client.post(
                f"/units/{unit_id}/sections/{section_id}/materials/create",
                data={"title": "Material", "body_md": "Text"},
                headers={"Origin": "http://test"},
            ),
            await client.post(
                f"/units/{unit_id}/sections/{section_id}/materials/reorder",
                headers={"Origin": "http://test"},
            ),
            await client.post(
                f"/units/{unit_id}/sections/{section_id}/materials/upload-intent",
                data={"filename": "material.pdf", "mime_type": "application/pdf", "size_bytes": "12"},
                headers={"Origin": "http://test"},
            ),
            await client.post(
                f"/units/{unit_id}/sections/{section_id}/materials/finalize",
                data={"intent_id": "intent", "title": "Material", "sha256": "abc"},
                headers={"Origin": "http://test"},
            ),
            await client.get(f"/units/{unit_id}/sections/{section_id}/materials/{material_id}"),
            await client.post(
                f"/units/{unit_id}/sections/{section_id}/materials/{material_id}/update",
                data={"title": "Material", "body_md": "Text"},
                headers={"Origin": "http://test"},
            ),
            await client.post(
                f"/units/{unit_id}/sections/{section_id}/materials/{material_id}/delete",
                headers={"Origin": "http://test"},
            ),
            await client.get(f"/units/{unit_id}/sections/{section_id}/tasks/new"),
            await client.post(
                f"/units/{unit_id}/sections/{section_id}/tasks/create",
                data={"instruction_md": "Aufgabe", "criteria": ["Kriterium"]},
                headers={"Origin": "http://test"},
            ),
            await client.post(
                f"/units/{unit_id}/sections/{section_id}/tasks/reorder",
                headers={"Origin": "http://test"},
            ),
            await client.get(f"/units/{unit_id}/sections/{section_id}/tasks/{task_id}"),
            await client.post(
                f"/units/{unit_id}/sections/{section_id}/tasks/{task_id}/update",
                data={"instruction_md": "Aufgabe", "criteria": ["Kriterium"]},
                headers={"Origin": "http://test"},
            ),
            await client.post(
                f"/units/{unit_id}/sections/{section_id}/tasks/{task_id}/delete",
                headers={"Origin": "http://test"},
            ),
        ]
    async with await _client_with_session(student_session) as client:
        forbidden_response = await client.get(f"/units/{unit_id}/sections/{section_id}", follow_redirects=False)

    assert all(response.status_code == 410 for response in retired_responses)
    assert all(response.headers.get("Cache-Control") == "private, no-store" for response in retired_responses)
    assert forbidden_response.status_code == 303
    assert forbidden_response.headers.get("location") == "/"
