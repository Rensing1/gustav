"""
SSR UI: teacher phase editor page for modular learning units.

Why:
    The API for modular unit phases exists, but the teacher SSR UI must expose
    it; otherwise teachers can create "modular" units yet have no way to manage
    phases (the core organizer concept).
"""

from __future__ import annotations

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
async def test_unit_phases_page_renders_for_modular_unit():
    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-ui-phases-1", name="Teacher", roles=["teacher"])

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        r_unit = await c.post("/api/teaching/units", json={"title": "Unit Phases UI", "unit_type": "modular"})
        assert r_unit.status_code == 201
        uid = r_unit.json()["id"]

        page = await c.get(f"/units/{uid}/phases")
        assert page.status_code == 200
        html = page.text
        assert "Phasen" in html
        # Default phase exists for modular units.
        assert "Phase 1" in html

