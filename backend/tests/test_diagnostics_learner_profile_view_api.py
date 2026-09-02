"""API tests for the diagnostics learner profile read-model."""

from __future__ import annotations

import importlib

import httpx
from httpx import ASGITransport
import pytest


main = importlib.import_module("backend.web.main")
app_routes = importlib.import_module("backend.web.routes.app")
diagnostics_routes = importlib.import_module("backend.web.routes.app_diagnostics_routes")


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


@pytest.mark.anyio
async def test_diagnostics_learner_profile_rejects_invalid_pagination(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers = _mock_bearer_auth(monkeypatch, sub="teacher-diagnostics", roles=["teacher"], name="Ada")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.get(
            "/api/diagnostics/views/learners/student-1/profile?limit=0",
            headers=headers,
        )

    assert response.status_code == 400
    assert response.json() == {"error": "bad_request", "detail": "invalid_pagination"}


@pytest.mark.anyio
async def test_diagnostics_learner_profile_rejects_non_integer_pagination_privately(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers = _mock_bearer_auth(monkeypatch, sub="teacher-diagnostics", roles=["teacher"], name="Ada")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.get(
            "/api/diagnostics/views/learners/student-1/profile?offset=abc",
            headers=headers,
        )

    assert response.status_code == 400
    assert response.headers.get("Cache-Control") == "private, no-store"
    assert response.json() == {"error": "bad_request", "detail": "invalid_pagination"}


@pytest.mark.anyio
async def test_diagnostics_learner_profile_returns_empty_valid_following_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    visible = {
        "id": "course-1",
        "title": "Mathe 9b",
        "href": "/diagnostics/courses/course-1",
        "submitted_tasks": 0,
        "total_tasks": 0,
        "units": [],
    }
    monkeypatch.setattr(
        app_routes,
        "_build_diagnostics_learner_profile_courses",
        lambda student_sub, owner_sub, limit, offset: [visible] if offset == 0 else [],
    )
    monkeypatch.setattr(
        app_routes.teaching_routes,
        "resolve_student_names",
        lambda subs: {str(subs[0]): "Anna"},
    )
    headers = _mock_bearer_auth(monkeypatch, sub="teacher-diagnostics", roles=["teacher"], name="Ada")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.get(
            "/api/diagnostics/views/learners/student-1/profile?limit=50&offset=50",
            headers=headers,
        )

    assert response.status_code == 200
    assert response.headers.get("Cache-Control") == "private, no-store"
    assert response.json()["courses"] == []
    assert response.json()["summary"] == {
        "courses_count": 0,
        "submitted_tasks": 0,
        "total_tasks": 0,
    }


@pytest.mark.anyio
async def test_diagnostics_learner_profile_keeps_invisible_following_page_private(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        app_routes,
        "_build_diagnostics_learner_profile_courses",
        lambda student_sub, owner_sub, limit, offset: [],
    )
    headers = _mock_bearer_auth(monkeypatch, sub="teacher-diagnostics", roles=["teacher"], name="Ada")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.get(
            "/api/diagnostics/views/learners/unknown/profile?limit=50&offset=50",
            headers=headers,
        )

    assert response.status_code == 404
    assert response.headers.get("Cache-Control") == "private, no-store"


def test_learner_profile_paginates_visible_courses_after_membership_filter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeRepo:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str, int, int]] = []

        def list_active_courses_for_owner_member(
            self, *, owner_sub: str, student_sub: str, limit: int, offset: int
        ) -> list[dict[str, str]]:
            self.calls.append((owner_sub, student_sub, limit, offset))
            return [
                {"id": f"course-{index:03d}", "title": f"Kurs {index:03d}"}
                for index in range(offset, offset + limit)
            ]

    repo = FakeRepo()
    monkeypatch.setattr(diagnostics_routes.teaching_routes, "_get_repo", lambda: repo)
    monkeypatch.setattr(app_routes, "_list_teacher_course_units", lambda course_id, owner_sub: [])
    monkeypatch.setattr(
        app_routes,
        "_list_submission_pairs_for_students",
        lambda course_id, owner_sub, student_subs, task_ids: set(),
    )

    courses = diagnostics_routes._build_diagnostics_learner_profile_courses(
        "student-1",
        "teacher-1",
        limit=20,
        offset=10,
    )

    assert [course["id"] for course in courses] == [
        f"course-{index:03d}" for index in range(10, 30)
    ]
    assert repo.calls == [("teacher-1", "student-1", 20, 10)]
