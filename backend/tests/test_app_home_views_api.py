"""API tests for the first concrete room read-models."""

from __future__ import annotations

import importlib

import httpx
import pytest
from httpx import ASGITransport


main = importlib.import_module("backend.web.main")
app_routes = importlib.import_module("backend.web.routes.app")
teacher_concern_routes = importlib.import_module("backend.web.routes.app_teacher_concern_routes")


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
async def test_learner_home_returns_student_courses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        app_routes,
        "_list_learner_courses",
        lambda student_sub, limit, offset: [
            {"id": "course-1", "title": "Mathe 9b"},
            {"id": "course-2", "title": "Informatik"},
        ],
    )
    headers = _mock_bearer_auth(monkeypatch, sub="student-home", roles=["student"], name="Lena")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.get("/api/learning/views/learner-home", headers=headers)

    assert response.status_code == 200
    assert response.headers.get("Cache-Control") == "private, no-store"
    assert response.json()["user"]["sub"] == "student-home"
    assert response.json()["courses"] == [
        {"id": "course-1", "title": "Mathe 9b", "href": "/learning/courses/course-1"},
        {"id": "course-2", "title": "Informatik", "href": "/learning/courses/course-2"},
    ]


@pytest.mark.anyio
async def test_teacher_home_returns_work_starter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        app_routes,
        "_teacher_home_workstarter",
        lambda owner_sub: {
            "courses": [
                {"id": "course-2", "title": "Informatik 9b"},
                {"id": "course-1", "title": "Politik 10L"},
            ],
            "recent_units": [
                {
                    "id": "unit-2",
                    "title": "Gesetzgebungsverfahren der EU",
                    "updated_at": "2026-08-06T10:26:00+00:00",
                    "href": "/teaching/units/unit-2",
                },
                {
                    "id": "unit-1",
                    "title": "Kommunikation in Rechnernetzen",
                    "updated_at": "2026-08-05T08:00:00+00:00",
                    "href": "/teaching/units/unit-1",
                },
            ],
        },
        raising=False,
    )
    headers = _mock_bearer_auth(monkeypatch, sub="teacher-home", roles=["teacher"], name="Ada")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.get("/api/teaching/views/teacher-home", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["sub"] == "teacher-home"
    assert body == {
        "user": {
            "sub": "teacher-home",
            "name": "Ada",
            "role": "teacher",
            "roles": ["teacher"],
        },
        "courses": [
            {"id": "course-2", "title": "Informatik 9b"},
            {"id": "course-1", "title": "Politik 10L"},
        ],
        "recent_units": [
            {
                "id": "unit-2",
                "title": "Gesetzgebungsverfahren der EU",
                "updated_at": "2026-08-06T10:26:00+00:00",
                "href": "/teaching/units/unit-2",
            },
            {
                "id": "unit-1",
                "title": "Kommunikation in Rechnernetzen",
                "updated_at": "2026-08-05T08:00:00+00:00",
                "href": "/teaching/units/unit-1",
            },
        ],
        "units_href": "/teaching/units",
        "create_unit_href": "/teaching/units?create=1",
    }


def test_teacher_home_workstarter_sorts_courses_and_limits_recent_units(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        app_routes,
        "_list_teacher_courses",
        lambda owner_sub, limit, offset: [
            {"id": "course-z", "title": "Zukunft"},
            {"id": "course-a", "title": "Anfang"},
        ],
    )
    monkeypatch.setattr(
        app_routes,
        "_teacher_units_catalog",
        lambda owner_sub, query, sort: {
            "items": [
                {
                    "id": f"unit-{index}",
                    "title": f"Einheit {index}",
                    "updated_at": f"2026-08-0{index}T10:00:00+00:00",
                    "href": f"/teaching/units/unit-{index}",
                }
                for index in range(5, 0, -1)
            ]
        },
        raising=False,
    )

    payload = teacher_concern_routes._teacher_home_workstarter("teacher-home")

    assert payload["courses"] == [
        {"id": "course-a", "title": "Anfang"},
        {"id": "course-z", "title": "Zukunft"},
    ]
    assert [unit["id"] for unit in payload["recent_units"]] == ["unit-5", "unit-4", "unit-3"]


@pytest.mark.anyio
async def test_teacher_courses_view_returns_teacher_course_cards(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        app_routes,
        "_list_teacher_course_cards",
        lambda owner_sub, limit, offset: [
            {
                "id": "course-1",
                "title": "Mathe 9b",
                "href": "/teaching/courses/course-1",
                "members_count": 28,
                "units_count": 6,
                "subject": "Mathematik",
                "grade_level": "9b",
                "term": "Q1",
            },
            {
                "id": "course-2",
                "title": "Informatik AG",
                "href": "/teaching/courses/course-2",
                "members_count": 12,
                "units_count": 2,
                "subject": None,
                "grade_level": None,
                "term": None,
            },
        ],
    )
    headers = _mock_bearer_auth(monkeypatch, sub="teacher-courses", roles=["teacher"], name="Ada")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.get("/api/teaching/views/courses", headers=headers)

    assert response.status_code == 200
    assert response.headers.get("Cache-Control") == "private, no-store"
    assert response.json() == {
        "user": {
            "sub": "teacher-courses",
            "name": "Ada",
            "role": "teacher",
            "roles": ["teacher"],
        },
        "courses": [
            {
                "id": "course-1",
                "title": "Mathe 9b",
                "href": "/teaching/courses/course-1",
                "members_count": 28,
                "units_count": 6,
                "subject": "Mathematik",
                "grade_level": "9b",
                "term": "Q1",
            },
            {
                "id": "course-2",
                "title": "Informatik AG",
                "href": "/teaching/courses/course-2",
                "members_count": 12,
                "units_count": 2,
                "subject": None,
                "grade_level": None,
                "term": None,
            },
        ],
    }


@pytest.mark.anyio
async def test_learner_home_forbids_teacher(monkeypatch: pytest.MonkeyPatch) -> None:
    headers = _mock_bearer_auth(monkeypatch, sub="teacher-home", roles=["teacher"], name="Ada")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.get("/api/learning/views/learner-home", headers=headers)

    assert response.status_code == 403
    assert response.json() == {"error": "forbidden"}


@pytest.mark.anyio
async def test_teacher_courses_view_forbids_student(monkeypatch: pytest.MonkeyPatch) -> None:
    headers = _mock_bearer_auth(monkeypatch, sub="student-home", roles=["student"], name="Lena")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.get("/api/teaching/views/courses", headers=headers)

    assert response.status_code == 403
    assert response.json() == {"error": "forbidden"}
