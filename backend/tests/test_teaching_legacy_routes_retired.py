"""Legacy teacher SSR trees are retired after the SvelteKit cutover."""

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
from backend.tests.runtime_auth_helpers import install_session_store


pytestmark = pytest.mark.anyio("asyncio")


@pytest.fixture()
def teacher_session(monkeypatch: pytest.MonkeyPatch) -> str:
    store = install_session_store(monkeypatch, main)
    rec = store.create(sub="teacher-legacy-routes", roles=["teacher"], name="Ada", ttl_seconds=60)
    return rec.session_id


@pytest.fixture()
def student_session(monkeypatch: pytest.MonkeyPatch) -> str:
    store = install_session_store(monkeypatch, main)
    rec = store.create(sub="student-legacy-routes", roles=["student"], name="Lena", ttl_seconds=60)
    return rec.session_id


async def _client_with_session(session_id: str) -> httpx.AsyncClient:
    client = httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test")
    client.cookies.set(main.SESSION_COOKIE_NAME, session_id)
    return client


@pytest.mark.anyio
async def test_teacher_legacy_course_and_unit_routes_return_gone(teacher_session: str) -> None:
    async with await _client_with_session(teacher_session) as client:
        responses = [
            await client.get("/courses"),
            await client.get("/courses/11111111-1111-1111-1111-111111111111/edit"),
            await client.get("/courses/11111111-1111-1111-1111-111111111111/modules"),
            await client.get("/courses/11111111-1111-1111-1111-111111111111/members"),
            await client.get("/units/11111111-1111-1111-1111-111111111111"),
            await client.get("/units/11111111-1111-1111-1111-111111111111/edit"),
        ]

    assert all(response.status_code == 410 for response in responses)
    assert all(response.headers.get("Cache-Control") == "private, no-store" for response in responses)


@pytest.mark.anyio
async def test_teacher_legacy_course_and_unit_writes_return_gone(teacher_session: str) -> None:
    async with await _client_with_session(teacher_session) as client:
        responses = [
            await client.post("/courses", data={"title": "Neu"}, headers={"Origin": "http://test"}),
            await client.post(
                "/courses/11111111-1111-1111-1111-111111111111/modules/create",
                data={"unit_id": "22222222-2222-2222-2222-222222222222"},
                headers={"Origin": "http://test"},
            ),
            await client.post("/units", data={"title": "Neu"}, headers={"Origin": "http://test"}),
            await client.post(
                "/courses/11111111-1111-1111-1111-111111111111/members",
                data={"student_sub": "student"},
                headers={"Origin": "http://test"},
            ),
        ]

    assert all(response.status_code == 410 for response in responses)
    assert all(response.headers.get("Cache-Control") == "private, no-store" for response in responses)


@pytest.mark.anyio
async def test_teacher_legacy_route_redirects_non_teachers(student_session: str) -> None:
    async with await _client_with_session(student_session) as client:
        response = await client.get("/courses/11111111-1111-1111-1111-111111111111/modules", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers.get("location") == "/"
