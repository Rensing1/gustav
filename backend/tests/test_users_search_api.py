"""
Users API — Search endpoint for student lookup by name.
"""
from __future__ import annotations

import importlib
import pytest
import httpx
from httpx import ASGITransport

from backend.tests.runtime_auth_helpers import install_session_store

pytestmark = pytest.mark.anyio("asyncio")

main = importlib.import_module("backend.web.main")
users_routes = importlib.import_module("backend.web.routes.users")


async def _client():
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test")


@pytest.mark.anyio
async def test_search_requires_teacher_and_min_query(monkeypatch: pytest.MonkeyPatch):
    store = install_session_store(monkeypatch, main)
    teacher = store.create(sub="teacher-S", name="Teach", roles=["teacher"])
    student = store.create(sub="student-S", name="Stud", roles=["student"])

    def fake_search(*, role: str, q: str, limit: int):
        return [{"sub": "s-1", "name": "Max Musterschüler"}]

    monkeypatch.setattr(users_routes, "search_users_by_name", fake_search, raising=False)

    async with (await _client()) as client:
        # Student forbidden
        client.cookies.set("gustav_session", student.session_id)
        r0 = await client.get("/api/users/search?q=ma&role=student&limit=5")
        assert r0.status_code == 403

        # Teacher: q too short
        client.cookies.set("gustav_session", teacher.session_id)
        r1 = await client.get("/api/users/search?q=m&role=student&limit=5")
        assert r1.status_code == 400
        assert r1.json().get("detail") == "q_too_short"

        # Teacher: ok
        r2 = await client.get("/api/users/search?q=ma&role=student&limit=5")
        assert r2.status_code == 200
        arr = r2.json()
        assert arr and arr[0]["sub"] == "s-1"
        assert arr[0]["name"] == "Max Musterschüler"
        # Responses must not be cached (privacy)
        cc = r2.headers.get("Cache-Control", "")
        assert "no-store" in cc and "private" in cc


@pytest.mark.anyio
async def test_search_invalid_role_returns_400(monkeypatch: pytest.MonkeyPatch):
    store = install_session_store(monkeypatch, main)
    teacher = store.create(sub="teacher-S2", name="Teach", roles=["teacher"])

    def fake_search(*, role: str, q: str, limit: int):
        return []

    monkeypatch.setattr(users_routes, "search_users_by_name", fake_search, raising=False)

    async with (await _client()) as client:
        client.cookies.set("gustav_session", teacher.session_id)
        r = await client.get("/api/users/search?q=ma&role=hacker&limit=5")
        assert r.status_code == 400
        assert r.json().get("error") == "bad_request"
        assert r.json().get("detail") == "invalid_role"
