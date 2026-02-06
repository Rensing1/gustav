"""
Teaching API (DB-backed): CRUD for the modular unit visual editor.

Why:
    The editor must support day-to-day authoring operations:
    - rename module nodes (title)
    - delete module nodes (incl. backing content)
    - delete phases (incl. all modules/edges/content in the phase)
"""

from __future__ import annotations

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
async def test_teaching_modular_unit_module_update_and_delete_remove_backing_content() -> None:
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for modular editor CRUD API tests")

    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-api-mod-editor-crud-1", name="Teacher", roles=["teacher"])

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)

        r_unit = await c.post("/api/teaching/units", json={"title": "U", "unit_type": "modular"})
        assert r_unit.status_code == 201, r_unit.text
        uid = r_unit.json()["id"]

        phases = (await c.get(f"/api/teaching/units/{uid}/phases")).json()
        p1 = phases[0]["id"]

        r_mod = await c.post(f"/api/teaching/units/{uid}/modules", json={"title": "A", "phase_id": p1})
        assert r_mod.status_code == 201, r_mod.text
        mid = r_mod.json()["id"]

        # Rename module title.
        r_rename = await c.patch(f"/api/teaching/units/{uid}/modules/{mid}", json={"title": "A2"})
        assert r_rename.status_code == 200, r_rename.text
        assert r_rename.json()["title"] == "A2"

        # Update k-of-n prerequisite semantics (k = required_prereq_count).
        r_k = await c.patch(f"/api/teaching/units/{uid}/modules/{mid}", json={"required_prereq_count": 1})
        assert r_k.status_code == 200, r_k.text
        assert r_k.json()["required_prereq_count"] == 1

        # Backing content is a section; the section list should reflect the new title.
        r_sections = await c.get(f"/api/teaching/units/{uid}/sections")
        assert r_sections.status_code == 200
        titles = {s.get("title") for s in r_sections.json()}
        assert "A2" in titles

        # Delete module must delete its backing content (section) too.
        r_del = await c.delete(f"/api/teaching/units/{uid}/modules/{mid}")
        assert r_del.status_code == 204, r_del.text

        r_sections2 = await c.get(f"/api/teaching/units/{uid}/sections")
        assert r_sections2.status_code == 200
        titles2 = {s.get("title") for s in r_sections2.json()}
        assert "A2" not in titles2

        r_graph = await c.get(f"/api/teaching/units/{uid}/modules/graph")
        assert r_graph.status_code == 200
        assert all(m.get("id") != mid for m in r_graph.json()["modules"])


@pytest.mark.anyio
async def test_teaching_modular_unit_phase_delete_cascades_to_modules_edges_and_content() -> None:
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for modular editor CRUD API tests")

    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-api-mod-editor-crud-2", name="Teacher", roles=["teacher"])

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)

        r_unit = await c.post("/api/teaching/units", json={"title": "U", "unit_type": "modular"})
        assert r_unit.status_code == 201, r_unit.text
        uid = r_unit.json()["id"]

        r_phases = await c.get(f"/api/teaching/units/{uid}/phases")
        assert r_phases.status_code == 200
        p1 = r_phases.json()[0]["id"]

        r_p2 = await c.post(f"/api/teaching/units/{uid}/phases", json={"title": "Phase 2"})
        assert r_p2.status_code == 201
        p2 = r_p2.json()["id"]

        r_a = await c.post(f"/api/teaching/units/{uid}/modules", json={"title": "A", "phase_id": p1})
        assert r_a.status_code == 201
        mod_a = r_a.json()["id"]

        r_b = await c.post(f"/api/teaching/units/{uid}/modules", json={"title": "B", "phase_id": p2})
        assert r_b.status_code == 201
        mod_b = r_b.json()["id"]

        r_edge = await c.post(
            f"/api/teaching/units/{uid}/modules/edges",
            json={"from_module_id": mod_a, "to_module_id": mod_b},
        )
        assert r_edge.status_code == 201

        r_del = await c.delete(f"/api/teaching/units/{uid}/phases/{p2}")
        assert r_del.status_code == 204, r_del.text

        r_graph = await c.get(f"/api/teaching/units/{uid}/modules/graph")
        assert r_graph.status_code == 200
        graph = r_graph.json()
        assert len(graph["phases"]) == 1
        assert all(m.get("id") != mod_b for m in graph["modules"])
        assert graph["edges"] == []

        r_sections = await c.get(f"/api/teaching/units/{uid}/sections")
        assert r_sections.status_code == 200
        titles = {s.get("title") for s in r_sections.json()}
        assert "B" not in titles


@pytest.mark.anyio
async def test_teaching_modular_create_section_keeps_documented_section_to_module_bridge() -> None:
    """`createSection` in modular units must still create the backing module entry."""
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for modular editor CRUD API tests")

    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-api-mod-editor-crud-3", name="Teacher", roles=["teacher"])

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        r_unit = await c.post("/api/teaching/units", json={"title": "U", "unit_type": "modular"})
        assert r_unit.status_code == 201, r_unit.text
        uid = r_unit.json()["id"]

        r_before = await c.get(f"/api/teaching/units/{uid}/modules/graph")
        assert r_before.status_code == 200, r_before.text
        modules_before = r_before.json().get("modules") or []

        r_create = await c.post(f"/api/teaching/units/{uid}/sections", json={"title": "Bridge Section"})
        assert r_create.status_code == 201, r_create.text

        r_after = await c.get(f"/api/teaching/units/{uid}/modules/graph")
        assert r_after.status_code == 200, r_after.text
        modules_after = r_after.json().get("modules") or []
        assert len(modules_after) == len(modules_before) + 1
        assert any(m.get("title") == "Bridge Section" for m in modules_after)


@pytest.mark.anyio
async def test_teaching_modular_module_delete_clamps_required_prereq_count_after_edge_cascade() -> None:
    """Deleting a prerequisite module must clamp target k-of-n to remaining incoming edges."""
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for modular editor CRUD API tests")

    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-api-mod-editor-crud-4", name="Teacher", roles=["teacher"])

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        r_unit = await c.post("/api/teaching/units", json={"title": "U", "unit_type": "modular"})
        assert r_unit.status_code == 201, r_unit.text
        uid = r_unit.json()["id"]

        r_phases = await c.get(f"/api/teaching/units/{uid}/phases")
        assert r_phases.status_code == 200
        p1 = r_phases.json()[0]["id"]
        r_p2 = await c.post(f"/api/teaching/units/{uid}/phases", json={"title": "P2"})
        assert r_p2.status_code == 201
        p2 = r_p2.json()["id"]

        mod_a = (await c.post(f"/api/teaching/units/{uid}/modules", json={"title": "A", "phase_id": p1})).json()["id"]
        mod_b = (await c.post(f"/api/teaching/units/{uid}/modules", json={"title": "B", "phase_id": p1})).json()["id"]
        mod_x = (await c.post(f"/api/teaching/units/{uid}/modules", json={"title": "X", "phase_id": p2})).json()["id"]

        r_e1 = await c.post(
            f"/api/teaching/units/{uid}/modules/edges",
            json={"from_module_id": mod_a, "to_module_id": mod_x},
        )
        assert r_e1.status_code == 201, r_e1.text
        r_e2 = await c.post(
            f"/api/teaching/units/{uid}/modules/edges",
            json={"from_module_id": mod_b, "to_module_id": mod_x},
        )
        assert r_e2.status_code == 201, r_e2.text

        r_patch = await c.patch(f"/api/teaching/units/{uid}/modules/{mod_x}", json={"required_prereq_count": 2})
        assert r_patch.status_code == 200, r_patch.text

        r_del = await c.delete(f"/api/teaching/units/{uid}/modules/{mod_a}")
        assert r_del.status_code == 204, r_del.text

        r_graph = await c.get(f"/api/teaching/units/{uid}/modules/graph")
        assert r_graph.status_code == 200, r_graph.text
        graph = r_graph.json()
        mod_x_state = next((m for m in graph["modules"] if m["id"] == mod_x), None)
        assert mod_x_state is not None
        assert mod_x_state.get("required_prereq_count") == 1


@pytest.mark.anyio
async def test_teaching_modular_phase_delete_clamps_required_prereq_count_after_edge_cascade() -> None:
    """Deleting a phase with prerequisite modules must clamp target k-of-n to zero."""
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for modular editor CRUD API tests")

    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-api-mod-editor-crud-5", name="Teacher", roles=["teacher"])

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        r_unit = await c.post("/api/teaching/units", json={"title": "U", "unit_type": "modular"})
        assert r_unit.status_code == 201, r_unit.text
        uid = r_unit.json()["id"]

        r_phases = await c.get(f"/api/teaching/units/{uid}/phases")
        assert r_phases.status_code == 200
        p1 = r_phases.json()[0]["id"]
        r_p2 = await c.post(f"/api/teaching/units/{uid}/phases", json={"title": "P2"})
        assert r_p2.status_code == 201
        p2 = r_p2.json()["id"]

        mod_a = (await c.post(f"/api/teaching/units/{uid}/modules", json={"title": "A", "phase_id": p1})).json()["id"]
        mod_b = (await c.post(f"/api/teaching/units/{uid}/modules", json={"title": "B", "phase_id": p1})).json()["id"]
        mod_x = (await c.post(f"/api/teaching/units/{uid}/modules", json={"title": "X", "phase_id": p2})).json()["id"]

        assert (
            await c.post(
                f"/api/teaching/units/{uid}/modules/edges",
                json={"from_module_id": mod_a, "to_module_id": mod_x},
            )
        ).status_code == 201
        assert (
            await c.post(
                f"/api/teaching/units/{uid}/modules/edges",
                json={"from_module_id": mod_b, "to_module_id": mod_x},
            )
        ).status_code == 201

        r_patch = await c.patch(f"/api/teaching/units/{uid}/modules/{mod_x}", json={"required_prereq_count": 2})
        assert r_patch.status_code == 200, r_patch.text

        r_del_phase = await c.delete(f"/api/teaching/units/{uid}/phases/{p1}")
        assert r_del_phase.status_code == 204, r_del_phase.text

        r_graph = await c.get(f"/api/teaching/units/{uid}/modules/graph")
        assert r_graph.status_code == 200, r_graph.text
        graph = r_graph.json()
        mod_x_state = next((m for m in graph["modules"] if m["id"] == mod_x), None)
        assert mod_x_state is not None
        assert mod_x_state.get("required_prereq_count") == 0
