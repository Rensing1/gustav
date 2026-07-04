"""
Guard-order tests to prevent error-oracle leaks for Units and Sections.

Intent:
    Non-authors must not learn about payload validation outcomes. The handler
    must check ownership (author) before validating the JSON body for PATCH.

Scenarios:
    - PATCH Unit with empty body as non-author → 403/404 (not 400).
    - PATCH Section with empty body as non-author → 403/404 (not 400).
"""
from __future__ import annotations

import importlib

import pytest
import httpx
from httpx import ASGITransport

from backend.tests.runtime_auth_helpers import install_session_store
from backend.tests.utils.db import require_db_or_skip as _require_db_or_skip

main = importlib.import_module("backend.web.main")
pytestmark = pytest.mark.anyio("asyncio")


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=ASGITransport(app=main.app),
        base_url="http://test",
        headers={"Origin": "http://test"},
    )


async def _create_unit(client: httpx.AsyncClient, title: str) -> dict:
    r = await client.post("/api/teaching/units", json={"title": title})
    assert r.status_code == 201
    return r.json()


async def _create_section(client: httpx.AsyncClient, unit_id: str, title: str) -> dict:
    r = await client.post(f"/api/teaching/units/{unit_id}/sections", json={"title": title})
    assert r.status_code == 201
    return r.json()


@pytest.mark.anyio
async def test_non_author_unit_patch_empty_body_returns_403_or_404(monkeypatch: pytest.MonkeyPatch):
    store = install_session_store(monkeypatch, main)
    _require_db_or_skip()
    teaching = importlib.import_module("backend.web.routes.teaching")

    try:
        from backend.teaching.repo_db import DBTeachingRepo

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    author = store.create(sub="teacher-guard-unit-author", name="A", roles=["teacher"])
    other = store.create(sub="teacher-guard-unit-other", name="B", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", author.session_id)
        unit = await _create_unit(client, "Mechanik")

        # Switch to non-author
        client.cookies.set("gustav_session", other.session_id)
        resp = await client.patch(f"/api/teaching/units/{unit['id']}", json={})
        assert resp.status_code in (403, 404), resp.text


@pytest.mark.anyio
async def test_non_author_section_patch_empty_body_returns_403_or_404(monkeypatch: pytest.MonkeyPatch):
    store = install_session_store(monkeypatch, main)
    _require_db_or_skip()
    teaching = importlib.import_module("backend.web.routes.teaching")

    try:
        from backend.teaching.repo_db import DBTeachingRepo

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    author = store.create(sub="teacher-guard-sec-author", name="A", roles=["teacher"])
    other = store.create(sub="teacher-guard-sec-other", name="B", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", author.session_id)
        unit = await _create_unit(client, "Optik")
        sec = await _create_section(client, unit["id"], "Einführung")

        # Switch to non-author
        client.cookies.set("gustav_session", other.session_id)
        resp = await client.patch(
            f"/api/teaching/units/{unit['id']}/sections/{sec['id']}", json={}
        )
        assert resp.status_code in (403, 404), resp.text
