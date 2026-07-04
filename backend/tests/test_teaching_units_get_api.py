"""
Teaching API: GET /api/teaching/units/{id}

Scenarios
- Owner fetches by id -> 200
- Different teacher fetches same id -> 403
- Owner fetches unknown id -> 404
"""

from __future__ import annotations

import uuid as _uuid
from pathlib import Path
import sys

import pytest
import httpx
from httpx import ASGITransport


REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
sys.path.insert(0, str(WEB_DIR))

import main  # type: ignore
from runtime_auth_helpers import install_session_store


pytestmark = pytest.mark.anyio("asyncio")


async def _create_unit(client: httpx.AsyncClient, *, title: str, teacher_cookie: str) -> str:
    client.cookies.set(main.SESSION_COOKIE_NAME, teacher_cookie)
    r = await client.post("/api/teaching/units", json={"title": title}, headers={"Origin": "http://test"})
    assert r.status_code == 201
    body = r.json()
    assert isinstance(body, dict) and body.get("id")
    return body["id"]


@pytest.mark.anyio
async def test_get_unit_by_id_owner_returns_200(monkeypatch: pytest.MonkeyPatch):
    store = install_session_store(monkeypatch, main)
    owner = store.create(sub="t-unit-owner-1", name="Owner", roles=["teacher"])
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test", headers={"Origin": "http://test"}) as c:
        uid = await _create_unit(c, title="Genetik", teacher_cookie=owner.session_id)
        c.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        r = await c.get(f"/api/teaching/units/{uid}")
    assert r.status_code == 200
    body = r.json()
    assert body.get("id") == uid
    assert body.get("title") == "Genetik"


@pytest.mark.anyio
async def test_get_unit_by_id_non_author_returns_403(monkeypatch: pytest.MonkeyPatch):
    store = install_session_store(monkeypatch, main)
    owner = store.create(sub="t-unit-owner-2", name="Owner", roles=["teacher"])
    intruder = store.create(sub="t-unit-other-2", name="Other", roles=["teacher"])
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test", headers={"Origin": "http://test"}) as c:
        uid = await _create_unit(c, title="Ökologie", teacher_cookie=owner.session_id)
        c.cookies.set(main.SESSION_COOKIE_NAME, intruder.session_id)
        r = await c.get(f"/api/teaching/units/{uid}")
    assert r.status_code == 403


@pytest.mark.anyio
async def test_get_unit_by_id_unknown_returns_404(monkeypatch: pytest.MonkeyPatch):
    store = install_session_store(monkeypatch, main)
    owner = store.create(sub="t-unit-owner-3", name="Owner", roles=["teacher"])
    unknown = str(_uuid.uuid4())
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test", headers={"Origin": "http://test"}) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        r = await c.get(f"/api/teaching/units/{unknown}")
    assert r.status_code == 404


@pytest.mark.anyio
async def test_get_unit_invalid_id_returns_400(monkeypatch: pytest.MonkeyPatch):
    store = install_session_store(monkeypatch, main)
    owner = store.create(sub="t-unit-owner-4", name="Owner", roles=["teacher"])
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test", headers={"Origin": "http://test"}) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        r = await c.get("/api/teaching/units/not-a-uuid")
    assert r.status_code == 400
    body = r.json()
    assert body.get("detail") == "invalid_unit_id"
    assert r.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_get_unit_by_id_owner_without_origin_header_still_returns_200(monkeypatch: pytest.MonkeyPatch):
    """GET must not require CSRF Origin/Referer headers."""
    store = install_session_store(monkeypatch, main)
    owner = store.create(sub="t-unit-owner-no-origin", name="Owner", roles=["teacher"])
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
        uid = await _create_unit(c, title="Evolution", teacher_cookie=owner.session_id)
        c.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        r = await c.get(f"/api/teaching/units/{uid}")
    assert r.status_code == 200
