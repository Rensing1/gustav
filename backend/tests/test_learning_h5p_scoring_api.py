"""
Learning API — H5P scoring submissions (Phase 3)

These tests specify the MVP behavior for `Task.kind="h5p"` on the Learning side:

- Students submit scored H5P results as `kind=h5p`.
- Every submission is a new attempt (`attempt_nr` increments).
- `max_attempts` is **not** enforced for H5P tasks (H5P can enforce its own limits).

Why:
    H5P provides immediate in-task feedback and scoring. GUSTAV only needs to
    persist attempts and scores for progress tracking ("attempted" and "full score").
"""

from __future__ import annotations

import importlib
import uuid

import httpx
import pytest
from httpx import ASGITransport

from backend.tests.utils.db import require_db_or_skip as _require_db_or_skip

from backend.tests.runtime_auth_helpers import install_session_store

main = importlib.import_module("backend.web.main")


pytestmark = [pytest.mark.anyio("asyncio"), pytest.mark.db_write]


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=ASGITransport(app=main.app),
        base_url="http://test",
        headers={"Origin": "http://test"},
    )


async def _prepare_h5p_task_fixture(monkeypatch: pytest.MonkeyPatch, *, max_attempts: int | None = None) -> dict:
    """Create course/unit/section with one released H5P task and one enrolled student."""
    _require_db_or_skip()

    teaching = importlib.import_module("backend.web.routes.teaching")
    learning = importlib.import_module("backend.web.routes.learning")

    try:
        from backend.teaching.repo_db import DBTeachingRepo
        assert isinstance(teaching.REPO, DBTeachingRepo)
        from backend.learning.repo_db import DBLearningRepo  # type: ignore
        assert isinstance(learning.REPO, DBLearningRepo)
    except Exception:
        pytest.skip("DB-backed repos required")

    store = install_session_store(monkeypatch, main)
    teacher = store.create(sub="t-h5p", name="Lehrkraft", roles=["teacher"])
    student = store.create(sub="s-h5p", name="Schüler", roles=["student"])

    async with (await _client()) as c:
        c.cookies.set("gustav_session", teacher.session_id)

        r = await c.post("/api/teaching/courses", json={"title": "Kurs H5P"})
        assert r.status_code == 201
        course_id = r.json()["id"]

        unit = (await c.post("/api/teaching/units", json={"title": "Unit"})).json()
        section = (
            await c.post(f"/api/teaching/units/{unit['id']}/sections", json={"title": "Abschnitt"})
        ).json()

        task_payload: dict = {
            "instruction_md": "H5P Aufgabe (placeholder; not shown in UI).",
            "criteria": [],
            "h5p": {"content_id": "1", "display_options": {}},
        }
        if max_attempts is not None:
            task_payload["max_attempts"] = int(max_attempts)

        task = (
            await c.post(
                f"/api/teaching/units/{unit['id']}/sections/{section['id']}/tasks",
                json=task_payload,
            )
        ).json()

        module = (
            await c.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": unit["id"]})
        ).json()

        r = await c.patch(
            f"/api/teaching/courses/{course_id}/modules/{module['id']}/sections/{section['id']}/visibility",
            json={"visible": True},
            headers={"Origin": "http://test"},
        )
        assert r.status_code == 200

        r = await c.post(f"/api/teaching/courses/{course_id}/members", json={"student_sub": student.sub})
        assert r.status_code in (201, 204)

    return {"teacher": teacher, "student": student, "course_id": course_id, "task_id": task["id"]}


@pytest.mark.anyio
async def test_create_h5p_submission_persists_score_and_completes(monkeypatch: pytest.MonkeyPatch):
    fx = await _prepare_h5p_task_fixture(monkeypatch)
    statement_id = "123e4567-e89b-12d3-a456-426614174000"
    async with (await _client()) as c:
        c.cookies.set("gustav_session", fx["student"].session_id)
        r = await c.post(
            f"/api/learning/courses/{fx['course_id']}/tasks/{fx['task_id']}/submissions",
            headers={"Idempotency-Key": statement_id},
            json={"kind": "h5p", "score_raw": 3, "score_max": 3},
        )
        assert r.status_code in (201, 202)
        body = r.json()
        assert body["attempt_nr"] == 1
        assert body["kind"] == "h5p"
        assert body["score_raw"] == 3
        assert body["score_max"] == 3
        assert body["analysis_status"] == "completed"


@pytest.mark.anyio
async def test_h5p_submissions_do_not_enforce_max_attempts(monkeypatch: pytest.MonkeyPatch):
    fx = await _prepare_h5p_task_fixture(monkeypatch, max_attempts=1)
    async with (await _client()) as c:
        c.cookies.set("gustav_session", fx["student"].session_id)
        r1 = await c.post(
            f"/api/learning/courses/{fx['course_id']}/tasks/{fx['task_id']}/submissions",
            headers={"Idempotency-Key": str(uuid.uuid4())},
            json={"kind": "h5p", "score_raw": 0, "score_max": 1},
        )
        assert r1.status_code in (201, 202)
        assert r1.json()["attempt_nr"] == 1

        r2 = await c.post(
            f"/api/learning/courses/{fx['course_id']}/tasks/{fx['task_id']}/submissions",
            headers={"Idempotency-Key": str(uuid.uuid4())},
            json={"kind": "h5p", "score_raw": 1, "score_max": 1},
        )
        assert r2.status_code in (201, 202)
        assert r2.json()["attempt_nr"] == 2


@pytest.mark.anyio
async def test_learning_sections_include_h5p_task_kind_and_config(monkeypatch: pytest.MonkeyPatch):
    fx = await _prepare_h5p_task_fixture(monkeypatch)
    async with (await _client()) as c:
        c.cookies.set("gustav_session", fx["student"].session_id)
        r = await c.get(f"/api/learning/courses/{fx['course_id']}/sections?include=tasks&limit=50&offset=0")
        assert r.status_code == 200
        sections = r.json()
        assert isinstance(sections, list)
        tasks = []
        for entry in sections:
            tasks.extend(entry.get("tasks") or [])
        assert any(t.get("id") == fx["task_id"] for t in tasks)
        task = next(t for t in tasks if t.get("id") == fx["task_id"])
        assert task.get("kind") == "h5p"
        assert task.get("h5p", {}).get("content_id") == "1"
