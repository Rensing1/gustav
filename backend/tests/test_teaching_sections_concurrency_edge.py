"""
Teaching API — Sections concurrency on empty unit (regression test).

Ensures two concurrent POST /sections on an empty unit both succeed and
produce positions 1 and 2 without unique violations.
"""
from __future__ import annotations

import asyncio
import importlib

import pytest
import httpx
from httpx import ASGITransport

from backend.tests.runtime_auth_helpers import install_session_store
from backend.tests.utils.db import require_db_or_skip as _require_db_or_skip

main = importlib.import_module("backend.web.main")
pytestmark = [pytest.mark.anyio("asyncio"), pytest.mark.db_write]


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=ASGITransport(app=main.app),
        base_url="http://test",
        headers={"Origin": "http://test"},
    )


@pytest.mark.anyio
async def test_two_concurrent_creates_on_empty_unit_assign_contiguous_positions(monkeypatch: pytest.MonkeyPatch):
    store = install_session_store(monkeypatch, main)
    _require_db_or_skip()

    author = store.create(sub="teacher-sec-empty-concurrency", name="Autor", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", author.session_id)

        # Create empty unit
        unit = (await client.post("/api/teaching/units", json={"title": "Kinematik"})).json()

        async def create_section(title: str):
            return await client.post(f"/api/teaching/units/{unit['id']}/sections", json={"title": title})

        r1, r2 = await asyncio.gather(create_section("A"), create_section("B"))
        assert r1.status_code == 201 and r2.status_code == 201

        # Positions should be the contiguous set {1, 2} — no gaps or duplicates
        lst = await client.get(f"/api/teaching/units/{unit['id']}/sections")
        pos = [s["position"] for s in lst.json()]
        assert sorted(pos) == [1, 2]
