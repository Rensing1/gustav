"""API tests for the first diagnostics course matrix read-model."""

from __future__ import annotations

import httpx
import pytest
from httpx import ASGITransport
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))

import main  # type: ignore
from identity_access.stores import SessionStore  # type: ignore
from routes import app as app_routes  # type: ignore


pytestmark = pytest.mark.anyio("asyncio")


@pytest.mark.anyio
async def test_diagnostics_course_matrix_returns_course_units_and_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = SessionStore()
    monkeypatch.setattr(main, "SESSION_STORE", store)
    monkeypatch.setattr(app_routes.teaching_routes, "_guard_course_owner", lambda course_id, owner_sub: None)
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
                    "href": f"/diagnostics/courses/{course_id}/learners/student-1",
                },
                "cells": [
                    {
                        "unit_id": "unit-1",
                        "submitted_tasks": 1,
                        "total_tasks": 2,
                        "href": f"/diagnostics/courses/{course_id}/units/unit-1/learners/student-1",
                    },
                    {
                        "unit_id": "unit-2",
                        "submitted_tasks": 0,
                        "total_tasks": 3,
                        "href": f"/diagnostics/courses/{course_id}/units/unit-2/learners/student-1",
                    },
                ],
            }
        ],
    )
    rec = store.create(sub="teacher-diagnostics", roles=["teacher"], name="Ada", ttl_seconds=60)

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set("gustav_session", rec.session_id)
        response = await client.get("/api/diagnostics/views/courses/course-1/matrix")

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
                "href": "/diagnostics/courses/course-1/units/unit-1",
            },
            {
                "id": "unit-2",
                "title": "Terme",
                "position": 2,
                "href": "/diagnostics/courses/course-1/units/unit-2",
            },
        ],
        "rows": [
            {
                "student": {
                    "sub": "student-1",
                    "name": "Anna",
                    "href": "/diagnostics/courses/course-1/learners/student-1",
                },
                "cells": [
                    {
                        "unit_id": "unit-1",
                        "submitted_tasks": 1,
                        "total_tasks": 2,
                        "href": "/diagnostics/courses/course-1/units/unit-1/learners/student-1",
                    },
                    {
                        "unit_id": "unit-2",
                        "submitted_tasks": 0,
                        "total_tasks": 3,
                        "href": "/diagnostics/courses/course-1/units/unit-2/learners/student-1",
                    },
                ],
            }
        ],
    }


@pytest.mark.anyio
async def test_diagnostics_course_matrix_forbids_students(monkeypatch: pytest.MonkeyPatch) -> None:
    store = SessionStore()
    monkeypatch.setattr(main, "SESSION_STORE", store)
    rec = store.create(sub="student-diagnostics", roles=["student"], name="Lena", ttl_seconds=60)

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set("gustav_session", rec.session_id)
        response = await client.get("/api/diagnostics/views/courses/course-1/matrix")

    assert response.status_code == 403
    assert response.json() == {"error": "forbidden"}


@pytest.mark.anyio
async def test_diagnostics_course_matrix_returns_not_found_for_missing_course(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = SessionStore()
    monkeypatch.setattr(main, "SESSION_STORE", store)
    monkeypatch.setattr(app_routes.teaching_routes, "_guard_course_owner", lambda course_id, owner_sub: None)
    monkeypatch.setattr(app_routes, "_get_teacher_course", lambda course_id, owner_sub: None)
    rec = store.create(sub="teacher-diagnostics", roles=["teacher"], name="Ada", ttl_seconds=60)

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set("gustav_session", rec.session_id)
        response = await client.get("/api/diagnostics/views/courses/course-404/matrix")

    assert response.status_code == 404
    assert response.json() == {"error": "not_found"}
