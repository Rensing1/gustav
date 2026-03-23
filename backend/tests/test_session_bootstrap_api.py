"""API tests for the first room read-model: session bootstrap."""

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


pytestmark = pytest.mark.anyio("asyncio")


@pytest.mark.anyio
async def test_session_bootstrap_returns_student_start_target(monkeypatch: pytest.MonkeyPatch) -> None:
    store = SessionStore()
    monkeypatch.setattr(main, "SESSION_STORE", store)
    rec = store.create(sub="student-1", roles=["student"], name="Lena", ttl_seconds=60)

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set("gustav_session", rec.session_id)
        response = await client.get("/api/app/session-bootstrap")

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
    store = SessionStore()
    monkeypatch.setattr(main, "SESSION_STORE", store)
    rec = store.create(sub="teacher-1", roles=["teacher"], name="Ada", ttl_seconds=60)

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set("gustav_session", rec.session_id)
        response = await client.get("/api/app/session-bootstrap")

    assert response.status_code == 200
    assert response.json()["start_target"] == "/teaching"
    assert response.json()["spaces"] == ["teaching", "diagnostics", "live"]


@pytest.mark.anyio
async def test_session_bootstrap_requires_session() -> None:
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.get("/api/app/session-bootstrap")

    assert response.status_code == 401
    assert response.headers.get("Cache-Control") == "private, no-store"
    assert response.json() == {"error": "unauthenticated"}

