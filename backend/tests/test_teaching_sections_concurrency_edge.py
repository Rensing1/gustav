"""
Teaching API — Sections concurrency on empty unit (regression test).

Ensures two concurrent POST /sections on an empty unit both succeed and
produce positions 1 and 2 without unique violations.
"""
from __future__ import annotations

import os
import asyncio
from pathlib import Path

import pytest
import httpx
from httpx import ASGITransport

pytestmark = pytest.mark.anyio("asyncio")

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
if str(WEB_DIR) not in os.sys.path:
    os.sys.path.insert(0, str(WEB_DIR))
import main  # type: ignore  # noqa: E402
from identity_access.stores import SessionStore  # type: ignore  # noqa: E402


from utils.db import require_db_or_skip as _require_db_or_skip


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test")


@pytest.mark.anyio
async def test_two_concurrent_creates_on_empty_unit_assign_contiguous_positions():
    main.SESSION_STORE = SessionStore()
    _require_db_or_skip()

    author = main.SESSION_STORE.create(sub="teacher-sec-empty-concurrency", name="Autor", roles=["teacher"])

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
