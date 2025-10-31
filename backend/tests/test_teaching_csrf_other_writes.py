"""
Teaching API — CSRF same-origin checks for additional write endpoints

Covers representative endpoints beyond visibility:
- POST /api/teaching/courses
- POST /api/teaching/units

Asserts 403 with detail=csrf_violation on cross-origin requests and success on
same-origin, with private, no-store cache headers on both paths.
"""
from __future__ import annotations

import pytest
import httpx
from httpx import ASGITransport

import main  # type: ignore  # noqa: E402
import routes.teaching as teaching  # type: ignore  # noqa: E402
from identity_access.stores import SessionStore  # type: ignore  # noqa: E402


pytestmark = pytest.mark.anyio("asyncio")


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test")


@pytest.mark.anyio
async def test_create_course_blocks_cross_origin_and_allows_same_origin(monkeypatch: pytest.MonkeyPatch):
    teaching.set_repo(teaching._Repo())  # type: ignore[attr-defined]
    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-csrf-course", name="Teach", roles=["teacher"])  # type: ignore
    csrf_calls = {"count": 0}
    original_guard = teaching._csrf_guard

    def _counting_guard(request):
        csrf_calls["count"] += 1
        return original_guard(request)

    monkeypatch.setattr(teaching, "_csrf_guard", _counting_guard)

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        # Cross-origin → 403 + csrf_violation
        r = await c.post("/api/teaching/courses", json={"title": "Kurs"}, headers={"Origin": "http://evil.local"})
        assert r.status_code == 403
        assert r.json().get("detail") == "csrf_violation"
        assert r.headers.get("Cache-Control") == "private, no-store"

        # Same-origin → 201 + private cache headers
        csrf_calls["count"] = 0
        r2 = await c.post("/api/teaching/courses", json={"title": "Kurs"}, headers={"Origin": "http://test"})
        assert r2.status_code == 201
        assert r2.headers.get("Cache-Control") == "private, no-store"
        assert csrf_calls["count"] == 1, "CSRF guard should be evaluated exactly once per request"


@pytest.mark.anyio
async def test_create_unit_blocks_cross_origin_and_allows_same_origin(monkeypatch: pytest.MonkeyPatch):
    teaching.set_repo(teaching._Repo())  # type: ignore[attr-defined]
    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-csrf-unit", name="Teach", roles=["teacher"])  # type: ignore
    csrf_calls = {"count": 0}
    original_guard = teaching._csrf_guard

    def _counting_guard(request):
        csrf_calls["count"] += 1
        return original_guard(request)

    monkeypatch.setattr(teaching, "_csrf_guard", _counting_guard)

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        # Cross-origin → 403 + csrf_violation
        r = await c.post("/api/teaching/units", json={"title": "Unit"}, headers={"Origin": "http://evil.local"})
        assert r.status_code == 403
        assert r.json().get("detail") == "csrf_violation"
        assert r.headers.get("Cache-Control") == "private, no-store"

        # Same-origin → 201 + private cache headers
        csrf_calls["count"] = 0
        r2 = await c.post("/api/teaching/units", json={"title": "Unit"}, headers={"Origin": "http://test"})
        assert r2.status_code == 201
        assert r2.headers.get("Cache-Control") == "private, no-store"
        assert csrf_calls["count"] == 1, "CSRF guard should be evaluated exactly once per request"
