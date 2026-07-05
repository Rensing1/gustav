"""
Teaching API (DB-backed): Modular unit visual editor endpoints.

These endpoints power the teacher-side visual editor:
- load phases/modules/edges as a graph
- create modules in a specific phase
- create/delete dependency edges
- drag&drop reorder and cross-phase moves (blocked when edges would be invalid)
"""

from __future__ import annotations

import importlib

import pytest
import httpx
from httpx import ASGITransport

from backend.tests.runtime_auth_helpers import install_session_store
from backend.tests.utils.db import require_db_or_skip as _require_db_or_skip


pytestmark = [pytest.mark.anyio("asyncio"), pytest.mark.db_write]

main = importlib.import_module("backend.web.main")
teaching = importlib.import_module("backend.web.routes.teaching")


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=ASGITransport(app=main.app),
        base_url="http://test",
        headers={"Origin": "http://test"},
    )



async def _get_required_prereq_count(c: httpx.AsyncClient, *, unit_id: str, module_id: str) -> int:
    r_graph = await c.get(f"/api/teaching/units/{unit_id}/modules/graph")
    assert r_graph.status_code == 200, r_graph.text
    graph = r_graph.json()
    mod = next((m for m in graph["modules"] if m["id"] == module_id), None)
    assert mod is not None, f"module_not_in_graph:{module_id}"
    return int(mod.get("required_prereq_count") or 0)


def _teacher_session(monkeypatch: pytest.MonkeyPatch, sub: str):
    store = install_session_store(monkeypatch, main)
    return store.create(sub=sub, name="Teacher", roles=["teacher"])


@pytest.mark.anyio
async def test_teaching_modular_unit_graph_endpoints_support_visual_authoring(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _require_db_or_skip()
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for modular editor API tests")

    teacher = _teacher_session(monkeypatch, "t-api-mod-editor-1")

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)

        # Arrange: modular unit with 2 phases.
        r_unit = await c.post("/api/teaching/units", json={"title": "U", "unit_type": "modular"})
        assert r_unit.status_code == 201, r_unit.text
        uid = r_unit.json()["id"]

        r_phases = await c.get(f"/api/teaching/units/{uid}/phases")
        assert r_phases.status_code == 200, r_phases.text
        phases = r_phases.json()
        assert isinstance(phases, list) and len(phases) >= 1
        p1 = phases[0]["id"]

        r_p2 = await c.post(f"/api/teaching/units/{uid}/phases", json={"title": "Phase 2"})
        assert r_p2.status_code == 201, r_p2.text
        p2 = r_p2.json()["id"]

        # Create modules in specific phases (Option B internally creates a backing section).
        r_a = await c.post(f"/api/teaching/units/{uid}/modules", json={"title": "A", "phase_id": p1})
        assert r_a.status_code == 201, r_a.text
        mod_a = r_a.json()["id"]

        r_b = await c.post(f"/api/teaching/units/{uid}/modules", json={"title": "B", "phase_id": p1})
        assert r_b.status_code == 201, r_b.text
        mod_b = r_b.json()["id"]

        r_c = await c.post(f"/api/teaching/units/{uid}/modules", json={"title": "C", "phase_id": p2})
        assert r_c.status_code == 201, r_c.text
        mod_c = r_c.json()["id"]

        # Graph endpoint returns phases/modules/edges.
        r_graph = await c.get(f"/api/teaching/units/{uid}/modules/graph")
        assert r_graph.status_code == 200, r_graph.text
        graph = r_graph.json()
        assert graph["unit_id"] == uid
        assert len(graph["phases"]) == 2
        assert {m["title"] for m in graph["modules"]} >= {"A", "B", "C"}
        assert graph["edges"] == []

        # Add a valid same-phase edge A -> B.
        r_edge = await c.post(
            f"/api/teaching/units/{uid}/modules/edges",
            json={"from_module_id": mod_a, "to_module_id": mod_b},
        )
        assert r_edge.status_code == 201, r_edge.text
        assert r_edge.json() == {"from": mod_a, "to": mod_b}

        # Invalid same-phase direction B -> A must be rejected.
        r_bad = await c.post(
            f"/api/teaching/units/{uid}/modules/edges",
            json={"from_module_id": mod_b, "to_module_id": mod_a},
        )
        assert r_bad.status_code == 400, r_bad.text
        assert r_bad.json().get("detail") == "edge_constraint_violation"

        # Reorder that would break A -> B must be blocked (B before A).
        r_reorder_bad = await c.post(
            f"/api/teaching/units/{uid}/phases/{p1}/modules/reorder",
            json={"module_ids": [mod_b, mod_a]},
        )
        assert r_reorder_bad.status_code == 400, r_reorder_bad.text
        assert r_reorder_bad.json().get("detail") == "edge_constraint_violation"

        # Moving modules across phases is allowed when constraints remain valid.
        r_move = await c.post(
            f"/api/teaching/units/{uid}/phases/{p1}/modules/reorder",
            json={"module_ids": [mod_a, mod_b, mod_c]},
        )
        assert r_move.status_code == 200, r_move.text

        r_graph2 = await c.get(f"/api/teaching/units/{uid}/modules/graph")
        assert r_graph2.status_code == 200, r_graph2.text
        moved = [m for m in r_graph2.json()["modules"] if m["id"] == mod_c][0]
        assert moved["phase_id"] == p1
        assert moved["position_in_phase"] == 3

@pytest.mark.anyio
async def test_teaching_modular_unit_required_prereq_count_tracks_incoming_edges_until_manual_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Option 1: k defaults to n and keeps tracking while "auto" (k==n)."""
    _require_db_or_skip()
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for modular editor API tests")

    teacher = _teacher_session(monkeypatch, "t-api-mod-editor-k1")

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)

        r_unit = await c.post("/api/teaching/units", json={"title": "U", "unit_type": "modular"})
        assert r_unit.status_code == 201, r_unit.text
        uid = r_unit.json()["id"]

        r_phases = await c.get(f"/api/teaching/units/{uid}/phases")
        assert r_phases.status_code == 200, r_phases.text
        p1 = r_phases.json()[0]["id"]

        r_p2 = await c.post(f"/api/teaching/units/{uid}/phases", json={"title": "Phase 2"})
        assert r_p2.status_code == 201, r_p2.text
        p2 = r_p2.json()["id"]

        # Phase 1: prerequisites; Phase 2: target module.
        r_a = await c.post(f"/api/teaching/units/{uid}/modules", json={"title": "A", "phase_id": p1})
        assert r_a.status_code == 201, r_a.text
        mod_a = r_a.json()["id"]

        r_b = await c.post(f"/api/teaching/units/{uid}/modules", json={"title": "B", "phase_id": p1})
        assert r_b.status_code == 201, r_b.text
        mod_b = r_b.json()["id"]

        r_c = await c.post(f"/api/teaching/units/{uid}/modules", json={"title": "C", "phase_id": p1})
        assert r_c.status_code == 201, r_c.text
        mod_c = r_c.json()["id"]

        r_x = await c.post(f"/api/teaching/units/{uid}/modules", json={"title": "X", "phase_id": p2})
        assert r_x.status_code == 201, r_x.text
        mod_x = r_x.json()["id"]

        # Default remains 0 before any edges exist.
        assert await _get_required_prereq_count(c, unit_id=uid, module_id=mod_x) == 0

        # Auto mode: k==n should track incoming edges as they are added.
        r_edge1 = await c.post(
            f"/api/teaching/units/{uid}/modules/edges",
            json={"from_module_id": mod_a, "to_module_id": mod_x},
        )
        assert r_edge1.status_code == 201, r_edge1.text
        assert await _get_required_prereq_count(c, unit_id=uid, module_id=mod_x) == 1

        r_edge2 = await c.post(
            f"/api/teaching/units/{uid}/modules/edges",
            json={"from_module_id": mod_b, "to_module_id": mod_x},
        )
        assert r_edge2.status_code == 201, r_edge2.text
        assert await _get_required_prereq_count(c, unit_id=uid, module_id=mod_x) == 2

        # Manual override: once teacher sets k!=n, further edges must not change k.
        r_patch = await c.patch(
            f"/api/teaching/units/{uid}/modules/{mod_x}",
            json={"required_prereq_count": 1},
        )
        assert r_patch.status_code == 200, r_patch.text
        assert r_patch.json()["required_prereq_count"] == 1

        r_edge3 = await c.post(
            f"/api/teaching/units/{uid}/modules/edges",
            json={"from_module_id": mod_c, "to_module_id": mod_x},
        )
        assert r_edge3.status_code == 201, r_edge3.text
        assert await _get_required_prereq_count(c, unit_id=uid, module_id=mod_x) == 1


@pytest.mark.anyio
async def test_teaching_modular_unit_required_prereq_count_decreases_when_auto_and_edge_removed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When k==n, removing an incoming edge should keep k in sync."""
    _require_db_or_skip()
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for modular editor API tests")

    teacher = _teacher_session(monkeypatch, "t-api-mod-editor-k2")

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)

        r_unit = await c.post("/api/teaching/units", json={"title": "U", "unit_type": "modular"})
        assert r_unit.status_code == 201, r_unit.text
        uid = r_unit.json()["id"]

        r_phases = await c.get(f"/api/teaching/units/{uid}/phases")
        assert r_phases.status_code == 200, r_phases.text
        p1 = r_phases.json()[0]["id"]

        r_p2 = await c.post(f"/api/teaching/units/{uid}/phases", json={"title": "Phase 2"})
        assert r_p2.status_code == 201, r_p2.text
        p2 = r_p2.json()["id"]

        r_a = await c.post(f"/api/teaching/units/{uid}/modules", json={"title": "A", "phase_id": p1})
        assert r_a.status_code == 201, r_a.text
        mod_a = r_a.json()["id"]

        r_b = await c.post(f"/api/teaching/units/{uid}/modules", json={"title": "B", "phase_id": p1})
        assert r_b.status_code == 201, r_b.text
        mod_b = r_b.json()["id"]

        r_x = await c.post(f"/api/teaching/units/{uid}/modules", json={"title": "X", "phase_id": p2})
        assert r_x.status_code == 201, r_x.text
        mod_x = r_x.json()["id"]

        # Establish 2 incoming edges => k should end at 2.
        r_edge1 = await c.post(
            f"/api/teaching/units/{uid}/modules/edges",
            json={"from_module_id": mod_a, "to_module_id": mod_x},
        )
        assert r_edge1.status_code == 201, r_edge1.text
        r_edge2 = await c.post(
            f"/api/teaching/units/{uid}/modules/edges",
            json={"from_module_id": mod_b, "to_module_id": mod_x},
        )
        assert r_edge2.status_code == 201, r_edge2.text
        assert await _get_required_prereq_count(c, unit_id=uid, module_id=mod_x) == 2

        # Remove one edge => k should track down to 1.
        r_del = await c.request(
            "DELETE",
            f"/api/teaching/units/{uid}/modules/edges",
            json={"from_module_id": mod_a, "to_module_id": mod_x},
        )
        assert r_del.status_code == 204, r_del.text
        assert await _get_required_prereq_count(c, unit_id=uid, module_id=mod_x) == 1


@pytest.mark.anyio
async def test_teaching_modular_unit_duplicate_edge_returns_conflict_instead_of_500(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Creating the same edge twice must return a stable API error, not 500."""
    _require_db_or_skip()
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for modular editor API tests")

    teacher = _teacher_session(monkeypatch, "t-api-mod-editor-dup-edge")

    async with httpx.AsyncClient(
        transport=ASGITransport(app=main.app, raise_app_exceptions=False),
        base_url="http://test",
        headers={"Origin": "http://test"},
    ) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)

        r_unit = await c.post("/api/teaching/units", json={"title": "U", "unit_type": "modular"})
        assert r_unit.status_code == 201, r_unit.text
        uid = r_unit.json()["id"]

        r_phases = await c.get(f"/api/teaching/units/{uid}/phases")
        assert r_phases.status_code == 200, r_phases.text
        p1 = r_phases.json()[0]["id"]

        r_p2 = await c.post(f"/api/teaching/units/{uid}/phases", json={"title": "Phase 2"})
        assert r_p2.status_code == 201, r_p2.text
        p2 = r_p2.json()["id"]

        mod_a = (await c.post(f"/api/teaching/units/{uid}/modules", json={"title": "A", "phase_id": p1})).json()["id"]
        mod_b = (await c.post(f"/api/teaching/units/{uid}/modules", json={"title": "B", "phase_id": p2})).json()["id"]

        first = await c.post(
            f"/api/teaching/units/{uid}/modules/edges",
            json={"from_module_id": mod_a, "to_module_id": mod_b},
        )
        assert first.status_code == 201, first.text

        second = await c.post(
            f"/api/teaching/units/{uid}/modules/edges",
            json={"from_module_id": mod_a, "to_module_id": mod_b},
        )
        assert second.status_code == 409, second.text
        assert second.json().get("detail") == "duplicate_edge"


@pytest.mark.anyio
async def test_teaching_modular_unit_edge_create_accepts_uppercase_module_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Edge create must accept valid UUIDs regardless of letter casing."""
    _require_db_or_skip()
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for modular editor API tests")

    teacher = _teacher_session(monkeypatch, "t-api-mod-editor-upper-edge")

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        r_unit = await c.post("/api/teaching/units", json={"title": "U", "unit_type": "modular"})
        assert r_unit.status_code == 201, r_unit.text
        uid = r_unit.json()["id"]

        p1 = (await c.get(f"/api/teaching/units/{uid}/phases")).json()[0]["id"]
        p2 = (await c.post(f"/api/teaching/units/{uid}/phases", json={"title": "Phase 2"})).json()["id"]
        mod_a = (await c.post(f"/api/teaching/units/{uid}/modules", json={"title": "A", "phase_id": p1})).json()["id"]
        mod_b = (await c.post(f"/api/teaching/units/{uid}/modules", json={"title": "B", "phase_id": p2})).json()["id"]

        r_edge = await c.post(
            f"/api/teaching/units/{uid}/modules/edges",
            json={"from_module_id": mod_a.upper(), "to_module_id": mod_b.upper()},
        )
        assert r_edge.status_code == 201, r_edge.text
        assert r_edge.json() == {"from": mod_a, "to": mod_b}


@pytest.mark.anyio
async def test_teaching_modular_unit_edge_delete_rejects_linear_unit_invalid_unit_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Edge delete endpoint must reject linear units with a typed 400 detail code."""
    _require_db_or_skip()
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for modular editor API tests")

    teacher = _teacher_session(monkeypatch, "t-api-mod-editor-del-linear")

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        r_unit = await c.post("/api/teaching/units", json={"title": "Linear Unit"})
        assert r_unit.status_code == 201, r_unit.text
        uid = r_unit.json()["id"]

        r_del = await c.request(
            "DELETE",
            f"/api/teaching/units/{uid}/modules/edges",
            json={
                "from_module_id": "00000000-0000-0000-0000-000000000001",
                "to_module_id": "00000000-0000-0000-0000-000000000002",
            },
        )
        assert r_del.status_code == 400, r_del.text
        assert r_del.json().get("detail") == "invalid_unit_type"


@pytest.mark.anyio
async def test_teaching_modular_unit_edge_delete_by_path_params_happy_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Preferred edge delete endpoint should work without DELETE request body."""
    _require_db_or_skip()
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for modular editor API tests")

    teacher = _teacher_session(monkeypatch, "t-api-mod-editor-del-path")

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        r_unit = await c.post("/api/teaching/units", json={"title": "U", "unit_type": "modular"})
        assert r_unit.status_code == 201, r_unit.text
        uid = r_unit.json()["id"]

        p1 = (await c.get(f"/api/teaching/units/{uid}/phases")).json()[0]["id"]
        p2 = (await c.post(f"/api/teaching/units/{uid}/phases", json={"title": "Phase 2"})).json()["id"]
        mod_a = (await c.post(f"/api/teaching/units/{uid}/modules", json={"title": "A", "phase_id": p1})).json()["id"]
        mod_b = (await c.post(f"/api/teaching/units/{uid}/modules", json={"title": "B", "phase_id": p2})).json()["id"]

        r_edge = await c.post(
            f"/api/teaching/units/{uid}/modules/edges",
            json={"from_module_id": mod_a, "to_module_id": mod_b},
        )
        assert r_edge.status_code == 201, r_edge.text

        r_del = await c.delete(f"/api/teaching/units/{uid}/modules/{mod_a}/edges/{mod_b}")
        assert r_del.status_code == 204, r_del.text

        r_graph = await c.get(f"/api/teaching/units/{uid}/modules/graph")
        assert r_graph.status_code == 200
        assert r_graph.json()["edges"] == []
