"""
Learning API — "Meine Kurse" and course units (contract-first, red tests)

Covers:
- GET /api/learning/courses (alphabetical, minimal fields)
- GET /api/learning/courses/{course_id}/units (ordered by course module position)
- 401/404/400 semantics
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from uuid import uuid4

import httpx
import psycopg
import pytest
from httpx import ASGITransport

from backend.tests.utils.db import is_safe_db_test_dsn
from backend.tests.utils.db import require_db_or_skip as _require_db_or_skip
from backend.web.main import SESSION_COOKIE_NAME, create_app

pytestmark = [pytest.mark.anyio("asyncio"), pytest.mark.db_write]


@pytest.fixture
def app():
    """Own the authentication state and remove only records created by this test."""
    _require_db_or_skip()
    claims = {}
    created = create_app(access_token_verifier=lambda token, cfg: claims)
    created.state.test_claims = claims
    created.state.test_course_ids = []
    created.state.test_unit_ids = []
    yield created
    dsn = os.environ["RLS_TEST_SERVICE_DSN"]
    assert is_safe_db_test_dsn(dsn)
    with psycopg.connect(dsn) as conn:
        conn.execute(
            "delete from public.courses where id = any(%s::uuid[])",
            (created.state.test_course_ids,),
        )
        conn.execute(
            "delete from public.units where id = any(%s::uuid[])", (created.state.test_unit_ids,)
        )


@dataclass
class _Actor:
    session_id: str
    sub: str


async def _client(app) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Origin": "http://test"},
    )


async def _create_course(
    client: httpx.AsyncClient, app, title: str, *, subject: str | None = None
) -> str:
    payload: dict[str, object] = {
        "title": title,
        "subject": subject or "Testfach",
        "grade_level": "10",
        "school_year_start": 2026,
    }
    r = await client.post("/api/teaching/courses", json=payload)
    assert r.status_code == 201
    app.state.test_course_ids.append(r.json()["id"])
    return r.json()["id"]


async def _create_unit(
    client: httpx.AsyncClient, app, title: str, summary: str | None = None
) -> dict:
    payload: dict[str, object] = {"title": title}
    if summary is not None:
        payload["summary"] = summary
    r = await client.post("/api/teaching/units", json=payload)
    assert r.status_code == 201
    app.state.test_unit_ids.append(r.json()["id"])
    return r.json()


async def _add_module(client: httpx.AsyncClient, course_id: str, unit_id: str) -> dict:
    r = await client.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": unit_id})
    assert r.status_code == 201
    return r.json()


async def _add_member(client: httpx.AsyncClient, course_id: str, student_sub: str) -> None:
    r = await client.post(
        f"/api/teaching/courses/{course_id}/members", json={"student_sub": student_sub}
    )
    assert r.status_code in (201, 204)


def _setup_sessions(app) -> tuple[_Actor, _Actor]:
    store = app.state.runtime.session_store
    teacher = store.create(sub=f"t-{uuid4()}", name="Teacher", roles=["teacher"])
    student = store.create(sub=f"s-{uuid4()}", name="Student", roles=["student"])
    return _Actor(teacher.session_id, teacher.sub), _Actor(student.session_id, student.sub)


@pytest.mark.anyio
async def test_list_student_courses_alphabetical_and_minimal_fields(app):
    _require_db_or_skip()

    teacher, student = _setup_sessions(app)

    async with await _client(app) as c:
        # Create two courses with titles that test alphabetical order
        c.cookies.set(SESSION_COOKIE_NAME, teacher.session_id)
        c1 = await _create_course(c, app, title="Biologie", subject="BIO")
        c2 = await _create_course(c, app, title="Algebra", subject="MATH")

        # Add student membership to both
        await _add_member(c, c1, student.sub)
        await _add_member(c, c2, student.sub)

        # Fetch via Learning endpoint
        c.cookies.set(SESSION_COOKIE_NAME, student.session_id)
        r = await c.get("/api/learning/courses", params={"limit": 50, "offset": 0})
        assert r.status_code == 200
        items = r.json()
        # Security: success responses must not be stored by intermediaries or browser caches
        assert r.headers.get("Cache-Control") == "private, no-store"
        # Alphabetical by title asc
        assert [it["title"] for it in items] == ["Algebra", "Biologie"]
        # Minimal fields, no teacher_id
        assert set(items[0].keys()) <= {
            "id",
            "title",
            "subject",
            "grade_level",
            "term",
            "school_year_start",
            "status",
            "membership_status",
        }
        assert "teacher_id" not in items[0]


@pytest.mark.anyio
async def test_list_units_for_course_returns_ordered_positions_and_404_when_not_member(app):
    _require_db_or_skip()

    teacher, student = _setup_sessions(app)

    async with await _client(app) as c:
        # Teacher creates course and units, adds modules in a specific order
        c.cookies.set(SESSION_COOKIE_NAME, teacher.session_id)
        course_id = await _create_course(c, app, title="Physik")
        u1 = await _create_unit(c, app, title="Mechanik")
        u2 = await _create_unit(c, app, title="Optik")
        await _add_module(c, course_id, u2["id"])  # position 1
        await _add_module(c, course_id, u1["id"])  # position 2

        # Not a member → 404
        c.cookies.set(SESSION_COOKIE_NAME, student.session_id)
        r_forbidden = await c.get(f"/api/learning/courses/{course_id}/units")
        assert r_forbidden.status_code == 404
        # Contract/Security: errors are private and not cacheable
        assert r_forbidden.headers.get("Cache-Control") == "private, no-store"
        # Error payload should not leak details beyond a generic not_found
        assert (r_forbidden.json() or {}).get("error") == "not_found"

        # Add membership and fetch
        c.cookies.set(SESSION_COOKIE_NAME, teacher.session_id)
        await _add_member(c, course_id, student.sub)
        c.cookies.set(SESSION_COOKIE_NAME, student.session_id)
        r_ok = await c.get(f"/api/learning/courses/{course_id}/units")
        assert r_ok.status_code == 200
        # Security: success responses must not be stored by intermediaries or browser caches
        assert r_ok.headers.get("Cache-Control") == "private, no-store"
        assert [(row["unit"]["id"], row["position"]) for row in r_ok.json()] == [
            (u2["id"], 1),
            (u1["id"], 2),
        ]


async def test_home_and_courses_preserve_current_past_and_revoked_membership(app):
    teacher, student = _setup_sessions(app)
    async with await _client(app) as client:
        client.cookies.set(SESSION_COOKIE_NAME, teacher.session_id)
        active, archived, former, foreign = [
            await _create_course(client, app, title=title)
            for title in ("Aktuell", "Archiviert", "Beendet", "Fremd")
        ]
        for course_id in (active, archived, former):
            await _add_member(client, course_id, student.sub)
        assert (await client.post(f"/api/teaching/courses/{archived}/archive")).status_code == 200
        assert (
            await client.delete(f"/api/teaching/courses/{former}/members/{student.sub}")
        ).status_code == 204

        client.cookies.set(SESSION_COOKIE_NAME, student.session_id)
        app.state.test_claims.update({"sub": student.sub, "realm_access": {"roles": ["student"]}})
        response = await client.get(
            "/api/learning/views/learner-home", headers={"Authorization": "Bearer test.jwt"}
        )
        assert response.status_code == 200
        home = response.json()
        assert [row["id"] for row in home["current_courses"]] == [active]
        assert [row["id"] for row in home["past_courses"]] == [archived, former]
        assert all(row["href"].endswith("/archive") for row in home["past_courses"])
        current = await client.get("/api/learning/courses")
        past = await client.get("/api/learning/courses?scope=past")
        assert [row["id"] for row in current.json()] == [active]
        assert [row["id"] for row in past.json()] == [archived, former]
        for course_id in (former, foreign, str(uuid4())):
            denied = await client.get(f"/api/learning/courses/{course_id}/units")
            assert denied.status_code == 404
            assert denied.json() == {"error": "not_found"}
            assert denied.headers["Cache-Control"] == "private, no-store"


@pytest.mark.anyio
async def test_list_student_courses_empty_list(app):
    _require_db_or_skip()

    # Student with no memberships should get an empty list
    store = app.state.runtime.session_store
    student = store.create(sub=f"s-{uuid4()}", name="Student", roles=["student"])
    async with await _client(app) as c:
        c.cookies.set(SESSION_COOKIE_NAME, student.session_id)
        r = await c.get("/api/learning/courses")
        assert r.status_code == 200
        assert r.headers.get("Cache-Control") == "private, no-store"
        assert r.json() == []


@pytest.mark.anyio
async def test_courses_pagination_clamp_limit_and_offset(app):
    _require_db_or_skip()

    teacher, student = _setup_sessions(app)
    async with await _client(app) as c:
        # Create a few courses and add membership
        c.cookies.set(SESSION_COOKIE_NAME, teacher.session_id)
        cids = [
            await _create_course(c, app, title="A"),
            await _create_course(c, app, title="B"),
            await _create_course(c, app, title="C"),
        ]
        for cid in cids:
            await _add_member(c, cid, student.sub)

        # Ask for an excessive limit and negative offset; expect clamp (no error)
        c.cookies.set(SESSION_COOKIE_NAME, student.session_id)
        r = await c.get("/api/learning/courses", params={"limit": 1000, "offset": -10})
        assert r.status_code == 200
        items = r.json()
        # We only created 3 items; clamping should not truncate them
        assert len(items) == 3
        # Still alphabetically ordered
        assert [it["title"] for it in items] == ["A", "B", "C"]
        assert r.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_learning_courses_auth_and_uuid_errors(app):
    _require_db_or_skip()
    # Anonymous → 401
    async with await _client(app) as c:
        r = await c.get("/api/learning/courses")
        assert r.status_code == 401
        # Security: error responses must not be cached by intermediaries
        assert r.headers.get("Cache-Control") == "private, no-store"

    # Invalid UUID for units → 400
    store = app.state.runtime.session_store
    student = store.create(sub=f"s-{uuid4()}", name="Student", roles=["student"])
    async with await _client(app) as c:
        c.cookies.set(SESSION_COOKIE_NAME, student.session_id)
        r = await c.get("/api/learning/courses/not-a-uuid/units")
        assert r.status_code == 400


@pytest.mark.anyio
async def test_non_student_forbidden_learning_courses(app):
    _require_db_or_skip()
    # Teacher session should yield 403 on student-only endpoint
    store = app.state.runtime.session_store
    teacher = store.create(sub=f"t-{uuid4()}", name="Teacher", roles=["teacher"])
    async with await _client(app) as c:
        c.cookies.set(SESSION_COOKIE_NAME, teacher.session_id)
        r = await c.get("/api/learning/courses")
        assert r.status_code == 403
        assert r.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_units_unauthenticated_401(app):
    _require_db_or_skip()
    # No session cookie → 401
    async with await _client(app) as c:
        r = await c.get(f"/api/learning/courses/{uuid4()}/units")
        assert r.status_code == 401
        assert r.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_non_student_forbidden_units(app):
    _require_db_or_skip()
    # Teacher session should yield 403 on student-only units endpoint
    store = app.state.runtime.session_store
    teacher = store.create(sub=f"t-{uuid4()}", name="Teacher", roles=["teacher"])
    async with await _client(app) as c:
        c.cookies.set(SESSION_COOKIE_NAME, teacher.session_id)
        r = await c.get(f"/api/learning/courses/{uuid4()}/units")
        assert (
            r.status_code == 403 or r.status_code == 400
        )  # UUID may be invalid; ensure 403 with valid UUID below

    # Use a valid UUID to assert 403 specifically
    store = app.state.runtime.session_store
    teacher = store.create(sub=f"t-{uuid4()}", name="Teacher", roles=["teacher"])
    valid_course_id = str(uuid4())
    async with await _client(app) as c:
        c.cookies.set(SESSION_COOKIE_NAME, teacher.session_id)
        r = await c.get(f"/api/learning/courses/{valid_course_id}/units")
        assert r.status_code == 403
        assert r.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_courses_pagination_clamp_limit_upper_bound(app):
    _require_db_or_skip()

    teacher, student = _setup_sessions(app)
    async with await _client(app) as c:
        # Create a small number of courses; the check focuses on clamping behavior and non-error
        c.cookies.set(SESSION_COOKIE_NAME, teacher.session_id)
        course_ids = [await _create_course(c, app, title=f"Clamp {i:02d}") for i in range(3)]
        for cid in course_ids:
            await _add_member(c, cid, student.sub)
        # Request an excessive limit; should succeed and never exceed 100 items per contract
        c.cookies.set(SESSION_COOKIE_NAME, student.session_id)
        r = await c.get("/api/learning/courses", params={"limit": 500, "offset": 0})
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list)
        assert len(items) <= 100
