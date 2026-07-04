"""Contract tests for removing the transitional BFF session transport.

Why:
    The SvelteKit BFF now sends real bearer JWTs to FastAPI. The temporary
    `Bearer session:<id>` transport must no longer authenticate requests.
"""

from __future__ import annotations

import importlib

import httpx
import pytest
from httpx import ASGITransport


main = importlib.import_module("backend.web.main")
from backend.tests.runtime_auth_helpers import install_session_store


pytestmark = pytest.mark.anyio("asyncio")


@pytest.mark.anyio
async def test_session_bootstrap_rejects_transitional_session_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = install_session_store(monkeypatch, main)
    rec = store.create(sub="teacher-bff", roles=["teacher"], name="Ada", ttl_seconds=60)

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.get(
            "/api/app/session-bootstrap",
            headers={"Authorization": f"Bearer session:{rec.session_id}"},
        )

    assert response.status_code == 401
    assert response.json()["error"] == "unauthenticated"


@pytest.mark.anyio
async def test_api_me_rejects_transitional_session_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    store = install_session_store(monkeypatch, main)
    rec = store.create(sub="student-bff", roles=["student"], name="Lena", ttl_seconds=60)

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.get(
            "/api/me",
            headers={"Authorization": f"Bearer session:{rec.session_id}"},
        )

    assert response.status_code == 401
    assert response.json()["error"] == "unauthenticated"
