"""
SSR UI: Modular unit editor (teacher) is a single entrypoint.

Intent:
    Teachers should not have to switch between separate "phases" and "modules"
    pages. A modular unit should offer one editor view (graph/board), and
    clicking a module should open its content editor (materials/tasks).

Scope:
    This is a DB-backed integration test because modular phases/modules are
    stored in Postgres. The in-memory Teaching repo does not implement them.
"""

from __future__ import annotations

import re
from pathlib import Path
import sys

import pytest
import httpx
from httpx import ASGITransport

from utils.db import require_db_or_skip as _require_db_or_skip

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
async def test_modular_unit_editor_renders_phases_modules_and_module_click_opens_content():
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for modular editor UI test")

    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-ui-mod-editor-1", name="Teacher", roles=["teacher"])

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        # Create modular unit + one module (via section create).
        r_unit = await c.post("/api/teaching/units", json={"title": "Modular Editor Unit", "unit_type": "modular"})
        assert r_unit.status_code == 201, r_unit.text
        uid = r_unit.json()["id"]
        r_sec = await c.post(f"/api/teaching/units/{uid}/sections", json={"title": "Modul A"})
        assert r_sec.status_code == 201, r_sec.text

        # Editor is the unit details page for modular units.
        page = await c.get(f"/units/{uid}")
        assert page.status_code == 200
        html = page.text
        assert "Editor" in html
        assert "Phase 1" in html
        assert "Modul A" in html

        # Module cards must link to a module content page.
        pattern = rf"/units/{re.escape(uid)}/modules/([0-9a-fA-F-]{{36}})"
        m = re.search(pattern, html)
        assert m, "Expected a module link /units/{unit_id}/modules/{module_id} in editor HTML"
        module_id = m.group(1)

        module_page = await c.get(f"/units/{uid}/modules/{module_id}")
        assert module_page.status_code == 200
        assert "Modul" in module_page.text
        assert "Materialien" in module_page.text
        assert "Aufgaben" in module_page.text
