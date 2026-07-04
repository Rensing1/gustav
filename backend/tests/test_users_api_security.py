"""
Users API — Security headers and basic authz on directory endpoints.

Validates that error responses are non-cacheable and that authorization is
enforced. Directory backend is not exercised (returns empty list on success).
"""
from __future__ import annotations

import pytest
import httpx
from httpx import ASGITransport

import main  # type: ignore  # noqa: E402
from backend.tests.runtime_auth_helpers import install_session_store  # noqa: E402


pytestmark = pytest.mark.anyio("asyncio")


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test")


def _setup_sessions(monkeypatch: pytest.MonkeyPatch) -> tuple[str, str]:
    store = install_session_store(monkeypatch, main)
    teacher = store.create(sub="u-teacher-users", name="Teacher", roles=["teacher"])
    student = store.create(sub="u-student-users", name="Student", roles=["student"])
    return teacher.session_id, student.session_id


@pytest.mark.anyio
async def test_users_search_forbidden_for_non_teacher(monkeypatch: pytest.MonkeyPatch):
    t_sid, s_sid = _setup_sessions(monkeypatch)
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, s_sid)
        r = await c.get("/api/users/search", params={"q": "ab", "role": "student"})
        assert r.status_code == 403
        assert r.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_users_search_400_has_private_no_store_header(monkeypatch: pytest.MonkeyPatch):
    t_sid, _ = _setup_sessions(monkeypatch)
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, t_sid)
        # q too short
        r = await c.get("/api/users/search", params={"q": "a", "role": "student"})
        assert r.status_code == 400
        assert r.headers.get("Cache-Control") == "private, no-store"
        # invalid role
        r2 = await c.get("/api/users/search", params={"q": "al", "role": "unknown"})
        assert r2.status_code == 400
        assert r2.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_users_list_headers_and_authz(monkeypatch: pytest.MonkeyPatch):
    t_sid, s_sid = _setup_sessions(monkeypatch)
    async with (await _client()) as c:
        # forbidden for student
        c.cookies.set(main.SESSION_COOKIE_NAME, s_sid)
        r_forbid = await c.get("/api/users/list", params={"role": "student"})
        assert r_forbid.status_code == 403
        assert r_forbid.headers.get("Cache-Control") == "private, no-store"

        # bad request for invalid role (as teacher)
        c.cookies.set(main.SESSION_COOKIE_NAME, t_sid)
        r_bad = await c.get("/api/users/list", params={"role": "invalid"})
        assert r_bad.status_code == 400
        assert r_bad.headers.get("Cache-Control") == "private, no-store"
