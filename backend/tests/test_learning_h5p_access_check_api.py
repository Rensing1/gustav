"""
Learning API — H5P content access-check (student scope, fail-closed)

Contract (BDD):
    Given a student enrolled and a released H5P task exists
    When GET /api/learning/courses/{course_id}/h5p/contents/{content_id}/access
    Then 204 No Content

    Given a student is not a member (or content not released)
    When GET access-check
    Then 404 Not Found (fail-closed, leak-minimizing)
"""

from __future__ import annotations

import httpx
import pytest
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


async def _prepare_released_h5p_task(*, content_id: str = "1") -> dict:
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
    teacher = main.SESSION_STORE.create(sub="t-h5p-access", name="Teacher", roles=["teacher"])  # type: ignore
    student = main.SESSION_STORE.create(sub="s-h5p-access", name="Student", roles=["student"])  # type: ignore
    outsider = main.SESSION_STORE.create(sub="s-h5p-outsider", name="Outsider", roles=["student"])  # type: ignore

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)

        course = await c.post("/api/teaching/courses", json={"title": "Kurs H5P Access"})
        assert course.status_code == 201
        course_id = course.json()["id"]

        unit = (await c.post("/api/teaching/units", json={"title": "Unit"})).json()
        section = (await c.post(f"/api/teaching/units/{unit['id']}/sections", json={"title": "Abschnitt"})).json()

        task = (
            await c.post(
                f"/api/teaching/units/{unit['id']}/sections/{section['id']}/tasks",
                json={
                    "instruction_md": "H5P Aufgabe (placeholder; not shown in UI).",
                    "criteria": [],
                    "h5p": {"content_id": content_id, "display_options": {}},
                },
            )
        ).json()

        module = (
            await c.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": unit["id"]})
        ).json()

        r_release = await c.patch(
            f"/api/teaching/courses/{course_id}/modules/{module['id']}/sections/{section['id']}/visibility",
            json={"visible": True},
            headers={"Origin": "http://test"},
        )
        assert r_release.status_code == 200

        r_member = await c.post(f"/api/teaching/courses/{course_id}/members", json={"student_sub": student.sub})
        assert r_member.status_code in (201, 204)

    return {
        "teacher": teacher,
        "student": student,
        "outsider": outsider,
        "course_id": course_id,
        "content_id": content_id,
        "task_id": task["id"],
    }


@pytest.mark.anyio
async def test_learning_h5p_access_204_for_enrolled_student_and_released_task() -> None:
    fx = await _prepare_released_h5p_task()
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, fx["student"].session_id)
        r = await c.get(
            f"/api/learning/courses/{fx['course_id']}/h5p/contents/{fx['content_id']}/access"
        )
        assert r.status_code == 204
        assert r.headers.get("Cache-Control") == "private, no-store"
        assert (r.text or "") == ""


@pytest.mark.anyio
async def test_learning_h5p_access_404_for_student_not_member() -> None:
    fx = await _prepare_released_h5p_task()
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, fx["outsider"].session_id)
        r = await c.get(
            f"/api/learning/courses/{fx['course_id']}/h5p/contents/{fx['content_id']}/access"
        )
        assert r.status_code == 404
        assert r.headers.get("Cache-Control") == "private, no-store"
        assert (r.json() or {}).get("error") == "not_found"


@pytest.mark.anyio
async def test_learning_h5p_access_403_for_teacher() -> None:
    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-h5p-access-role", name="Teacher", roles=["teacher"])  # type: ignore
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        r = await c.get(
            "/api/learning/courses/123e4567-e89b-12d3-a456-426614174000/h5p/contents/1/access"
        )
        assert r.status_code == 403
        assert r.headers.get("Cache-Control") == "private, no-store"
        assert (r.json() or {}).get("error") == "forbidden"


@pytest.mark.anyio
async def test_learning_h5p_access_401_for_unauthenticated() -> None:
    async with (await _client()) as c:
        r = await c.get(
            "/api/learning/courses/123e4567-e89b-12d3-a456-426614174000/h5p/contents/1/access"
        )
        assert r.status_code == 401
        assert r.headers.get("Cache-Control") == "private, no-store"
        assert (r.json() or {}).get("error") == "unauthenticated"


@pytest.mark.anyio
async def test_learning_h5p_access_400_for_invalid_course_uuid() -> None:
    main.SESSION_STORE = SessionStore()
    student = main.SESSION_STORE.create(sub="s-h5p-access-bad-uuid", name="Student", roles=["student"])  # type: ignore
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)
        r = await c.get("/api/learning/courses/not-a-uuid/h5p/contents/1/access")
        assert r.status_code == 400
        assert r.headers.get("Cache-Control") == "private, no-store"
        body = r.json() or {}
        assert body.get("error") == "bad_request"
        assert body.get("detail") == "invalid_uuid"


@pytest.mark.anyio
async def test_learning_h5p_access_400_for_invalid_content_id() -> None:
    main.SESSION_STORE = SessionStore()
    student = main.SESSION_STORE.create(sub="s-h5p-access-bad-cid", name="Student", roles=["student"])  # type: ignore
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)
        r = await c.get(
            "/api/learning/courses/123e4567-e89b-12d3-a456-426614174000/h5p/contents/not-a-number/access"
        )
        assert r.status_code == 400
        assert r.headers.get("Cache-Control") == "private, no-store"
        body = r.json() or {}
        assert body.get("error") == "bad_request"
        assert body.get("detail") == "invalid_content_id"


@pytest.mark.anyio
async def test_learning_h5p_access_400_for_non_ascii_digit_content_id() -> None:
    """Non-ASCII digits must be rejected to match the OpenAPI `^[0-9]+$` pattern."""
    main.SESSION_STORE = SessionStore()
    student = main.SESSION_STORE.create(sub="s-h5p-access-nonascii", name="Student", roles=["student"])  # type: ignore
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)
        r = await c.get(
            "/api/learning/courses/123e4567-e89b-12d3-a456-426614174000/h5p/contents/١/access"
        )
        assert r.status_code == 400
        assert r.headers.get("Cache-Control") == "private, no-store"
        body = r.json() or {}
        assert body.get("error") == "bad_request"
        assert body.get("detail") == "invalid_content_id"
