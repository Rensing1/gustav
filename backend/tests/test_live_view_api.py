"""API tests for the new live room read-models."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import httpx
import pytest
from fastapi.responses import JSONResponse, Response
from httpx import ASGITransport


REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))

import main  # type: ignore
from routes import app as app_routes  # type: ignore


pytestmark = pytest.mark.anyio("asyncio")


def _mock_bearer_auth(
    monkeypatch: pytest.MonkeyPatch,
    *,
    sub: str,
    roles: list[str],
    name: str,
) -> dict[str, str]:
    monkeypatch.setattr(
        main,
        "verify_bearer_token",
        lambda token, cfg: {
            "sub": sub,
            "name": name,
            "gustav_display_name": name,
            "realm_access": {"roles": roles},
            "exp": 4102444800,
        },
    )
    return {"Authorization": "Bearer test.jwt"}


def _json_response(payload: object, status_code: int = 200) -> JSONResponse:
    return JSONResponse(payload, status_code=status_code, headers={"Cache-Control": "private, no-store"})


@pytest.mark.anyio
async def test_live_matrix_returns_course_unit_tasks_and_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app_routes.teaching_routes, "_guard_course_owner", lambda course_id, owner_sub: None)
    monkeypatch.setattr(
        app_routes,
        "_get_teacher_course",
        lambda course_id, owner_sub: {"id": course_id, "title": "Mathe 9b"},
    )
    monkeypatch.setattr(
        app_routes,
        "_list_teacher_course_units",
        lambda course_id, owner_sub: [{"id": "unit-1", "title": "Brueche", "position": 1}],
    )
    monkeypatch.setattr(
        app_routes.teaching_routes,
        "get_unit_live_summary",
        lambda request, course_id, unit_id, updated_since=None, limit=100, offset=0, include_students=True: _json_response(
            {
                "tasks": [
                    {
                        "id": "task-1",
                        "instruction_md": "### Aufgabe 1",
                        "position": 1,
                        "kind": "native",
                    }
                ],
                "rows": [
                    {
                        "student": {"sub": "student-1", "name": "Anna"},
                        "tasks": [{"task_id": "task-1", "has_submission": True, "average_score": 4.0}],
                    }
                ],
            }
        ),
    )
    headers = _mock_bearer_auth(monkeypatch, sub="teacher-live", roles=["teacher"], name="Ada")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.get("/api/live/views/courses/course-1/units/unit-1/matrix", headers=headers)

    assert response.status_code == 200
    assert response.headers.get("Cache-Control") == "private, no-store"
    assert response.json() == {
        "user": {
            "sub": "teacher-live",
            "name": "Ada",
            "role": "teacher",
            "roles": ["teacher"],
        },
        "course": {
            "id": "course-1",
            "title": "Mathe 9b",
            "href": "/live/courses/course-1",
        },
        "unit": {
            "id": "unit-1",
            "title": "Brueche",
            "position": 1,
            "href": "/live/courses/course-1/units/unit-1",
        },
        "tasks": [
            {
                "id": "task-1",
                "instruction_md": "### Aufgabe 1",
                "position": 1,
                "kind": "native",
            }
        ],
        "rows": [
            {
                "student": {
                    "sub": "student-1",
                    "name": "Anna",
                    "href": "/live/courses/course-1/units/unit-1?student_sub=student-1",
                },
                "tasks": [
                    {
                        "task_id": "task-1",
                        "has_submission": True,
                        "average_score": 4.0,
                        "href": "/live/courses/course-1/units/unit-1?student_sub=student-1&task_id=task-1",
                    }
                ],
            }
        ],
    }


@pytest.mark.anyio
async def test_live_detail_sheet_returns_selected_submission(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app_routes.teaching_routes, "_guard_course_owner", lambda course_id, owner_sub: None)
    monkeypatch.setattr(
        app_routes,
        "_get_teacher_course",
        lambda course_id, owner_sub: {"id": course_id, "title": "Mathe 9b"},
    )
    monkeypatch.setattr(
        app_routes,
        "_list_teacher_course_units",
        lambda course_id, owner_sub: [{"id": "unit-1", "title": "Brueche", "position": 1}],
    )
    monkeypatch.setattr(
        app_routes.teaching_routes,
        "resolve_student_login_labels_by_sub",
        lambda subs: {"student-1": "Anna"},
    )
    monkeypatch.setattr(
        app_routes.teaching_routes,
        "get_latest_submission_detail",
        lambda request, course_id, unit_id, task_id, student_sub: _json_response(
            {
                "id": "submission-1",
                "task_id": task_id,
                "student_sub": student_sub,
                "instruction_md": "### Aufgabe 1",
                "created_at": "2026-03-23T10:00:00+00:00",
                "completed_at": "2026-03-23T10:01:00+00:00",
                "kind": "text",
                "text_body": "Meine Antwort",
                "feedback_md": "Kurzfeedback",
                "files": [],
            }
        ),
    )
    headers = _mock_bearer_auth(monkeypatch, sub="teacher-live", roles=["teacher"], name="Ada")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.get(
            "/api/live/views/courses/course-1/units/unit-1/detail-sheet",
            params={"student_sub": "student-1", "task_id": "task-1"},
            headers=headers,
        )

    assert response.status_code == 200
    assert response.json() == {
        "user": {
            "sub": "teacher-live",
            "name": "Ada",
            "role": "teacher",
            "roles": ["teacher"],
        },
        "course": {
            "id": "course-1",
            "title": "Mathe 9b",
            "href": "/live/courses/course-1",
        },
        "unit": {
            "id": "unit-1",
            "title": "Brueche",
            "position": 1,
            "href": "/live/courses/course-1/units/unit-1",
        },
        "student": {
            "sub": "student-1",
            "name": "Anna",
            "href": "/live/courses/course-1/units/unit-1?student_sub=student-1",
        },
        "task": {
            "id": "task-1",
            "href": "/live/courses/course-1/units/unit-1?student_sub=student-1&task_id=task-1",
        },
        "submission": {
            "id": "submission-1",
            "task_id": "task-1",
            "student_sub": "student-1",
            "instruction_md": "### Aufgabe 1",
            "created_at": "2026-03-23T10:00:00+00:00",
            "completed_at": "2026-03-23T10:01:00+00:00",
            "kind": "text",
            "text_body": "Meine Antwort",
            "feedback_md": "Kurzfeedback",
            "files": [],
        },
    }


@pytest.mark.anyio
async def test_live_detail_sheet_returns_no_content_state(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app_routes.teaching_routes, "_guard_course_owner", lambda course_id, owner_sub: None)
    monkeypatch.setattr(
        app_routes,
        "_get_teacher_course",
        lambda course_id, owner_sub: {"id": course_id, "title": "Mathe 9b"},
    )
    monkeypatch.setattr(
        app_routes,
        "_list_teacher_course_units",
        lambda course_id, owner_sub: [{"id": "unit-1", "title": "Brueche", "position": 1}],
    )
    monkeypatch.setattr(
        app_routes.teaching_routes,
        "resolve_student_login_labels_by_sub",
        lambda subs: {"student-1": "Anna"},
    )
    monkeypatch.setattr(
        app_routes.teaching_routes,
        "get_latest_submission_detail",
        lambda request, course_id, unit_id, task_id, student_sub: Response(
            status_code=204, headers={"Cache-Control": "private, no-store"}
        ),
    )
    headers = _mock_bearer_auth(monkeypatch, sub="teacher-live", roles=["teacher"], name="Ada")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.get(
            "/api/live/views/courses/course-1/units/unit-1/detail-sheet",
            params={"student_sub": "student-1", "task_id": "task-1"},
            headers=headers,
        )

    assert response.status_code == 200
    assert response.json()["submission"] is None


@pytest.mark.anyio
async def test_live_view_forbids_students(monkeypatch: pytest.MonkeyPatch) -> None:
    headers = _mock_bearer_auth(monkeypatch, sub="student-live", roles=["student"], name="Lena")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        matrix_response = await client.get("/api/live/views/courses/course-1/units/unit-1/matrix", headers=headers)
        detail_response = await client.get(
            "/api/live/views/courses/course-1/units/unit-1/detail-sheet",
            params={"student_sub": "student-1", "task_id": "task-1"},
            headers=headers,
        )

    assert matrix_response.status_code == 403
    assert detail_response.status_code == 403
