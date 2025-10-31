"""
Learning API — Idempotency-Key header validation for submissions

Scenarios:
- Reject non-ASCII/whitespace characters in Idempotency-Key with 400
- Reject tokens longer than 64 characters with 400
- Accept valid tokens (letters, digits, underscore, hyphen) and create submission
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
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test")


async def _prepare_fixture():
    """Create a course/unit/section/task and enroll a student; release the section."""
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

    # Sessions
    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-idem", name="Lehrkraft", roles=["teacher"])  # type: ignore
    student = main.SESSION_STORE.create(sub="s-idem", name="Schüler", roles=["student"])  # type: ignore

    async with (await _client()) as c:
        c.cookies.set("gustav_session", teacher.session_id)
        # Create course/unit/section/task
        r = await c.post("/api/teaching/courses", json={"title": "Kurs Idem"})
        assert r.status_code == 201
        course_id = r.json()["id"]
        u = (await c.post("/api/teaching/units", json={"title": "Unit"})).json()
        s = (await c.post(f"/api/teaching/units/{u['id']}/sections", json={"title": "Abschnitt"})).json()
        t = (
            await c.post(
                f"/api/teaching/units/{u['id']}/sections/{s['id']}/tasks",
                json={"instruction_md": "Aufgabe", "criteria": ["Kriterium"]},
            )
        ).json()
        m = (await c.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": u["id"]})).json()
        # Release
        r = await c.patch(
            f"/api/teaching/courses/{course_id}/modules/{m['id']}/sections/{s['id']}/visibility",
            json={"visible": True},
            headers={"Origin": "http://test"},
        )
        assert r.status_code == 200
        # Enroll student
        r = await c.post(f"/api/teaching/courses/{course_id}/members", json={"student_sub": student.sub})
        assert r.status_code in (201, 204)

    return {
        "teacher": teacher,
        "student": student,
        "course_id": course_id,
        "task_id": t["id"],
    }


@pytest.mark.anyio
async def test_rejects_invalid_idempotency_key_chars():
    fx = await _prepare_fixture()
    async with (await _client()) as c:
        c.cookies.set("gustav_session", fx["student"].session_id)
        r = await c.post(
            f"/api/learning/courses/{fx['course_id']}/tasks/{fx['task_id']}/submissions",
            headers={"Idempotency-Key": "bad token with space"},
            json={"kind": "text", "text_body": "Antwort"},
        )
        assert r.status_code == 400
        assert r.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_rejects_idempotency_key_too_long():
    fx = await _prepare_fixture()
    long_token = "a" * 65
    async with (await _client()) as c:
        c.cookies.set("gustav_session", fx["student"].session_id)
        r = await c.post(
            f"/api/learning/courses/{fx['course_id']}/tasks/{fx['task_id']}/submissions",
            headers={"Idempotency-Key": long_token},
            json={"kind": "text", "text_body": "Antwort"},
        )
        assert r.status_code == 400
        assert r.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_accepts_valid_idempotency_key_token():
    fx = await _prepare_fixture()
    token = "abc-DEF_123"
    async with (await _client()) as c:
        c.cookies.set("gustav_session", fx["student"].session_id)
        r = await c.post(
            f"/api/learning/courses/{fx['course_id']}/tasks/{fx['task_id']}/submissions",
            headers={"Idempotency-Key": token},
            json={"kind": "text", "text_body": "Meine Antwort"},
        )
        assert r.status_code == 201
        assert r.headers.get("Cache-Control") == "private, no-store"
        body = r.json()
        assert body.get("id") and body.get("attempt_nr") == 1


@pytest.mark.anyio
async def test_idempotent_retry_returns_existing_submission():
    fx = await _prepare_fixture()
    token = "retry-token-1"
    payload = {"kind": "text", "text_body": "Dies ist meine Lösung"}
    async with (await _client()) as c:
        c.cookies.set("gustav_session", fx["student"].session_id)
        first = await c.post(
            f"/api/learning/courses/{fx['course_id']}/tasks/{fx['task_id']}/submissions",
            headers={"Idempotency-Key": token},
            json=payload,
        )
        assert first.status_code == 201
        first_body = first.json()
        second = await c.post(
            f"/api/learning/courses/{fx['course_id']}/tasks/{fx['task_id']}/submissions",
            headers={"Idempotency-Key": token},
            json=payload,
        )
        assert second.status_code == 201
        second_body = second.json()
        assert second_body["id"] == first_body["id"]
        assert second_body["attempt_nr"] == first_body["attempt_nr"]
        assert second.headers.get("Cache-Control") == "private, no-store"
