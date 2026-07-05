"""API tests for the first diagnostics course matrix read-model."""

from __future__ import annotations

import importlib

import httpx
import pytest
from httpx import ASGITransport


main = importlib.import_module("backend.web.main")
app_routes = importlib.import_module("backend.web.routes.app")
teaching_guards = importlib.import_module("backend.web.routes.teaching_guards")


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
async def test_diagnostics_course_matrix_returns_course_units_and_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(teaching_guards, "_guard_course_owner", lambda course_id, owner_sub, repo_provider=None: None)
    monkeypatch.setattr(
        app_routes,
        "_get_teacher_course",
        lambda course_id, owner_sub: {"id": course_id, "title": "Mathe 9b"},
    )
    monkeypatch.setattr(
        app_routes,
        "_list_teacher_course_units",
        lambda course_id, owner_sub: [
            {"id": "unit-1", "title": "Brueche", "position": 1},
            {"id": "unit-2", "title": "Terme", "position": 2},
        ],
    )
    monkeypatch.setattr(
        app_routes,
        "_build_diagnostics_course_matrix_rows",
        lambda course_id, owner_sub, limit, offset, units: [
            {
                "student": {
                    "sub": "student-1",
                    "name": "Anna",
                    "href": "/diagnostics/learners/student-1",
                },
                "cells": [
                    {
                        "unit_id": "unit-1",
                        "submitted_tasks": 1,
                        "total_tasks": 2,
                        "href": f"/live/courses/{course_id}/units/unit-1",
                    },
                    {
                        "unit_id": "unit-2",
                        "submitted_tasks": 0,
                        "total_tasks": 3,
                        "href": f"/live/courses/{course_id}/units/unit-2",
                    },
                ],
            }
        ],
    )
    headers = _mock_bearer_auth(monkeypatch, sub="teacher-diagnostics", roles=["teacher"], name="Ada")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.get("/api/diagnostics/views/courses/course-1/matrix", headers=headers)

    assert response.status_code == 200
    assert response.headers.get("Cache-Control") == "private, no-store"
    assert response.json() == {
        "user": {
            "sub": "teacher-diagnostics",
            "name": "Ada",
            "role": "teacher",
            "roles": ["teacher"],
        },
        "course": {
            "id": "course-1",
            "title": "Mathe 9b",
            "href": "/diagnostics/courses/course-1",
        },
        "units": [
            {
                "id": "unit-1",
                "title": "Brueche",
                "position": 1,
                "href": "/live/courses/course-1/units/unit-1",
            },
            {
                "id": "unit-2",
                "title": "Terme",
                "position": 2,
                "href": "/live/courses/course-1/units/unit-2",
            },
        ],
        "rows": [
            {
                "student": {
                    "sub": "student-1",
                    "name": "Anna",
                    "href": "/diagnostics/learners/student-1",
                },
                "cells": [
                    {
                        "unit_id": "unit-1",
                        "submitted_tasks": 1,
                        "total_tasks": 2,
                        "href": "/live/courses/course-1/units/unit-1",
                    },
                    {
                        "unit_id": "unit-2",
                        "submitted_tasks": 0,
                        "total_tasks": 3,
                        "href": "/live/courses/course-1/units/unit-2",
                    },
                ],
            }
        ],
    }


@pytest.mark.anyio
async def test_diagnostics_course_matrix_forbids_students(monkeypatch: pytest.MonkeyPatch) -> None:
    headers = _mock_bearer_auth(monkeypatch, sub="student-diagnostics", roles=["student"], name="Lena")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.get("/api/diagnostics/views/courses/course-1/matrix", headers=headers)

    assert response.status_code == 403
    assert response.json() == {"error": "forbidden"}


@pytest.mark.anyio
async def test_diagnostics_course_matrix_returns_not_found_for_missing_course(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(teaching_guards, "_guard_course_owner", lambda course_id, owner_sub, repo_provider=None: None)
    monkeypatch.setattr(app_routes, "_get_teacher_course", lambda course_id, owner_sub: None)
    headers = _mock_bearer_auth(monkeypatch, sub="teacher-diagnostics", roles=["teacher"], name="Ada")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.get("/api/diagnostics/views/courses/course-404/matrix", headers=headers)

    assert response.status_code == 404
    assert response.json() == {"error": "not_found"}
