"""
Learning API — submission persistence must fail closed (no silent 202 fallback).

Why:
    If the Learning repository / database is unavailable, the API must not
    pretend a submission was accepted. Otherwise we risk silent data loss and
    broken monitoring. "local = prod" means: persistence errors must surface
    as 5xx/503.

This test simulates a repo failure by patching CreateSubmissionUseCase to raise.
"""

from __future__ import annotations

import importlib
import uuid

import pytest
import httpx
from httpx import ASGITransport

from backend.tests.runtime_auth_helpers import install_session_store

main = importlib.import_module("backend.web.main")


pytestmark = pytest.mark.anyio("asyncio")


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test")


@pytest.mark.anyio
async def test_create_submission_returns_503_when_persistence_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    session_store = install_session_store(monkeypatch, main)
    student = session_store.create(sub="s-fail-closed", name="S", roles=["student"])

    class _FailUC:
        def __init__(self, *a, **k):
            pass

        def execute(self, input_data):
            raise RuntimeError("db down")

    # Patch the package-oriented call site.
    learning_routes = importlib.import_module("backend.web.routes.learning")
    monkeypatch.setattr(learning_routes, "CreateSubmissionUseCase", _FailUC)
    # Patch the actual FastAPI route endpoint (ground truth) to avoid module aliasing issues.
    for route in getattr(main.app, "routes", []):
        if getattr(route, "path", None) != "/api/learning/courses/{course_id}/tasks/{task_id}/submissions":
            continue
        methods = set(getattr(route, "methods", []) or [])
        if "POST" not in methods:
            continue
        endpoint = getattr(route, "endpoint", None)
        if callable(endpoint):
            monkeypatch.setitem(endpoint.__globals__, "CreateSubmissionUseCase", _FailUC)  # type: ignore[attr-defined]
            break
    else:  # pragma: no cover - defensive guard for unexpected router changes
        raise AssertionError("Expected create_submission route not registered on main.app")

    course_id = str(uuid.uuid4())
    task_id = str(uuid.uuid4())

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)
        r = await c.post(
            f"/api/learning/courses/{course_id}/tasks/{task_id}/submissions",
            json={"kind": "text", "text_body": "Hallo"},
            headers={"Origin": "http://test"},
        )

    assert r.status_code == 503
    assert r.headers.get("Cache-Control") == "private, no-store"
    assert r.headers.get("Vary") == "Origin"
    payload = r.json()
    assert payload.get("error") == "service_unavailable"
    assert payload.get("detail") == "submission_persistence_unavailable"
