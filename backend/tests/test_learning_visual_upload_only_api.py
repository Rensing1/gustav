"""
Learning API — Visual tasks are upload-only (Phase 3)

Intent:
    Specify the contract for `Task.kind="visual"`:
    - Students may only submit uploads (`kind=image|file`).
    - Text submissions are rejected with 400 (detail=invalid_input).

Why:
    Visual tasks are designed for handwritten solutions, sketches, diagrams,
    and other non-text artifacts. Allowing `kind=text` would reintroduce the
    "native" workflow and blur the UX and AI-processing expectations.
"""

from __future__ import annotations

import os
import uuid

import httpx
import pytest
from httpx import ASGITransport

from utils.db import require_db_or_skip as _require_db_or_skip

import main  # type: ignore  # noqa: E402
from identity_access.stores import SessionStore  # type: ignore  # noqa: E402


pytestmark = pytest.mark.anyio("asyncio")


async def _client() -> httpx.AsyncClient:
    # Provide Origin for strict CSRF on Learning write endpoints
    return httpx.AsyncClient(
        transport=ASGITransport(app=main.app),
        base_url="http://test",
        headers={"Origin": "http://test"},
    )


def _service_dsn() -> str:
    host = os.getenv("TEST_DB_HOST", "127.0.0.1")
    port = os.getenv("TEST_DB_PORT", "54322")
    user = os.getenv("APP_DB_USER", "gustav_app")
    password = os.getenv("APP_DB_PASSWORD", "CHANGE_ME_DEV")
    return (
        os.getenv("SERVICE_ROLE_DSN")
        or os.getenv("RLS_TEST_SERVICE_DSN")
        or os.getenv("DATABASE_URL")
        or f"postgresql://{user}:{password}@{host}:{port}/postgres"
    )


async def _prepare_visual_task_fixture() -> dict:
    """Create course/unit/section with one released visual task and one enrolled student."""
    _require_db_or_skip()

    import routes.teaching as teaching  # noqa: E402
    import routes.learning as learning  # noqa: E402

    # Verify repos are DB-backed (avoid in-memory fallbacks masking behavior)
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        assert isinstance(teaching.REPO, DBTeachingRepo)
        from backend.learning.repo_db import DBLearningRepo  # type: ignore
        assert isinstance(learning.REPO, DBLearningRepo)
    except Exception:
        pytest.skip("DB-backed repos required")

    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub=f"t-visual-{uuid.uuid4()}", name="T", roles=["teacher"])  # type: ignore
    student = main.SESSION_STORE.create(sub=f"s-visual-{uuid.uuid4()}", name="S", roles=["student"])  # type: ignore

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)

        course = (await c.post("/api/teaching/courses", json={"title": "Kurs Visual"})).json()
        unit = (await c.post("/api/teaching/units", json={"title": "Unit"})).json()
        section = (
            await c.post(f"/api/teaching/units/{unit['id']}/sections", json={"title": "Abschnitt"})
        ).json()

        task = (
            await c.post(
                f"/api/teaching/units/{unit['id']}/sections/{section['id']}/tasks",
                json={
                    "instruction_md": "### Visual Aufgabe",
                    "criteria": ["K1"],
                    "visual": {},
                    "max_attempts": 2,
                },
            )
        ).json()

        module = (
            await c.post(f"/api/teaching/courses/{course['id']}/modules", json={"unit_id": unit["id"]})
        ).json()

        r = await c.patch(
            f"/api/teaching/courses/{course['id']}/modules/{module['id']}/sections/{section['id']}/visibility",
            json={"visible": True},
        )
        assert r.status_code == 200

        r = await c.post(
            f"/api/teaching/courses/{course['id']}/members",
            json={"student_sub": student.sub},  # type: ignore[attr-defined]
        )
        assert r.status_code in (201, 204)

    return {"teacher": teacher, "student": student, "course_id": course["id"], "task_id": task["id"]}


@pytest.mark.anyio
async def test_visual_task_rejects_text_submissions():
    fx = await _prepare_visual_task_fixture()
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, fx["student"].session_id)
        r = await c.post(
            f"/api/learning/courses/{fx['course_id']}/tasks/{fx['task_id']}/submissions",
            headers={"Idempotency-Key": "visual-text-reject"},
            json={"kind": "text", "text_body": "Meine Lösung als Text"},
        )
        assert r.status_code == 400
        assert r.json().get("detail") == "invalid_input"


@pytest.mark.anyio
async def test_visual_task_accepts_upload_submissions():
    fx = await _prepare_visual_task_fixture()
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, fx["student"].session_id)
        r = await c.post(
            f"/api/learning/courses/{fx['course_id']}/tasks/{fx['task_id']}/submissions",
            headers={"Idempotency-Key": "visual-image-ok"},
            json={
                "kind": "image",
                "storage_key": "submissions/course/task/student/visual.png",
                "mime_type": "image/png",
                "size_bytes": 1234,
                "sha256": "0" * 64,
            },
        )
        assert r.status_code in (201, 202)
        body = r.json()
        assert body["kind"] == "image"
        assert body["analysis_status"] == "pending"

