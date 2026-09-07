"""API tests for the first concrete room read-models."""

from __future__ import annotations

import importlib

import httpx
import pytest
from httpx import ASGITransport

from backend.web.learning_course_providers import LearningCourseProviders

main = importlib.import_module("backend.web.main")
app_routes = importlib.import_module("backend.web.routes.app")


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
async def test_learner_home_returns_student_courses() -> None:
    class Courses:
        def list_personal_courses(self, *, student_sub, limit, offset, scope):
            return [
                {"id": "course-1", "title": "Mathe 9b"},
                {"id": "course-2", "title": "Informatik"},
            ] if scope == "current" else []

    app = main.create_app(
        learning_course_providers=LearningCourseProviders(repository=Courses),
        access_token_verifier=lambda token, cfg: {
            "sub": "student-home", "realm_access": {"roles": ["student"]},
        },
    )
    headers = {"Authorization": "Bearer test.jwt"}

    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/learning/views/learner-home", headers=headers)

    assert response.status_code == 200
    assert response.headers.get("Cache-Control") == "private, no-store"
    assert response.json()["user"]["sub"] == "student-home"
    assert response.json()["current_courses"] == [
        {"id": "course-1", "title": "Mathe 9b", "href": "/learning/courses/course-1", "school_year_start": None},
        {"id": "course-2", "title": "Informatik", "href": "/learning/courses/course-2", "school_year_start": None},
    ]
    assert response.json()["past_courses"] == []


@pytest.mark.anyio
async def test_teacher_home_returns_work_starter() -> None:
    from backend.web.teacher_catalog_providers import TeacherCatalogProviders

    class EmptyRepository:
        def list_courses_for_teacher(self, **kwargs):
            return []
        def list_units_for_author(self, **kwargs):
            return []

    app = main.create_app(
        teacher_catalog_providers=TeacherCatalogProviders(repository=EmptyRepository),
        access_token_verifier=lambda token, cfg: {
            "sub": "teacher-home", "name": "Ada", "gustav_display_name": "Ada",
            "realm_access": {"roles": ["teacher"]},
        },
    )
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/teaching/views/teacher-home", headers={"Authorization": "Bearer test.jwt"})
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "private, no-store"
    assert response.json() == {
        "user": {"sub": "teacher-home", "name": "Ada", "role": "teacher", "roles": ["teacher"]},
        "courses": [], "recent_units": [], "units_href": "/teaching/units",
        "create_unit_href": "/teaching/units?create=1",
    }


@pytest.mark.anyio
async def test_teacher_courses_view_returns_teacher_course_cards(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        app_routes,
        "_list_teacher_course_cards",
        lambda owner_sub, limit, offset, **filters: [
            {
                "id": "course-1",
                "title": "Mathe 9b",
                "href": "/teaching/courses/course-1",
                "members_count": 28,
                "units_count": 6,
                "subject": "Mathematik",
                "grade_level": "9b",
                "term": "Q1",
                "school_year_start": 2026,
                "status": "active",
                "metadata_complete": True,
                "archived_at": None,
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
                "school_year_start": None,
                "status": "active",
                "metadata_complete": False,
                "archived_at": None,
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
        "status": "active",
        "query": "",
        "school_year_start": None,
        "subject": "",
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
                "school_year_start": 2026,
                "status": "active",
                "metadata_complete": True,
                "archived_at": None,
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
                "school_year_start": None,
                "status": "active",
                "metadata_complete": False,
                "archived_at": None,
            },
        ],
    }


@pytest.mark.anyio
async def test_learner_home_forbids_teacher() -> None:
    app = main.create_app(access_token_verifier=lambda token, cfg: {
        "sub": "teacher-home", "realm_access": {"roles": ["teacher"]},
    })
    headers = {"Authorization": "Bearer test.jwt"}

    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
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
