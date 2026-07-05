"""
Teaching API — Unit Phases (modular units)

Contract-first intent:
- Modular units have phases that can be listed, created, renamed and reordered.
- Linear units must reject phase endpoints with 400 detail=invalid_unit_type.
"""
from __future__ import annotations

import importlib

import pytest
import httpx
from httpx import ASGITransport

pytestmark = [pytest.mark.anyio("asyncio"), pytest.mark.db_write]

main = importlib.import_module("backend.web.main")
teaching = importlib.import_module("backend.web.routes.teaching")
from backend.tests.runtime_auth_helpers import install_session_store

from backend.tests.utils.db import require_db_or_skip as _require_db_or_skip


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test", headers={"Origin": "http://test"})


async def _create_unit(client: httpx.AsyncClient, *, title: str, unit_type: str | None = None) -> dict:
    payload: dict[str, object] = {"title": title}
    if unit_type is not None:
        payload["unit_type"] = unit_type
    resp = await client.post("/api/teaching/units", json=payload)
    assert resp.status_code == 201
    return resp.json()


def _assert_phase_public_shape(phase: dict, *, unit_id: str) -> None:
    """Assert TeachingUnitPhase contract shape (additionalProperties=false)."""
    assert set(phase.keys()) == {"id", "unit_id", "title", "position"}
    assert phase["unit_id"] == unit_id


@pytest.mark.anyio
async def test_unit_phases_list_create_rename_reorder_happy_path(monkeypatch: pytest.MonkeyPatch):
    store = install_session_store(monkeypatch, main)
    _require_db_or_skip()

    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    teacher = store.create(sub="teacher-phases-1", name="Phases", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", teacher.session_id)
        unit = await _create_unit(client, title="Modular Unit", unit_type="modular")

        r_list = await client.get(f"/api/teaching/units/{unit['id']}/phases")
        assert r_list.status_code == 200
        phases = r_list.json()
        assert isinstance(phases, list) and len(phases) == 1
        phase1 = phases[0]
        _assert_phase_public_shape(phase1, unit_id=unit["id"])
        assert phase1["position"] == 1

        r_create = await client.post(f"/api/teaching/units/{unit['id']}/phases", json={"title": "Phase 2"})
        assert r_create.status_code == 201
        phase2 = r_create.json()
        _assert_phase_public_shape(phase2, unit_id=unit["id"])
        assert phase2["position"] == 2

        r_rename = await client.patch(
            f"/api/teaching/units/{unit['id']}/phases/{phase2['id']}",
            json={"title": "Praxis"},
        )
        assert r_rename.status_code == 200
        renamed = r_rename.json()
        _assert_phase_public_shape(renamed, unit_id=unit["id"])
        assert renamed["title"] == "Praxis"

        r_reorder = await client.post(
            f"/api/teaching/units/{unit['id']}/phases/reorder",
            json={"phase_ids": [phase2["id"], phase1["id"]]},
        )
        assert r_reorder.status_code == 200
        reordered = r_reorder.json()
        assert isinstance(reordered, list) and len(reordered) == 2
        for entry in reordered:
            _assert_phase_public_shape(entry, unit_id=unit["id"])
        assert [p["id"] for p in reordered] == [phase2["id"], phase1["id"]]
        assert [p["position"] for p in reordered] == [1, 2]

        # GET reflects new order.
        r_list2 = await client.get(f"/api/teaching/units/{unit['id']}/phases")
        assert r_list2.status_code == 200
        listed_again = r_list2.json()
        assert isinstance(listed_again, list) and len(listed_again) == 2
        for entry in listed_again:
            _assert_phase_public_shape(entry, unit_id=unit["id"])
        assert [p["id"] for p in listed_again] == [phase2["id"], phase1["id"]]


@pytest.mark.anyio
async def test_unit_phases_requires_authentication_returns_401(monkeypatch: pytest.MonkeyPatch):
    """Phase endpoints must return 401 without an authenticated session."""
    install_session_store(monkeypatch, main)
    _require_db_or_skip()

    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    async with (await _client()) as client:
        unit_id = "00000000-0000-0000-0000-000000000000"
        r_get = await client.get(f"/api/teaching/units/{unit_id}/phases")
        assert r_get.status_code == 401

        r_post = await client.post(f"/api/teaching/units/{unit_id}/phases", json={"title": "X"})
        assert r_post.status_code == 401


@pytest.mark.anyio
async def test_unit_phases_non_teacher_returns_403(monkeypatch: pytest.MonkeyPatch):
    """Phase endpoints must return 403 for authenticated non-teacher callers."""
    store = install_session_store(monkeypatch, main)
    _require_db_or_skip()

    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    student = store.create(sub="student-phases-403", name="Student", roles=["student"])
    async with (await _client()) as client:
        client.cookies.set("gustav_session", student.session_id)
        unit_id = "00000000-0000-0000-0000-000000000000"
        r_get = await client.get(f"/api/teaching/units/{unit_id}/phases")
        assert r_get.status_code == 403


@pytest.mark.anyio
async def test_unit_phases_rejects_linear_unit_invalid_unit_type(monkeypatch: pytest.MonkeyPatch):
    store = install_session_store(monkeypatch, main)
    _require_db_or_skip()

    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    teacher = store.create(sub="teacher-phases-2", name="Linear", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", teacher.session_id)
        unit = await _create_unit(client, title="Linear Unit")

        r_list = await client.get(f"/api/teaching/units/{unit['id']}/phases")
        assert r_list.status_code == 400
        assert r_list.json().get("detail") == "invalid_unit_type"

        r_create = await client.post(f"/api/teaching/units/{unit['id']}/phases", json={"title": "X"})
        assert r_create.status_code == 400
        assert r_create.json().get("detail") == "invalid_unit_type"


@pytest.mark.anyio
async def test_unit_phases_reorder_rejects_edge_constraint_violation(monkeypatch: pytest.MonkeyPatch):
    """Reordering phases must fail-closed when it would invalidate existing edges."""
    store = install_session_store(monkeypatch, main)
    _require_db_or_skip()

    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    teacher = store.create(sub="teacher-phases-3", name="Edges", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", teacher.session_id)
        unit = await _create_unit(client, title="Modular Unit", unit_type="modular")

        r_list = await client.get(f"/api/teaching/units/{unit['id']}/phases")
        assert r_list.status_code == 200
        phase1 = r_list.json()[0]

        r_create = await client.post(f"/api/teaching/units/{unit['id']}/phases", json={"title": "Phase 2"})
        assert r_create.status_code == 201
        phase2 = r_create.json()

        r_mod_a = await client.post(
            f"/api/teaching/units/{unit['id']}/modules",
            json={"title": "A", "phase_id": phase1["id"]},
        )
        assert r_mod_a.status_code == 201
        mod_a = r_mod_a.json()

        r_mod_b = await client.post(
            f"/api/teaching/units/{unit['id']}/modules",
            json={"title": "B", "phase_id": phase2["id"]},
        )
        assert r_mod_b.status_code == 201
        mod_b = r_mod_b.json()

        r_edge = await client.post(
            f"/api/teaching/units/{unit['id']}/modules/edges",
            json={"from_module_id": mod_a["id"], "to_module_id": mod_b["id"]},
        )
        assert r_edge.status_code == 201, r_edge.text

        # This reorder would move phase2 before phase1, making the existing A->B edge invalid.
        r_reorder = await client.post(
            f"/api/teaching/units/{unit['id']}/phases/reorder",
            json={"phase_ids": [phase2["id"], phase1["id"]]},
        )
        assert r_reorder.status_code == 400, r_reorder.text
        assert r_reorder.json().get("detail") == "edge_constraint_violation"


@pytest.mark.anyio
async def test_unit_phases_reorder_rejects_non_string_ids_with_400(monkeypatch: pytest.MonkeyPatch):
    """Reorder must not crash on unhashable items; return invalid_phase_ids."""
    store = install_session_store(monkeypatch, main)
    _require_db_or_skip()

    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    teacher = store.create(sub="teacher-phases-invalid-ids", name="InvalidIds", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", teacher.session_id)
        unit = await _create_unit(client, title="Modular Unit", unit_type="modular")

        r_list = await client.get(f"/api/teaching/units/{unit['id']}/phases")
        assert r_list.status_code == 200
        phase1 = r_list.json()[0]

        r_create = await client.post(f"/api/teaching/units/{unit['id']}/phases", json={"title": "Phase 2"})
        assert r_create.status_code == 201
        phase2 = r_create.json()

        r_bad = await client.post(
            f"/api/teaching/units/{unit['id']}/phases/reorder",
            json={"phase_ids": [phase2["id"], {"not": "a-uuid"}, phase1["id"]]},
        )
        assert r_bad.status_code == 400, r_bad.text
        assert r_bad.json().get("detail") == "invalid_phase_ids"


@pytest.mark.anyio
async def test_unit_phase_modules_reorder_rejects_non_string_ids_with_400(monkeypatch: pytest.MonkeyPatch):
    """Module reorder must not crash on unhashable items; return invalid_module_ids."""
    store = install_session_store(monkeypatch, main)
    _require_db_or_skip()

    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    teacher = store.create(sub="teacher-modules-invalid-ids", name="InvalidIds", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", teacher.session_id)
        unit = await _create_unit(client, title="Modular Unit", unit_type="modular")

        r_phases = await client.get(f"/api/teaching/units/{unit['id']}/phases")
        assert r_phases.status_code == 200
        phase1 = r_phases.json()[0]

        r_mod = await client.post(
            f"/api/teaching/units/{unit['id']}/modules",
            json={"title": "A", "phase_id": phase1["id"]},
        )
        assert r_mod.status_code == 201
        mod1 = r_mod.json()

        r_bad = await client.post(
            f"/api/teaching/units/{unit['id']}/phases/{phase1['id']}/modules/reorder",
            json={"module_ids": [mod1["id"], {"not": "a-uuid"}]},
        )
        assert r_bad.status_code == 400, r_bad.text
        assert r_bad.json().get("detail") == "invalid_module_ids"
