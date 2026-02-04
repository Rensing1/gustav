"""
SSR UI: modular units should use "modules" terminology on the sections page.

Why:
    In Option B, every module maps 1:1 to a unit section. Teachers still edit
    content (materials/tasks) per section, but the UI must make it clear that
    these sections represent modules in a modular learning unit.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys

import pytest
import httpx
from httpx import ASGITransport

pytestmark = pytest.mark.anyio("asyncio")


REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
sys.path.insert(0, str(WEB_DIR))

import main  # type: ignore  # noqa: E402
from identity_access.stores import SessionStore  # type: ignore  # noqa: E402


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=ASGITransport(app=main.app),
        base_url="http://test",
        headers={"Origin": "http://test"},
    )


@pytest.mark.anyio
async def test_modular_unit_sections_page_uses_module_headings():
    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-mod-sections-ui", name="Teacher", roles=["teacher"])

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        r = await c.post("/api/teaching/units", json={"title": "Mod Unit", "unit_type": "modular"})
        assert r.status_code == 201
        uid = r.json()["id"]

        page = await c.get(f"/units/{uid}")
        assert page.status_code == 200
        # The page should communicate the modular concept clearly.
        assert "Module" in page.text
        assert "Abschnitte" not in page.text.split("Module", 1)[0], "Heading should not claim sections for modular units"

