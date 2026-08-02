"""HTTP adapter tests for learner dialog endpoints."""

from __future__ import annotations

import importlib
from fastapi import FastAPI, Request
import httpx
import pytest

_dialog_routes = importlib.import_module("backend.web.routes.learning_dialogs")
learning_dialog_router = _dialog_routes.learning_dialog_router
set_dialog_dependencies = _dialog_routes.set_dialog_dependencies


COURSE_ID = "11111111-1111-4111-8111-111111111111"
TASK_ID = "22222222-2222-4222-8222-222222222222"
SESSION_ID = "33333333-3333-4333-8333-333333333333"


class UseCases:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def _result(self) -> dict:
        return {"id": SESSION_ID, "status": "active", "round_count": 0, "turns": []}

    def start(self, **kwargs):  # type: ignore[no-untyped-def]
        self.calls.append(("start", kwargs))
        return self._result()

    def get(self, **kwargs):  # type: ignore[no-untyped-def]
        self.calls.append(("get", kwargs))
        return self._result()

    def send_turn(self, **kwargs):  # type: ignore[no-untyped-def]
        self.calls.append(("send", kwargs))
        return self._result()

    def retry_turn(self, **kwargs):  # type: ignore[no-untyped-def]
        self.calls.append(("retry", kwargs))
        return self._result()

    def complete(self, **kwargs):  # type: ignore[no-untyped-def]
        self.calls.append(("complete", kwargs))
        return {"session": {**self._result(), "status": "completed"}, "submission": {"kind": "dialog"}}

    def abandon(self, **kwargs):  # type: ignore[no-untyped-def]
        self.calls.append(("abandon", kwargs))
        return {**self._result(), "status": "abandoned"}


def _app(usecases: UseCases) -> FastAPI:
    app = FastAPI()

    @app.middleware("http")
    async def student(request: Request, call_next):  # type: ignore[no-untyped-def]
        request.state.user = {"sub": "student-1", "roles": ["student"]}
        return await call_next(request)

    app.include_router(learning_dialog_router)
    set_dialog_dependencies(usecases=usecases)
    return app


@pytest.mark.anyio
async def test_start_and_send_turn_forward_student_scope_and_idempotency() -> None:
    usecases = UseCases()
    base = f"/api/learning/courses/{COURSE_ID}/tasks/{TASK_ID}/dialog-sessions"
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=_app(usecases)), base_url="http://test") as client:
        started = await client.post(base, headers={"Origin": "http://test"})
        sent = await client.post(
            f"{base}/{SESSION_ID}/turns",
            json={"student_message_md": "Meine Antwort", "used_sentence_starter_md": "Ich denke …", "used_sentence_starter_source": "initial"},
            headers={"Origin": "http://test", "Idempotency-Key": "turn-1"},
        )

    assert started.status_code == 201
    assert sent.status_code == 200
    assert usecases.calls[0][1]["student_sub"] == "student-1"
    assert usecases.calls[1][1]["idempotency_key"] == "turn-1"


@pytest.mark.anyio
async def test_mutation_rejects_missing_idempotency_key() -> None:
    usecases = UseCases()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=_app(usecases)), base_url="http://test") as client:
        response = await client.post(
            f"/api/learning/courses/{COURSE_ID}/tasks/{TASK_ID}/dialog-sessions/{SESSION_ID}/turns",
            json={"student_message_md": "Antwort"},
            headers={"Origin": "http://test"},
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "invalid_idempotency_key"


@pytest.mark.anyio
async def test_cross_site_start_is_forbidden() -> None:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=_app(UseCases())), base_url="http://test") as client:
        response = await client.post(
            f"/api/learning/courses/{COURSE_ID}/tasks/{TASK_ID}/dialog-sessions",
            headers={"Origin": "https://evil.example"},
        )

    assert response.status_code == 403
