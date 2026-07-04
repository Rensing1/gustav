"""Legacy student learning SSR routes are retired after the SvelteKit cutover."""

from __future__ import annotations

import importlib

import httpx
import pytest
from httpx import ASGITransport


main = importlib.import_module("backend.web.main")
from backend.tests.runtime_auth_helpers import install_session_store


pytestmark = pytest.mark.anyio("asyncio")


@pytest.fixture()
def student_session(monkeypatch: pytest.MonkeyPatch) -> str:
    store = install_session_store(monkeypatch, main)
    rec = store.create(sub="student-learning-retired", roles=["student"], name="Lena", ttl_seconds=60)
    return rec.session_id


async def _client_with_student(student_session: str) -> httpx.AsyncClient:
    client = httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test")
    client.cookies.set(main.SESSION_COOKIE_NAME, student_session)
    return client


@pytest.mark.anyio
async def test_learning_legacy_unit_page_returns_gone(student_session: str) -> None:
    async with await _client_with_student(student_session) as client:
        response = await client.get(
            "/learning/courses/11111111-1111-1111-1111-111111111111/units/22222222-2222-2222-2222-222222222222"
        )

    assert response.status_code == 410
    assert response.headers.get("Cache-Control") == "private, no-store"
    assert "legacy route retired" in response.text.lower()


@pytest.mark.anyio
async def test_learning_legacy_module_fragment_returns_gone(student_session: str) -> None:
    async with await _client_with_student(student_session) as client:
        response = await client.get(
            "/learning/courses/11111111-1111-1111-1111-111111111111/units/22222222-2222-2222-2222-222222222222/modules/33333333-3333-3333-3333-333333333333/fragment"
        )

    assert response.status_code == 410
    assert response.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_learning_legacy_submit_returns_gone(student_session: str) -> None:
    async with await _client_with_student(student_session) as client:
        response = await client.post(
            "/learning/courses/11111111-1111-1111-1111-111111111111/tasks/22222222-2222-2222-2222-222222222222/submit",
            data={"text_body": "Hallo"},
            headers={"Origin": "http://test"},
        )

    assert response.status_code == 410
    assert response.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_learning_legacy_history_routes_return_gone(student_session: str) -> None:
    async with await _client_with_student(student_session) as client:
        history = await client.get(
            "/learning/courses/11111111-1111-1111-1111-111111111111/tasks/22222222-2222-2222-2222-222222222222/history"
        )
        poll = await client.get(
            "/learning/courses/11111111-1111-1111-1111-111111111111/tasks/22222222-2222-2222-2222-222222222222/history/poll"
        )

    assert history.status_code == 410
    assert poll.status_code == 410
    assert history.headers.get("Cache-Control") == "private, no-store"
    assert poll.headers.get("Cache-Control") == "private, no-store"
