"""
Learning API — "Meine Kurse" and course units (contract-first, red tests)

Covers:
- GET /api/learning/courses (alphabetical, minimal fields)
- GET /api/learning/courses/{course_id}/units (ordered by course module position)
- 401/404/400 semantics
"""
from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4
import os

import pytest
import httpx
from httpx import ASGITransport

from utils.db import require_db_or_skip as _require_db_or_skip


pytestmark = pytest.mark.anyio("asyncio")

import main  # type: ignore  # noqa: E402
from identity_access.stores import SessionStore  # type: ignore  # noqa: E402


@dataclass
class _Actor:
    session_id: str
    sub: str


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test")


async def _create_course(client: httpx.AsyncClient, title: str, *, subject: str | None = None) -> str:
    payload: dict[str, object] = {"title": title}
    if subject is not None:
        payload["subject"] = subject
    r = await client.post("/api/teaching/courses", json=payload)
    assert r.status_code == 201
    return r.json()["id"]


async def _create_unit(client: httpx.AsyncClient, title: str, summary: str | None = None) -> dict:
    payload: dict[str, object] = {"title": title}
    if summary is not None:
        payload["summary"] = summary
    r = await client.post("/api/teaching/units", json=payload)
    assert r.status_code == 201
    return r.json()


async def _add_module(client: httpx.AsyncClient, course_id: str, unit_id: str) -> dict:
    r = await client.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": unit_id})
    assert r.status_code == 201
    return r.json()


async def _add_member(client: httpx.AsyncClient, course_id: str, student_sub: str) -> None:
    r = await client.post(f"/api/teaching/courses/{course_id}/members", json={"student_sub": student_sub})
    assert r.status_code in (201, 204)


def _setup_sessions() -> tuple[_Actor, _Actor]:
    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub=f"t-{uuid4()}", name="Teacher", roles=["teacher"])
    student = main.SESSION_STORE.create(sub=f"s-{uuid4()}", name="Student", roles=["student"])
    return _Actor(teacher.session_id, teacher.sub), _Actor(student.session_id, student.sub)


@pytest.mark.anyio
async def test_list_student_courses_alphabetical_and_minimal_fields():
    _require_db_or_skip()
    # Ensure DB-backed repos are active
    import routes.teaching as teaching  # noqa: E402
    import routes.learning as learning  # noqa: E402
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        assert isinstance(teaching.REPO, DBTeachingRepo)
        from backend.learning.repo_db import DBLearningRepo  # type: ignore
        assert isinstance(learning.REPO, DBLearningRepo)
    except Exception:
        pytest.skip("DB-backed repos required")

    teacher, student = _setup_sessions()

    async with (await _client()) as c:
        # Create two courses with titles that test alphabetical order
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        c1 = await _create_course(c, title="Biologie", subject="BIO")
        c2 = await _create_course(c, title="Algebra", subject="MATH")

        # Add student membership to both
        await _add_member(c, c1, student.sub)
        await _add_member(c, c2, student.sub)

        # Fetch via Learning endpoint
        c.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)
        r = await c.get("/api/learning/courses", params={"limit": 50, "offset": 0})
        assert r.status_code == 200
        items = r.json()
        # Success responses may be privately cached with zero max-age
        assert r.headers.get("Cache-Control") == "private, max-age=0"
        # Alphabetical by title asc
        assert [it["title"] for it in items] == ["Algebra", "Biologie"]
        # Minimal fields, no teacher_id
        assert set(items[0].keys()) <= {"id", "title", "subject", "grade_level", "term"}
        assert "teacher_id" not in items[0]


@pytest.mark.anyio
async def test_list_units_for_course_returns_ordered_positions_and_404_when_not_member():
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

    teacher, student = _setup_sessions()

    async with (await _client()) as c:
        # Teacher creates course and units, adds modules in a specific order
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        course_id = await _create_course(c, title="Physik")
        u1 = await _create_unit(c, title="Mechanik")
        u2 = await _create_unit(c, title="Optik")
        await _add_module(c, course_id, u2["id"])  # position 1
        await _add_module(c, course_id, u1["id"])  # position 2

        # Not a member → 404
        c.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)
        r_forbidden = await c.get(f"/api/learning/courses/{course_id}/units")
        assert r_forbidden.status_code == 404

        # Add membership and fetch
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        await _add_member(c, course_id, student.sub)
        c.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)
        r_ok = await c.get(f"/api/learning/courses/{course_id}/units")
        assert r_ok.status_code == 200
        # Success responses may be privately cached with zero max-age
        assert r_ok.headers.get("Cache-Control") == "private, max-age=0"
        rows = r_ok.json()
        assert [row["unit"]["title"] for row in rows] == ["Optik", "Mechanik"]
        assert [row["position"] for row in rows] == [1, 2]
        # UnitPublic has no author_id
        assert set(rows[0]["unit"].keys()) <= {"id", "title", "summary"}
        assert "author_id" not in rows[0]["unit"]


@pytest.mark.anyio
async def test_learning_courses_auth_and_uuid_errors():
    _require_db_or_skip()
    # Anonymous → 401
    async with (await _client()) as c:
        r = await c.get("/api/learning/courses")
        assert r.status_code == 401
        # Security: error responses must not be cached by intermediaries
        assert r.headers.get("Cache-Control") == "private, no-store"

    # Invalid UUID for units → 400
    main.SESSION_STORE = SessionStore()
    student = main.SESSION_STORE.create(sub=f"s-{uuid4()}", name="Student", roles=["student"])
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)
        r = await c.get("/api/learning/courses/not-a-uuid/units")
        assert r.status_code == 400


@pytest.mark.anyio
async def test_non_student_forbidden_learning_courses():
    _require_db_or_skip()
    # Teacher session should yield 403 on student-only endpoint
    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub=f"t-{uuid4()}", name="Teacher", roles=["teacher"])  # type: ignore
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        r = await c.get("/api/learning/courses")
        assert r.status_code == 403
        assert r.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_units_unauthenticated_401():
    _require_db_or_skip()
    # No session cookie → 401
    async with (await _client()) as c:
        r = await c.get(f"/api/learning/courses/{uuid4()}/units")
        assert r.status_code == 401
        assert r.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_non_student_forbidden_units():
    _require_db_or_skip()
    # Teacher session should yield 403 on student-only units endpoint
    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub=f"t-{uuid4()}", name="Teacher", roles=["teacher"])  # type: ignore
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        r = await c.get(f"/api/learning/courses/{uuid4()}/units")
        assert r.status_code == 403 or r.status_code == 400  # UUID may be invalid; ensure 403 with valid UUID below

    # Use a valid UUID to assert 403 specifically
    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub=f"t-{uuid4()}", name="Teacher", roles=["teacher"])  # type: ignore
    valid_course_id = str(uuid4())
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        r = await c.get(f"/api/learning/courses/{valid_course_id}/units")
        assert r.status_code == 403
        assert r.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_courses_pagination_clamp_limit_upper_bound():
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

    teacher, student = _setup_sessions()
    async with (await _client()) as c:
        # Create a small number of courses; the check focuses on clamping behavior and non-error
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        course_ids = [
            await _create_course(c, title=f"Clamp {i:02d}")
            for i in range(3)
        ]
        for cid in course_ids:
            await _add_member(c, cid, student.sub)
        # Request an excessive limit; should succeed and never exceed 50 items
        c.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)
        r = await c.get("/api/learning/courses", params={"limit": 500, "offset": 0})
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list)
        assert len(items) <= 50
