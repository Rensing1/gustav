"""Contract tests for the BFF-to-backend authorization bridge.

Why:
    SvelteKit should call FastAPI as a server-side BFF without forwarding the
    backend session cookie to the browser. The backend therefore needs a
    controlled internal Authorization transport based on the mapped session id.
"""

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
async def test_session_bootstrap_accepts_internal_authorization_bearer(monkeypatch: pytest.MonkeyPatch) -> None:
    store = SessionStore()
    monkeypatch.setattr(main, "SESSION_STORE", store)
    rec = store.create(sub="teacher-bff", roles=["teacher"], name="Ada", ttl_seconds=60)

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.get(
            "/api/app/session-bootstrap",
            headers={"Authorization": f"Bearer session:{rec.session_id}"},
        )

    assert response.status_code == 200
    assert response.json()["user"]["sub"] == "teacher-bff"
    assert response.json()["start_target"] == "/teaching"


@pytest.mark.anyio
async def test_api_me_accepts_internal_authorization_bearer(monkeypatch: pytest.MonkeyPatch) -> None:
    store = SessionStore()
    monkeypatch.setattr(main, "SESSION_STORE", store)
    rec = store.create(sub="student-bff", roles=["student"], name="Lena", ttl_seconds=60)

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.get(
            "/api/me",
            headers={"Authorization": f"Bearer session:{rec.session_id}"},
        )

    assert response.status_code == 200
    assert response.json()["sub"] == "student-bff"

