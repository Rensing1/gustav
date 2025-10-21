"""
Teaching API — Course management (contract-first, TDD)

This test drives the minimal implementation for creating and listing courses.
It assumes authentication via the existing session middleware and requires the
"teacher" role for course creation.
"""

from __future__ import annotations

import pytest
import httpx
from httpx import ASGITransport
from pathlib import Path
import sys


pytestmark = pytest.mark.anyio("asyncio")


REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))
import main  # type: ignore
from identity_access.stores import SessionStore  # type: ignore
import os


def _require_db_or_skip():
    dsn = os.getenv("DATABASE_URL") or ""
    try:
        import psycopg  # type: ignore
        with psycopg.connect(dsn, connect_timeout=1):
            return
    except Exception:
        pytest.skip("Database not reachable; ensure migrations applied and DATABASE_URL set")


async def _client():
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test")


@pytest.mark.anyio
async def test_teacher_can_create_and_list_own_courses():
    # Ensure in-memory session store for this test run
    main.SESSION_STORE = SessionStore()
    # Require DB-backed repo
    import routes.teaching as teaching
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")
    _require_db_or_skip()
    # Arrange: teacher session
    sess = main.SESSION_STORE.create(sub="teacher-1", name="Frau Lehrerin", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", sess.session_id)

        # Act: create course
        create = await client.post(
            "/api/teaching/courses",
            json={"title": "Biologie Q1", "subject": "Biologie", "grade_level": "Q1", "term": "2025-1"},
        )

        # Assert: created
        assert create.status_code == 201
        body = create.json()
        assert body.get("title") == "Biologie Q1"
        assert body.get("teacher_id") == "teacher-1"
        assert body.get("id")

        # Act: list courses
        lst = await client.get("/api/teaching/courses?limit=10&offset=0")
        assert lst.status_code == 200
        arr = lst.json()
        assert isinstance(arr, list)
        assert any(c.get("id") == body.get("id") for c in arr)


@pytest.mark.anyio
async def test_create_course_invalid_title_returns_400():
    """Contract: invalid title yields 400 (bad_request), not 500.

    Uses DB-backed repo to exercise ValueError from repo and verifies the web
    adapter maps it to a 400 response as specified in openapi.yml.
    """
    # Ensure in-memory session store
    main.SESSION_STORE = SessionStore()
    # Require DB-backed repo
    import routes.teaching as teaching
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")
    _require_db_or_skip()

    teacher = main.SESSION_STORE.create(sub="teacher-bad-title", name="Owner", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", teacher.session_id)
        # Empty title should trigger invalid_title -> 400 bad_request
        resp = await client.post("/api/teaching/courses", json={"title": "   "})
        assert resp.status_code == 400
        body = resp.json()
        assert body.get("error") == "bad_request"
        assert body.get("detail") == "invalid_input"


@pytest.mark.anyio
async def test_student_cannot_create_course_forbidden():
    main.SESSION_STORE = SessionStore()
    # Arrange: student session
    sess = main.SESSION_STORE.create(sub="student-1", name="Max Musterschüler", roles=["student"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", sess.session_id)
        resp = await client.post("/api/teaching/courses", json={"title": "Test"})
        assert resp.status_code == 403
        data = resp.json()
        assert data.get("error") == "forbidden"


@pytest.mark.anyio
async def test_manage_members_add_list_remove_with_owner_checks(monkeypatch: pytest.MonkeyPatch):
    main.SESSION_STORE = SessionStore()
    # Require DB-backed repo
    import routes.teaching as teaching
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")
    _require_db_or_skip()
    # Arrange: two teachers and one student
    t1 = main.SESSION_STORE.create(sub="teacher-A", name="Frau A", roles=["teacher"])
    t2 = main.SESSION_STORE.create(sub="teacher-B", name="Herr B", roles=["teacher"])

    # Monkeypatch name resolver in teaching router to avoid external dependency
    import routes.teaching as teaching  # patch the module used by main

    def fake_resolver_bulk(ids: list[str]) -> dict[str, str]:
        mapping = {"student-1": "Max Musterschüler", "student-2": "Mia Muster"}
        return {i: mapping.get(i, f"Name:{i}") for i in ids}

    monkeypatch.setattr(teaching, "resolve_student_names", fake_resolver_bulk, raising=False)

    # Teacher A creates a course
    async with (await _client()) as client:
        client.cookies.set("gustav_session", t1.session_id)
        c = await client.post("/api/teaching/courses", json={"title": "Mathe 10"})
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
    main.SESSION_STORE = SessionStore()
    import routes.teaching as teaching
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")
    _require_db_or_skip()

    owner = main.SESSION_STORE.create(sub="teacher-member-missing", name="Owner", roles=["teacher"])

    def fake_resolver(ids: list[str]) -> dict[str, str]:
        return {sid: f"Name:{sid}" for sid in ids}

    monkeypatch.setattr(teaching, "resolve_student_names", fake_resolver, raising=False)

    async with (await _client()) as client:
        client.cookies.set("gustav_session", owner.session_id)
        created = await client.post("/api/teaching/courses", json={"title": "Physik 10"})
        assert created.status_code == 201
        course_id = created.json()["id"]

        resp = await client.post(f"/api/teaching/courses/{course_id}/members", json={})
        assert resp.status_code == 400
        body = resp.json()
        assert body.get("error") == "bad_request"
        assert body.get("detail") == "student_sub_required"


@pytest.mark.anyio
async def test_student_listing_includes_member_courses(monkeypatch: pytest.MonkeyPatch):
    main.SESSION_STORE = SessionStore()
    # Teacher creates course and adds student
    # Require DB-backed repo
    import routes.teaching as teaching
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")
    _require_db_or_skip()
    t = main.SESSION_STORE.create(sub="teacher-X", name="Lehrkraft X", roles=["teacher"])
    s = main.SESSION_STORE.create(sub="student-X", name="Schüler X", roles=["student"])

    # monkeypatch resolver for completeness (not used by listing)
    import routes.teaching as teaching

    def fake_resolver_bulk(ids: list[str]) -> dict[str, str]:
        return {i: f"Name:{i}" for i in ids}

    monkeypatch.setattr(teaching, "resolve_student_names", fake_resolver_bulk, raising=False)

    async with (await _client()) as client:
        client.cookies.set("gustav_session", t.session_id)
        c = await client.post("/api/teaching/courses", json={"title": "Physik 9"})
        assert c.status_code == 201
        course_id = c.json()["id"]
        a = await client.post(f"/api/teaching/courses/{course_id}/members", json={"student_sub": "student-X"})
        assert a.status_code in (201, 204)

    # As student: should see the course in listing
    async with (await _client()) as client:
        client.cookies.set("gustav_session", s.session_id)
        lst = await client.get("/api/teaching/courses?limit=10&offset=0")
        assert lst.status_code == 200
        ids = [c.get("id") for c in lst.json()]
        assert course_id in ids
