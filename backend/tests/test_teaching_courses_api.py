"""
Teaching API — Course management (contract-first, TDD)

This test drives the minimal implementation for creating and listing courses.
It assumes authentication via the existing session middleware and requires the
"teacher" role for course creation.
"""

from __future__ import annotations

import importlib
from uuid import uuid4

import httpx
import pytest
from httpx import ASGITransport

from backend.tests.runtime_auth_helpers import install_session_store
from backend.tests.utils.teaching import require_teaching_db_repo

pytestmark = [pytest.mark.anyio("asyncio"), pytest.mark.db_write]
main = importlib.import_module("backend.web.main")


async def _client():
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test", headers={"Origin": "http://test"})


@pytest.mark.anyio
async def test_teacher_can_create_and_list_own_courses(monkeypatch: pytest.MonkeyPatch):
    # Ensure in-memory session store for this test run
    store = install_session_store(monkeypatch, main)
    # Require DB-backed repo
    require_teaching_db_repo()
    # Arrange: teacher session
    teacher_sub = f"teacher-courses-{uuid4()}"
    sess = store.create(sub=teacher_sub, name="Lehrkraft", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", sess.session_id)

        # Act: create course
        create = await client.post(
            "/api/teaching/courses",
            json={"title": "Biologie Q1", "subject": "Biologie", "grade_level": "Q1", "term": "2025-1", "school_year_start": 2025},
        )

        # Assert: created
        assert create.status_code == 201
        body = create.json()
        assert body.get("title") == "Biologie Q1"
        assert body.get("teacher_id") == teacher_sub
        assert body.get("id")

        # Act: list courses
        lst = await client.get("/api/teaching/courses?limit=10&offset=0")
        assert lst.status_code == 200
        arr = lst.json()
        assert isinstance(arr, list)
        assert any(c.get("id") == body.get("id") for c in arr)


@pytest.mark.anyio
async def test_create_course_invalid_title_returns_400(monkeypatch: pytest.MonkeyPatch):
    """Contract: invalid title yields 400 (bad_request), not 500.

    Uses DB-backed repo to exercise ValueError from repo and verifies the web
    adapter maps it to a 400 response as specified in openapi.yml.
    """
    # Ensure in-memory session store
    store = install_session_store(monkeypatch, main)
    # Require DB-backed repo
    require_teaching_db_repo()

    teacher = store.create(sub="teacher-bad-title", name="Owner", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", teacher.session_id)
        # Empty title should trigger invalid_title -> 400 bad_request
        resp = await client.post("/api/teaching/courses", json={"title": "   ", "subject": "Testfach", "grade_level": "10", "school_year_start": 2026})
        assert resp.status_code == 400
        body = resp.json()
        assert body.get("error") == "bad_request"
        assert body.get("detail") == "invalid_input"


@pytest.mark.anyio
async def test_create_course_requires_complete_new_metadata(monkeypatch: pytest.MonkeyPatch):
    """New courses must not enter the catalog without lifecycle metadata."""
    teaching = importlib.import_module("backend.web.routes.teaching")
    store = install_session_store(monkeypatch, main)
    repo = teaching._Repo()  # type: ignore[attr-defined]
    monkeypatch.setattr(teaching, "REPO", repo, raising=False)
    teacher = store.create(sub="teacher-metadata-required", name="Owner", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", teacher.session_id)
        response = await client.post("/api/teaching/courses", json={"title": "Unvollständig"})

    assert response.status_code == 400
    assert response.json()["detail"] == "course_metadata_incomplete"


@pytest.mark.anyio
async def test_create_course_invalid_title_in_memory_repo(monkeypatch: pytest.MonkeyPatch):
    """Ensure fallback repo mirrors DB validation for blank titles."""
    teaching = importlib.import_module("backend.web.routes.teaching")
    store = install_session_store(monkeypatch, main)
    # Force fallback by swapping repo with fresh in-memory implementation.
    repo = teaching._Repo()  # type: ignore[attr-defined]
    monkeypatch.setattr(teaching, "REPO", repo, raising=False)
    monkeypatch.setattr(
        teaching,
        "MATERIALS_SERVICE",
        teaching.MaterialsService(repo, settings=teaching.MATERIAL_FILE_SETTINGS),
        raising=False,
    )

    teacher = store.create(sub="teacher-memory", name="Owner", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", teacher.session_id)
        resp = await client.post("/api/teaching/courses", json={"title": "   "})
        assert resp.status_code == 400
        body = resp.json()
        assert body.get("error") == "bad_request"
        assert body.get("detail") == "invalid_input"



@pytest.mark.anyio
async def test_student_cannot_create_course_forbidden(monkeypatch: pytest.MonkeyPatch):
    store = install_session_store(monkeypatch, main)
    # Arrange: student session
    sess = store.create(sub="student-1", name="Max Musterschüler", roles=["student"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", sess.session_id)
        resp = await client.post("/api/teaching/courses", json={"title": "Test"})
        assert resp.status_code == 403
        data = resp.json()
        assert data.get("error") == "forbidden"
        assert resp.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_manage_members_add_list_remove_with_owner_checks(monkeypatch: pytest.MonkeyPatch):
    store = install_session_store(monkeypatch, main)
    # Require DB-backed repo
    require_teaching_db_repo()
    # Arrange: two teachers and one student
    t1 = store.create(sub="teacher-A", name="Frau A", roles=["teacher"])
    t2 = store.create(sub="teacher-B", name="Herr B", roles=["teacher"])

    # Monkeypatch name resolver in teaching router to avoid external dependency
    def fake_resolver_bulk(ids: list[str]) -> dict[str, str]:
        mapping = {"student-1": "Max Musterschüler", "student-2": "Mia Muster"}
        return {i: mapping.get(i, f"Name:{i}") for i in ids}

    members = importlib.import_module("backend.web.routes.teaching_course_members")
    monkeypatch.setattr(members, "_resolve_student_names_runtime", fake_resolver_bulk)

    # Teacher A creates a course
    async with (await _client()) as client:
        client.cookies.set("gustav_session", t1.session_id)
        c = await client.post("/api/teaching/courses", json={"title": "Mathe 10", "subject": "Mathematik", "grade_level": "10", "school_year_start": 2026})
        assert c.status_code == 201
        course_id = c.json()["id"]

        # Initially: no members
        r0 = await client.get(f"/api/teaching/courses/{course_id}/members")
        assert r0.status_code == 200
        assert r0.json() == []

        # Add member
        add1 = await client.post(f"/api/teaching/courses/{course_id}/members", json={"student_sub": "student-1"})
        assert add1.status_code == 201
        # Idempotent add
        add2 = await client.post(f"/api/teaching/courses/{course_id}/members", json={"student_sub": "student-1"})
        assert add2.status_code == 204

        # List with names + joined_at
        lst = await client.get(f"/api/teaching/courses/{course_id}/members")
        assert lst.status_code == 200
        arr = lst.json()
        assert len(arr) == 1
        assert arr[0]["sub"] == "student-1"
        assert arr[0]["name"] == "Max Musterschüler"
        assert "joined_at" in arr[0]

        # Remove member idempotent
        d1 = await client.delete(f"/api/teaching/courses/{course_id}/members/student-1")
        assert d1.status_code == 204
        assert (d1.text or "") == ""
        d2 = await client.delete(f"/api/teaching/courses/{course_id}/members/student-1")
        assert d2.status_code == 204
        assert (d2.text or "") == ""

    # Non-owner teacher must be forbidden to manage or view members
    async with (await _client()) as client:
        client.cookies.set("gustav_session", t2.session_id)
        resp1 = await client.get(f"/api/teaching/courses/{course_id}/members")
        assert resp1.status_code == 403
        resp2 = await client.post(f"/api/teaching/courses/{course_id}/members", json={"student_sub": "student-2"})
        assert resp2.status_code == 403
        resp3 = await client.delete(f"/api/teaching/courses/{course_id}/members/student-2")
        assert resp3.status_code == 403


@pytest.mark.anyio
async def test_add_member_missing_student_sub_returns_400(monkeypatch: pytest.MonkeyPatch):
    store = install_session_store(monkeypatch, main)
    require_teaching_db_repo()

    owner = store.create(sub="teacher-member-missing", name="Owner", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", owner.session_id)
        created = await client.post("/api/teaching/courses", json={"title": "Physik 10", "subject": "Physik", "grade_level": "10", "school_year_start": 2026})
        assert created.status_code == 201
        course_id = created.json()["id"]

        resp = await client.post(f"/api/teaching/courses/{course_id}/members", json={})
        assert resp.status_code == 400
        body = resp.json()
        assert body.get("error") == "bad_request"
        assert body.get("detail") == "student_sub_required"


@pytest.mark.anyio
async def test_student_listing_includes_member_courses(monkeypatch: pytest.MonkeyPatch):
    store = install_session_store(monkeypatch, main)
    # Teacher creates course and adds student
    # Require DB-backed repo
    require_teaching_db_repo()
    t = store.create(sub=f"teacher-listing-{uuid4()}", name="Lehrkraft", roles=["teacher"])
    s = store.create(sub=f"student-listing-{uuid4()}", name="Schüler", roles=["student"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", t.session_id)
        c = await client.post("/api/teaching/courses", json={"title": "Physik 9", "subject": "Physik", "grade_level": "9", "school_year_start": 2026})
        assert c.status_code == 201
        course_id = c.json()["id"]
        a = await client.post(f"/api/teaching/courses/{course_id}/members", json={"student_sub": s.sub})
        assert a.status_code in (201, 204)

    # As student: should see the course in listing
    async with (await _client()) as client:
        client.cookies.set("gustav_session", s.session_id)
        lst = await client.get("/api/teaching/courses?limit=10&offset=0")
        assert lst.status_code == 200
        ids = [c.get("id") for c in lst.json()]
        assert course_id in ids


@pytest.mark.anyio
async def test_list_courses_default_limit_matches_contract_10(monkeypatch: pytest.MonkeyPatch):
    """GET /api/teaching/courses without `limit` must default to 10."""
    teaching = importlib.import_module("backend.web.routes.teaching")
    store = install_session_store(monkeypatch, main)
    # Isolate behavior from DB state.
    teaching.set_repo(teaching._Repo())  # type: ignore[attr-defined]

    teacher = store.create(sub="teacher-default-limit-10", name="T", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", teacher.session_id)
        for i in range(12):
            r = await client.post("/api/teaching/courses", json={"title": f"Kurs {i + 1}", "subject": "Testfach", "grade_level": "10", "school_year_start": 2026})
            assert r.status_code == 201, r.text

        listed = await client.get("/api/teaching/courses")
        assert listed.status_code == 200
        payload = listed.json()
        assert isinstance(payload, list)
        assert len(payload) == 10
