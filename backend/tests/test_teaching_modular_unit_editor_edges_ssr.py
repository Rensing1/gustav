"""
SSR UI: Modular unit editor must include persisted edges in the initial HTML.

Why:
    The teacher visual editor renders edges as an SVG overlay in the browser.
    On a full page reload, the JS initializer reads the edge list from the SSR
    markup. If the SSR page forgets to embed edges, teachers will see an empty
    graph until they re-create edges manually.

Scope:
    DB-backed integration test (modular phases/modules/edges live in Postgres).
"""

from __future__ import annotations

import json
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
async def test_modular_unit_editor_ssr_embeds_edges_on_reload():
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for modular editor edge SSR test")

    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-ui-mod-editor-edges-1", name="Teacher", roles=["teacher"])

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)

        r_unit = await c.post("/api/teaching/units", json={"title": "Edge SSR Unit", "unit_type": "modular"})
        assert r_unit.status_code == 201, r_unit.text
        uid = r_unit.json()["id"]

        # Create two modules (via sections; Option B creates unit_modules rows).
        r_a = await c.post(f"/api/teaching/units/{uid}/sections", json={"title": "A"})
        r_b = await c.post(f"/api/teaching/units/{uid}/sections", json={"title": "B"})
        assert r_a.status_code == 201, r_a.text
        assert r_b.status_code == 201, r_b.text

        # Resolve module ids from the graph endpoint.
        r_graph = await c.get(f"/api/teaching/units/{uid}/modules/graph")
        assert r_graph.status_code == 200, r_graph.text
        g = r_graph.json()
        modules = g.get("modules") if isinstance(g, dict) else None
        assert isinstance(modules, list)
        assert len(modules) >= 2
        m1 = modules[0]["id"]
        m2 = modules[1]["id"]

        # Persist an edge A -> B.
        r_edge = await c.post(
            f"/api/teaching/units/{uid}/modules/edges",
            json={"from_module_id": m1, "to_module_id": m2},
        )
        assert r_edge.status_code == 201, r_edge.text

        # Reload the editor SSR page and ensure the edge is embedded in the HTML.
        page = await c.get(f"/units/{uid}")
        assert page.status_code == 200
        html = page.text

        m = re.search(
            r'<template[^>]*id="modular-editor-edges-data"[^>]*>([^<]*)</template>',
            html,
        )
        assert m, "Expected SSR page to embed edges JSON in <template id=\"modular-editor-edges-data\">"
        raw = (m.group(1) or "").strip()
        assert raw, "Expected non-empty edges JSON in SSR page"

        edges = json.loads(raw)
        assert {"from": m1, "to": m2} in edges
