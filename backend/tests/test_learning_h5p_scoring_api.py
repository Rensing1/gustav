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

from backend.tests.runtime_auth_helpers import install_session_store
from backend.tests.utils.db import require_db_or_skip as _require_db_or_skip

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

        r = await c.post("/api/teaching/courses", json={"title": "Kurs H5P", "subject": "Testfach", "grade_level": "10", "school_year_start": 2026})
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

    return {
        "teacher": teacher,
        "student": student,
        "course_id": course_id,
        "unit_id": unit["id"],
        "section_id": section["id"],
        "task_id": task["id"],
    }


async def _load_h5p_task(client: httpx.AsyncClient, *, course_id: str, task_id: str) -> dict:
    """Read one released task through the learner-facing API."""
    response = await client.get(
        f"/api/learning/courses/{course_id}/sections?include=tasks&limit=50&offset=0"
    )
    assert response.status_code == 200
    tasks = [task for section in response.json() for task in section.get("tasks") or []]
    return next(task for task in tasks if task.get("id") == task_id)


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


@pytest.mark.anyio
async def test_learning_task_reports_h5p_completion_and_latest_score(monkeypatch: pytest.MonkeyPatch):
    """Completion stays true after a later partial attempt while the latest score changes."""
    fx = await _prepare_h5p_task_fixture(monkeypatch)
    async with (await _client()) as c:
        c.cookies.set("gustav_session", fx["student"].session_id)

        untouched = await _load_h5p_task(c, course_id=fx["course_id"], task_id=fx["task_id"])
        assert untouched["h5p_completed"] is False
        assert untouched["score_raw"] is None
        assert untouched["score_max"] is None

        partial = await c.post(
            f"/api/learning/courses/{fx['course_id']}/tasks/{fx['task_id']}/submissions",
            headers={"Idempotency-Key": str(uuid.uuid4())},
            json={"kind": "h5p", "score_raw": 0, "score_max": 1},
        )
        assert partial.status_code in (201, 202)
        after_partial = await _load_h5p_task(
            c, course_id=fx["course_id"], task_id=fx["task_id"]
        )
        assert after_partial["h5p_completed"] is False
        assert after_partial["score_raw"] == 0
        assert after_partial["score_max"] == 1

        complete = await c.post(
            f"/api/learning/courses/{fx['course_id']}/tasks/{fx['task_id']}/submissions",
            headers={"Idempotency-Key": str(uuid.uuid4())},
            json={"kind": "h5p", "score_raw": 1, "score_max": 1},
        )
        assert complete.status_code in (201, 202)
        latest_partial = await c.post(
            f"/api/learning/courses/{fx['course_id']}/tasks/{fx['task_id']}/submissions",
            headers={"Idempotency-Key": str(uuid.uuid4())},
            json={"kind": "h5p", "score_raw": 0, "score_max": 1},
        )
        assert latest_partial.status_code in (201, 202)

        after_later_partial = await _load_h5p_task(
            c, course_id=fx["course_id"], task_id=fx["task_id"]
        )
        assert after_later_partial["h5p_completed"] is True
        assert after_later_partial["score_raw"] == 0
        assert after_later_partial["score_max"] == 1


@pytest.mark.anyio
async def test_learning_task_projects_progress_from_current_kind_after_type_changes(
    monkeypatch: pytest.MonkeyPatch,
):
    """Historical submission kinds must not override the current Teaching task kind."""
    fx = await _prepare_h5p_task_fixture(monkeypatch)
    async with (await _client()) as c:
        c.cookies.set("gustav_session", fx["student"].session_id)
        completed = await c.post(
            f"/api/learning/courses/{fx['course_id']}/tasks/{fx['task_id']}/submissions",
            headers={"Idempotency-Key": str(uuid.uuid4())},
            json={"kind": "h5p", "score_raw": 1, "score_max": 1},
        )
        assert completed.status_code in (201, 202)

        c.cookies.set("gustav_session", fx["teacher"].session_id)
        changed_to_native = await c.patch(
            f"/api/teaching/units/{fx['unit_id']}/sections/{fx['section_id']}/tasks/{fx['task_id']}",
            json={"h5p": None},
        )
        assert changed_to_native.status_code == 200
        assert changed_to_native.json()["kind"] == "native"

        c.cookies.set("gustav_session", fx["student"].session_id)
        native_task = await _load_h5p_task(
            c, course_id=fx["course_id"], task_id=fx["task_id"]
        )
        assert native_task["kind"] == "native"
        assert native_task["h5p_completed"] is None
        assert native_task["score_raw"] is None
        assert native_task["score_max"] is None

        native_submission = await c.post(
            f"/api/learning/courses/{fx['course_id']}/tasks/{fx['task_id']}/submissions",
            headers={"Idempotency-Key": str(uuid.uuid4())},
            json={"intent": "submit", "kind": "text", "text_body": "Zwischenstand"},
        )
        assert native_submission.status_code in (201, 202)

        c.cookies.set("gustav_session", fx["teacher"].session_id)
        changed_back_to_h5p = await c.patch(
            f"/api/teaching/units/{fx['unit_id']}/sections/{fx['section_id']}/tasks/{fx['task_id']}",
            json={"h5p": {"content_id": "1", "display_options": {}}},
        )
        assert changed_back_to_h5p.status_code == 200
        assert changed_back_to_h5p.json()["kind"] == "h5p"

        c.cookies.set("gustav_session", fx["student"].session_id)
        h5p_task = await _load_h5p_task(
            c, course_id=fx["course_id"], task_id=fx["task_id"]
        )
        assert h5p_task["kind"] == "h5p"
        assert h5p_task["h5p_completed"] is True
        assert h5p_task["score_raw"] == 1
        assert h5p_task["score_max"] == 1
