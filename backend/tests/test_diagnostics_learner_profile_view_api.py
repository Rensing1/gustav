"""API tests for the diagnostics learner profile read-model."""

from __future__ import annotations

from pathlib import Path
import sys

import httpx
from httpx import ASGITransport
import pytest


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


@pytest.mark.anyio
async def test_diagnostics_learner_profile_returns_owner_scoped_course_summaries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        app_routes,
        "_build_diagnostics_learner_profile_courses",
        lambda student_sub, owner_sub, limit, offset: [
            {
                "id": "course-1",
                "title": "Mathe 9b",
                "href": "/diagnostics/courses/course-1",
                "submitted_tasks": 3,
                "total_tasks": 5,
                "units": [
                    {
                        "id": "unit-1",
                        "title": "Brueche",
                        "position": 1,
                        "href": "/diagnostics/courses/course-1/units/unit-1",
                        "submitted_tasks": 2,
                        "total_tasks": 2,
                    },
                    {
                        "id": "unit-2",
                        "title": "Terme",
                        "position": 2,
                        "href": "/diagnostics/courses/course-1/units/unit-2",
                        "submitted_tasks": 1,
                        "total_tasks": 3,
                    },
                ],
            }
        ],
    )
    monkeypatch.setattr(
        app_routes.teaching_routes,
        "resolve_student_names",
        lambda subs: {str(subs[0]): "Anna"},
    )
    headers = _mock_bearer_auth(monkeypatch, sub="teacher-diagnostics", roles=["teacher"], name="Ada")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.get("/api/diagnostics/views/learners/student-1/profile", headers=headers)

    assert response.status_code == 200
    assert response.headers.get("Cache-Control") == "private, no-store"
    assert response.json() == {
        "user": {
            "sub": "teacher-diagnostics",
            "name": "Ada",
            "role": "teacher",
            "roles": ["teacher"],
        },
        "learner": {
            "sub": "student-1",
            "name": "Anna",
            "href": "/diagnostics/learners/student-1",
        },
        "summary": {
            "courses_count": 1,
            "submitted_tasks": 3,
            "total_tasks": 5,
        },
        "courses": [
            {
                "id": "course-1",
                "title": "Mathe 9b",
                "href": "/diagnostics/courses/course-1",
                "submitted_tasks": 3,
                "total_tasks": 5,
                "units": [
                    {
                        "id": "unit-1",
                        "title": "Brueche",
                        "position": 1,
                        "href": "/diagnostics/courses/course-1/units/unit-1",
                        "submitted_tasks": 2,
                        "total_tasks": 2,
                    },
                    {
                        "id": "unit-2",
                        "title": "Terme",
                        "position": 2,
                        "href": "/diagnostics/courses/course-1/units/unit-2",
                        "submitted_tasks": 1,
                        "total_tasks": 3,
                    },
                ],
            }
        ],
    }


@pytest.mark.anyio
async def test_diagnostics_learner_profile_forbids_students(monkeypatch: pytest.MonkeyPatch) -> None:
    headers = _mock_bearer_auth(monkeypatch, sub="student-diagnostics", roles=["student"], name="Lena")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.get("/api/diagnostics/views/learners/student-1/profile", headers=headers)

    assert response.status_code == 403
    assert response.json() == {"error": "forbidden"}


@pytest.mark.anyio
async def test_diagnostics_learner_profile_returns_not_found_when_owner_sees_no_courses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(app_routes, "_build_diagnostics_learner_profile_courses", lambda student_sub, owner_sub, limit, offset: [])
    headers = _mock_bearer_auth(monkeypatch, sub="teacher-diagnostics", roles=["teacher"], name="Ada")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.get("/api/diagnostics/views/learners/student-404/profile", headers=headers)

    assert response.status_code == 404
    assert response.json() == {"error": "not_found"}
