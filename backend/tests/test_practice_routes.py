"""HTTP adapter tests for learner practice sessions."""

from __future__ import annotations

import importlib

from fastapi import FastAPI, Request
from httpx import ASGITransport
import httpx
import pytest

practice = importlib.import_module("backend.web.routes.practice")


class Service:
    def list_stacks(self, student_sub: str):
        return [{"course_id": "course-1", "practice_module_id": "module-1"}]

    def get_active_session(self, student_sub: str):
        return None

    def create_session(self, student_sub: str, *, mode: object, stacks: object):
        return {
            "id": "11111111-1111-1111-1111-111111111111",
            "mode": mode,
            "status": "active",
            "started_at": "2026-08-08T12:00:00+00:00",
            "ended_at": None,
            "total_items": 1,
            "completed_items": 0,
            "current_item": None,
        }

    def get_session(self, student_sub: str, session_id: str):
        raise LookupError("practice_session_not_found")


@pytest.fixture
def app() -> FastAPI:
    application = FastAPI()

    @application.middleware("http")
    async def student(request: Request, call_next):  # noqa: ANN001
        request.state.user = {
            "sub": "student-1",
            "role": "student",
            "roles": ["student"],
            "name": "Lena",
        }
        return await call_next(request)

    application.include_router(practice.practice_router)
    practice.set_practice_service(Service())  # type: ignore[arg-type]
    yield application
    practice.set_practice_service(None)


@pytest.mark.anyio
async def test_active_session_returns_204_when_none_exists(app: FastAPI) -> None:
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/learning/practice/sessions/active")
    assert response.status_code == 204
    assert response.headers["cache-control"] == "private, no-store"


@pytest.mark.anyio
async def test_new_session_is_disabled_by_default(app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ENABLE_PRACTICE_SESSIONS", raising=False)
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/learning/practice/sessions",
            headers={"Origin": "http://test"},
            json={"mode": "due", "stacks": [{"course_id": "course-1", "practice_module_id": "module-1"}]},
        )
    assert response.status_code == 503
    assert response.json()["detail"] == "practice_disabled"


@pytest.mark.anyio
async def test_enabled_session_creation_returns_201(app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_PRACTICE_SESSIONS", "true")
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/learning/practice/sessions",
            headers={"Origin": "http://test"},
            json={"mode": "due", "stacks": [{"course_id": "course-1", "practice_module_id": "module-1"}]},
        )
    assert response.status_code == 201
    assert response.json()["status"] == "active"


@pytest.mark.anyio
async def test_foreign_session_is_fail_closed_404(app: FastAPI) -> None:
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/learning/practice/sessions/11111111-1111-1111-1111-111111111111"
        )
    assert response.status_code == 404
    assert response.json()["detail"] == "practice_session_not_found"
