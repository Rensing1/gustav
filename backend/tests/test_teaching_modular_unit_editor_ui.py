"""
SSR UI: Modular unit editor (teacher) is a visual graph + right-side panel.

Intent:
    Teachers plan a modular unit as phases (columns) and modules (nodes).
    The editor should render a visual representation and load module content
    into a right-side panel via HTMX (no page navigation).

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
        # Create modular unit + one module (via section create; Option B will
        # create a unit_module record automatically).
        r_unit = await c.post("/api/teaching/units", json={"title": "Modular Editor Unit", "unit_type": "modular"})
        assert r_unit.status_code == 201, r_unit.text
        uid = r_unit.json()["id"]
        r_sec = await c.post(f"/api/teaching/units/{uid}/sections", json={"title": "Modul A"})
        assert r_sec.status_code == 201, r_sec.text

        # Editor is the unit details page for modular units.
        page = await c.get(f"/units/{uid}")
        assert page.status_code == 200
        html = page.text
        assert 'data-testid="modular-unit-editor"' in html
        # The visual editor uses Teaching APIs via JS (edges + drag&drop). Those
        # endpoints are protected by synchronizer CSRF, so the SSR page must
        # expose a token as a data attribute.
        assert 'data-csrf-token="' in html
        assert 'id="modular-editor-panel"' in html
        assert "Phase 1" in html
        assert "Modul A" in html
        # Basic CRUD controls must be present in the visual editor.
        assert 'data-action="modular-editor-rename-phase"' in html
        assert 'data-action="modular-editor-delete-phase"' in html
        assert 'data-action="modular-editor-rename-module"' in html
        assert 'data-action="modular-editor-delete-module"' in html

        # Module nodes must load panel content via HTMX.
        pattern = rf"/units/{re.escape(uid)}/modules/([0-9a-fA-F-]{{36}})/panel"
        m = re.search(pattern, html)
        assert m, "Expected a module panel link /units/{unit_id}/modules/{module_id}/panel in editor HTML"
        module_id = m.group(1)

        panel = await c.get(f"/units/{uid}/modules/{module_id}/panel")
        assert panel.status_code == 200
        assert "Materialien" in panel.text
        assert "Aufgaben" in panel.text
