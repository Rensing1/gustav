"""
Learning API — H5P submissions should return 201 (synchronous persistence).

Why:
    For `Task.kind=h5p`, the submission is persisted synchronously with
    `analysis_status="completed"` (no async worker job). The API should reflect
    that by returning HTTP 201.

Note:
    This is a route-level unit test. It patches the use case to avoid DB
    dependencies while still exercising request validation and auth.
"""

from __future__ import annotations

import uuid

import httpx
import pytest
from httpx import ASGITransport

import main  # type: ignore  # noqa: E402
from backend.tests.runtime_auth_helpers import install_session_store  # noqa: E402


pytestmark = pytest.mark.anyio("asyncio")


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=ASGITransport(app=main.app),
        base_url="http://test",
        headers={"Origin": "http://test"},
    )


@pytest.mark.anyio
async def test_learning_create_submission_returns_201_for_h5p(monkeypatch: pytest.MonkeyPatch) -> None:
    store = install_session_store(monkeypatch, main)
    student = store.create(sub="s-h5p-201", name="S", roles=["student"])

    class _OKUC:
        def __init__(self, *a, **k):
            pass

        def execute(self, input_data):
            return {
                "id": str(uuid.uuid4()),
                "attempt_nr": 1,
                "kind": "h5p",
                "score_raw": 2,
                "score_max": 3,
                "analysis_status": "completed",
                "analysis_json": None,
                "feedback_md": None,
                "error_code": None,
                "created_at": "2026-01-11T00:00:00+00:00",
                "completed_at": "2026-01-11T00:00:00+00:00",
            }

    from backend.web.routes import learning as learning_routes

    monkeypatch.setattr(learning_routes, "CreateSubmissionUseCase", _OKUC)
    try:
        import importlib as _importlib

        lr_alias = _importlib.import_module("routes.learning")
        monkeypatch.setattr(lr_alias, "CreateSubmissionUseCase", _OKUC, raising=False)
    except Exception:
        pass
    # Patch the actual FastAPI route endpoint (ground truth) to avoid module aliasing issues.
    for route in getattr(main.app, "routes", []):
        if getattr(route, "path", None) != "/api/learning/courses/{course_id}/tasks/{task_id}/submissions":
            continue
        methods = set(getattr(route, "methods", []) or [])
        if "POST" not in methods:
            continue
        endpoint = getattr(route, "endpoint", None)
        if callable(endpoint):
            monkeypatch.setitem(endpoint.__globals__, "CreateSubmissionUseCase", _OKUC)  # type: ignore[attr-defined]
            break
    else:  # pragma: no cover - defensive guard for unexpected router changes
        raise AssertionError("Expected create_submission route not registered on main.app")

    course_id = str(uuid.uuid4())
    task_id = str(uuid.uuid4())
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)
        r = await c.post(
            f"/api/learning/courses/{course_id}/tasks/{task_id}/submissions",
            headers={"Idempotency-Key": "h5p_score_1"},
            json={"kind": "h5p", "score_raw": 2, "score_max": 3},
        )

    assert r.status_code == 201
    assert r.headers.get("Cache-Control") == "private, no-store"
