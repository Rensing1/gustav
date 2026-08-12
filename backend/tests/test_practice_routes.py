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

    def create_native_attempt(self, student_sub: str, session_id: str, item_id: str, **kwargs):
        return {"attempt_id": "22222222-2222-2222-2222-222222222222", "status": "pending"}

    def get_attempt(self, student_sub: str, attempt_id: str):
        raise LookupError("practice_attempt_not_found")

    def reveal_solution(self, student_sub: str, session_id: str, item_id: str):
        return {"model_solution_md": "Eine sichere Musterlösung"}


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
async def test_session_creation_is_always_available(app: FastAPI) -> None:
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


@pytest.mark.anyio
async def test_native_attempt_requires_idempotency_key(app: FastAPI) -> None:
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/learning/practice/sessions/11111111-1111-1111-1111-111111111111/items/33333333-3333-3333-3333-333333333333/attempts",
            headers={"Origin": "http://test"},
            json={"answer_text": "Antwort"},
        )
    assert response.status_code == 400
    assert response.json()["detail"] == "missing_idempotency_key"


@pytest.mark.anyio
async def test_native_attempt_is_accepted_for_async_analysis(app: FastAPI) -> None:
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/learning/practice/sessions/11111111-1111-1111-1111-111111111111/items/33333333-3333-3333-3333-333333333333/attempts",
            headers={"Origin": "http://test", "Idempotency-Key": "attempt-key"},
            json={"answer_text": "Antwort"},
        )
    assert response.status_code == 202
    assert response.json()["status"] == "pending"


@pytest.mark.anyio
async def test_reused_idempotency_key_for_another_item_is_stable_conflict(
    app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    def conflict(*args, **kwargs):  # noqa: ANN002, ANN003
        raise ValueError("practice_idempotency_conflict")

    monkeypatch.setattr(practice._service(), "create_native_attempt", conflict)
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/learning/practice/sessions/11111111-1111-1111-1111-111111111111/items/33333333-3333-3333-3333-333333333333/attempts",
            headers={"Origin": "http://test", "Idempotency-Key": "reused-key"},
            json={"answer_text": "Antwort"},
        )
    assert response.status_code == 409
    assert response.json()["detail"] == "practice_idempotency_conflict"


@pytest.mark.anyio
async def test_foreign_attempt_is_fail_closed_404(app: FastAPI) -> None:
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/learning/practice/attempts/22222222-2222-2222-2222-222222222222"
        )
    assert response.status_code == 404
