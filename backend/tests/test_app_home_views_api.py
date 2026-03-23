"""API tests for the first concrete room read-models."""

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
async def test_learner_home_returns_student_courses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = SessionStore()
    monkeypatch.setattr(main, "SESSION_STORE", store)
    monkeypatch.setattr(
        app_routes,
        "_list_learner_courses",
        lambda student_sub, limit, offset: [
            {"id": "course-1", "title": "Mathe 9b"},
            {"id": "course-2", "title": "Informatik"},
        ],
    )
    rec = store.create(sub="student-home", roles=["student"], name="Lena", ttl_seconds=60)

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set("gustav_session", rec.session_id)
        response = await client.get("/api/learning/views/learner-home")

    assert response.status_code == 200
    assert response.headers.get("Cache-Control") == "private, no-store"
    assert response.json()["user"]["sub"] == "student-home"
    assert response.json()["courses"] == [
        {"id": "course-1", "title": "Mathe 9b", "href": "/learning/courses/course-1"},
        {"id": "course-2", "title": "Informatik", "href": "/learning/courses/course-2"},
    ]


@pytest.mark.anyio
async def test_teacher_home_returns_navigation_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    store = SessionStore()
    monkeypatch.setattr(main, "SESSION_STORE", store)
    rec = store.create(sub="teacher-home", roles=["teacher"], name="Ada", ttl_seconds=60)

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set("gustav_session", rec.session_id)
        response = await client.get("/api/teaching/views/teacher-home")

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["sub"] == "teacher-home"
    assert body["entries"] == [
        {
            "id": "courses",
            "title": "Kurse",
            "href": "/courses",
            "description": "Kurse organisieren und betreuen.",
        },
        {
            "id": "units",
            "title": "Lerneinheiten",
            "href": "/units",
            "description": "Lerneinheiten bearbeiten und strukturieren.",
        },
        {
            "id": "diagnostics",
            "title": "Diagnostik",
            "href": "/diagnostics",
            "description": "Diagnostische Sichten fuer Lehrkraefte.",
        },
        {
            "id": "live",
            "title": "Live",
            "href": "/live",
            "description": "Operative Kurs-Lerneinheit-Matrix.",
        },
    ]


@pytest.mark.anyio
async def test_learner_home_forbids_teacher(monkeypatch: pytest.MonkeyPatch) -> None:
    store = SessionStore()
    monkeypatch.setattr(main, "SESSION_STORE", store)
    rec = store.create(sub="teacher-home", roles=["teacher"], name="Ada", ttl_seconds=60)

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set("gustav_session", rec.session_id)
        response = await client.get("/api/learning/views/learner-home")

    assert response.status_code == 403
    assert response.json() == {"error": "forbidden"}

