"""
Teaching UI (SSR + HTMX): Modular unit visual editor CRUD controls.

Why:
    The visual editor must be usable without browser prompt()/confirm() dialogs.
    Instead, the UI should render inline forms (HTMX) for:
      - creating phases/modules
      - renaming phases/modules
      - deleting phases/modules (destructive; requires confirmation UI)

    For destructive actions we enforce CSRF at the UI boundary (dev = prod).
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


async def _create_modular_unit_with_two_modules(c: httpx.AsyncClient) -> tuple[str, str, str, str, str]:
    """Return (unit_id, phase1_id, phase2_id, module_a_id, module_b_id)."""
    r_unit = await c.post("/api/teaching/units", json={"title": "U", "unit_type": "modular"})
    assert r_unit.status_code == 201, r_unit.text
    uid = r_unit.json()["id"]

    r_phases = await c.get(f"/api/teaching/units/{uid}/phases")
    assert r_phases.status_code == 200, r_phases.text
    phase1_id = r_phases.json()[0]["id"]

    r_p2 = await c.post(f"/api/teaching/units/{uid}/phases", json={"title": "P2"})
    assert r_p2.status_code == 201, r_p2.text
    phase2_id = r_p2.json()["id"]

    r_a = await c.post(f"/api/teaching/units/{uid}/modules", json={"title": "A", "phase_id": phase1_id})
    assert r_a.status_code == 201, r_a.text
    mod_a = r_a.json()["id"]

    r_b = await c.post(f"/api/teaching/units/{uid}/modules", json={"title": "B", "phase_id": phase2_id})
    assert r_b.status_code == 201, r_b.text
    mod_b = r_b.json()["id"]

    return uid, phase1_id, phase2_id, mod_a, mod_b


def _extract_csrf(html: str) -> str:
    m = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert m, "csrf_token not found"
    return m.group(1)


@pytest.mark.anyio
async def test_modular_editor_module_rename_is_htmx_and_updates_title() -> None:
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for modular editor HTMX CRUD UI test")

    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-ui-mod-editor-htmx-rename", name="Teacher", roles=["teacher"])

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        uid, _p1, _p2, mod_a, _mod_b = await _create_modular_unit_with_two_modules(c)

        # Load the inline rename fragment (HTMX GET).
        frag = await c.get(
            f"/units/{uid}/modular-editor/module/{mod_a}/rename",
            headers={"HX-Request": "true"},
        )
        assert frag.status_code == 200, frag.text
        csrf = _extract_csrf(frag.text)

        # Submit rename via HTMX POST; the response should include an OOB graph update.
        res = await c.post(
            f"/units/{uid}/modular-editor/module/{mod_a}/rename",
            data={"csrf_token": csrf, "title": "A2"},
            headers={"HX-Request": "true"},
        )
        assert res.status_code == 200, res.text
        assert 'id="modular-editor-graph"' in res.text
        assert "hx-swap-oob" in res.text

        # Backend source of truth: module title is stored on the backing section (Option B).
        graph = await c.get(f"/api/teaching/units/{uid}/modules/graph")
        assert graph.status_code == 200
        titles = {m.get("title") for m in graph.json()["modules"]}
        assert "A2" in titles


@pytest.mark.anyio
async def test_modular_editor_phase_delete_requires_csrf_and_cascades() -> None:
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for modular editor HTMX CRUD UI test")

    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-ui-mod-editor-htmx-delete", name="Teacher", roles=["teacher"])

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        uid, _p1, p2, mod_a, mod_b = await _create_modular_unit_with_two_modules(c)

        # Create an edge A -> B (valid: phase1 -> phase2).
        r_edge = await c.post(
            f"/api/teaching/units/{uid}/modules/edges",
            json={"from_module_id": mod_a, "to_module_id": mod_b},
        )
        assert r_edge.status_code == 201, r_edge.text

        # Load delete confirm fragment.
        frag = await c.get(
            f"/units/{uid}/modular-editor/phase/{p2}/delete",
            headers={"HX-Request": "true"},
        )
        assert frag.status_code == 200, frag.text
        csrf = _extract_csrf(frag.text)

        # Missing CSRF must be rejected (security contract).
        no_csrf = await c.post(
            f"/units/{uid}/modular-editor/phase/{p2}/delete",
            data={},
            headers={"HX-Request": "true"},
        )
        assert no_csrf.status_code == 403

        # Delete phase via HTMX POST; expect OOB graph update.
        res = await c.post(
            f"/units/{uid}/modular-editor/phase/{p2}/delete",
            data={"csrf_token": csrf},
            headers={"HX-Request": "true"},
        )
        assert res.status_code == 200, res.text
        assert 'id="modular-editor-graph"' in res.text
        assert "hx-swap-oob" in res.text

        # Graph should now have one phase, one module, and no edges.
        graph = await c.get(f"/api/teaching/units/{uid}/modules/graph")
        assert graph.status_code == 200
        body = graph.json()
        assert len(body["phases"]) == 1
        assert all(m.get("id") != mod_b for m in body["modules"])
        assert body["edges"] == []


@pytest.mark.anyio
async def test_modular_editor_required_prereq_count_update_via_panel_settings() -> None:
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for modular editor HTMX CRUD UI test")

    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-ui-mod-editor-htmx-k", name="Teacher", roles=["teacher"])

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        uid, _p1, _p2, mod_a, _mod_b = await _create_modular_unit_with_two_modules(c)

        # Load panel fragment to get CSRF token for the inline settings form.
        panel = await c.get(
            f"/units/{uid}/modules/{mod_a}/panel",
            headers={"HX-Request": "true"},
        )
        assert panel.status_code == 200, panel.text
        csrf = _extract_csrf(panel.text)

        # Update required_prereq_count via UI endpoint (form POST).
        res = await c.post(
            f"/units/{uid}/modular-editor/module/{mod_a}/settings",
            data={"csrf_token": csrf, "required_prereq_count": "2"},
            headers={"HX-Request": "true"},
        )
        assert res.status_code == 200, res.text

        # Source of truth: the teaching graph API must reflect the new k.
        graph = await c.get(f"/api/teaching/units/{uid}/modules/graph")
        assert graph.status_code == 200, graph.text
        mod = next((m for m in graph.json()["modules"] if m.get("id") == mod_a), None)
        assert isinstance(mod, dict)
        assert mod.get("required_prereq_count") == 2


@pytest.mark.anyio
async def test_modular_editor_edge_delete_via_panel_removes_edge_and_refreshes_graph() -> None:
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for modular editor HTMX CRUD UI test")

    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-ui-mod-editor-edge-del", name="Teacher", roles=["teacher"])

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        uid, _p1, _p2, mod_a, mod_b = await _create_modular_unit_with_two_modules(c)

        # Create an edge A -> B (valid: phase1 -> phase2).
        r_edge = await c.post(
            f"/api/teaching/units/{uid}/modules/edges",
            json={"from_module_id": mod_a, "to_module_id": mod_b},
        )
        assert r_edge.status_code == 201, r_edge.text

        # Load the module panel; it should contain a delete-edge control.
        panel = await c.get(
            f"/units/{uid}/modules/{mod_a}/panel",
            headers={"HX-Request": "true"},
        )
        assert panel.status_code == 200, panel.text
        csrf = _extract_csrf(panel.text)
        assert f'hx-post="/units/{uid}/modular-editor/module/{mod_a}/edges/delete"' in panel.text

        # Delete the edge via panel action; expect OOB graph refresh.
        res = await c.post(
            f"/units/{uid}/modular-editor/module/{mod_a}/edges/delete",
            data={"csrf_token": csrf, "from_module_id": mod_a, "to_module_id": mod_b},
            headers={"HX-Request": "true"},
        )
        assert res.status_code == 200, res.text
        assert 'id="modular-editor-graph"' in res.text
        assert "hx-swap-oob" in res.text

        # Source of truth: the graph API must not return the edge anymore.
        graph = await c.get(f"/api/teaching/units/{uid}/modules/graph")
        assert graph.status_code == 200
        assert graph.json()["edges"] == []

@pytest.mark.anyio
async def test_modular_editor_material_and_task_create_pages_link_back_to_editor_when_return_to_provided() -> None:
    """Regression: when leaving the editor to create content, back should return to the editor."""
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for modular editor HTMX CRUD UI test")

    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-ui-mod-editor-return-to", name="Teacher", roles=["teacher"])

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        uid, _p1, _p2, mod_a, _mod_b = await _create_modular_unit_with_two_modules(c)

        panel = await c.get(
            f"/units/{uid}/modules/{mod_a}/panel",
            headers={"HX-Request": "true"},
        )
        assert panel.status_code == 200, panel.text

        uid_esc = re.escape(uid)
        mat_m = re.search(
            rf'href="(/units/{uid_esc}/sections/([0-9a-f-]+)/materials/new\?return_to=/units/{uid_esc})"',
            panel.text,
        )
        assert mat_m, "+Material link not found in panel"
        mat_href = mat_m.group(1)

        task_m = re.search(
            rf'href="(/units/{uid_esc}/sections/([0-9a-f-]+)/tasks/new\?return_to=/units/{uid_esc})"',
            panel.text,
        )
        assert task_m, "+Aufgabe link not found in panel"
        task_href = task_m.group(1)

        mat_new = await c.get(mat_href)
        assert mat_new.status_code == 200, mat_new.text
        assert f'<a href="/units/{uid}">Zurück</a>' in mat_new.text

        task_new = await c.get(task_href)
        assert task_new.status_code == 200, task_new.text
        assert f'<a href="/units/{uid}">Zurück</a>' in task_new.text
