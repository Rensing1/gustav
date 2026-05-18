"""API tests for the first room read-model: session bootstrap."""

from __future__ import annotations

import httpx
import logging
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
async def test_session_bootstrap_returns_student_start_target(monkeypatch: pytest.MonkeyPatch) -> None:
    headers = _mock_bearer_auth(monkeypatch, sub="student-1", roles=["student"], name="Lena")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.get("/api/app/session-bootstrap", headers=headers)

    assert response.status_code == 200
    assert response.headers.get("Cache-Control") == "private, no-store"
    assert response.json() == {
        "user": {
            "sub": "student-1",
            "name": "Lena",
            "role": "student",
            "roles": ["student"],
        },
        "start_target": "/learning",
        "spaces": ["learning"],
    }


@pytest.mark.anyio
async def test_session_bootstrap_returns_teacher_spaces(monkeypatch: pytest.MonkeyPatch) -> None:
    headers = _mock_bearer_auth(monkeypatch, sub="teacher-1", roles=["teacher"], name="Ada")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.get("/api/app/session-bootstrap", headers=headers)

    assert response.status_code == 200
    assert response.json()["start_target"] == "/teaching"
    assert response.json()["spaces"] == ["teaching", "diagnostics", "live"]


@pytest.mark.anyio
async def test_session_bootstrap_requires_bearer_even_with_cookie_session(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="gustav.identity_access")
    store = SessionStore()
    monkeypatch.setattr(main, "SESSION_STORE", store)
    rec = store.create(sub="student-cookie", roles=["student"], name="Lena", ttl_seconds=60)

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set("gustav_session", rec.session_id)
        response = await client.get("/api/app/session-bootstrap")

    assert response.status_code == 401
    assert response.headers.get("Cache-Control") == "private, no-store"
    assert response.json() == {"error": "unauthenticated"}
    logs = "\n".join(record.getMessage() for record in caplog.records)
    assert "auth_failure reason=session_bootstrap_missing_bearer path_class=api.app" in logs


@pytest.mark.anyio
async def test_session_bootstrap_logs_low_cardinality_auth_reason_without_sensitive_values(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="gustav.identity_access")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.get(
            "/api/app/session-bootstrap",
            headers={"Authorization": "Bearer sensitive.jwt"},
            cookies={"gustav_session": "sensitive-session"},
        )

    assert response.status_code == 401
    logs = "\n".join(record.getMessage() for record in caplog.records)
    assert "auth_failure reason=session_bootstrap_invalid_bearer path_class=api.app" in logs
    assert "path=/api/app/session-bootstrap" not in logs
    assert "sensitive.jwt" not in logs
    assert "sensitive-session" not in logs


@pytest.mark.anyio
async def test_auth_failure_logs_path_class_without_dynamic_identifiers(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="gustav.identity_access")

    dynamic_path = "/api/teaching/courses/course-1/units/unit-1/tasks/task-1/students/student@example.com/submissions/latest"
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.get(
            dynamic_path,
            headers={"Authorization": "Bearer sensitive.jwt"},
            cookies={"gustav_session": "sensitive-session"},
        )

    assert response.status_code == 401
    logs = "\n".join(record.getMessage() for record in caplog.records)
    assert "auth_failure reason=session_bootstrap_invalid_bearer path_class=api.teaching" in logs
    assert dynamic_path not in logs
    assert "student@example.com" not in logs
    assert "sensitive.jwt" not in logs
    assert "sensitive-session" not in logs
