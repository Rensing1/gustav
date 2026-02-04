"""
Teaching API — Unit Phases (modular units)

Contract-first intent:
- Modular units have phases that can be listed, created, renamed and reordered.
- Linear units must reject phase endpoints with 400 detail=invalid_unit_type.
"""
from __future__ import annotations

import os
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
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test", headers={"Origin": "http://test"})


async def _create_unit(client: httpx.AsyncClient, *, title: str, unit_type: str | None = None) -> dict:
    payload: dict[str, object] = {"title": title}
    if unit_type is not None:
        payload["unit_type"] = unit_type
    resp = await client.post("/api/teaching/units", json=payload)
    assert resp.status_code == 201
    return resp.json()


@pytest.mark.anyio
async def test_unit_phases_list_create_rename_reorder_happy_path():
    main.SESSION_STORE = SessionStore()
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    teacher = main.SESSION_STORE.create(sub="teacher-phases-1", name="Phases", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", teacher.session_id)
        unit = await _create_unit(client, title="Modular Unit", unit_type="modular")

        r_list = await client.get(f"/api/teaching/units/{unit['id']}/phases")
        assert r_list.status_code == 200
        phases = r_list.json()
        assert isinstance(phases, list) and len(phases) == 1
        phase1 = phases[0]
        assert phase1["unit_id"] == unit["id"]
        assert phase1["position"] == 1

        r_create = await client.post(f"/api/teaching/units/{unit['id']}/phases", json={"title": "Phase 2"})
        assert r_create.status_code == 201
        phase2 = r_create.json()
        assert phase2["unit_id"] == unit["id"]
        assert phase2["position"] == 2

        r_rename = await client.patch(
            f"/api/teaching/units/{unit['id']}/phases/{phase2['id']}",
            json={"title": "Praxis"},
        )
        assert r_rename.status_code == 200
        assert r_rename.json()["title"] == "Praxis"

        r_reorder = await client.post(
            f"/api/teaching/units/{unit['id']}/phases/reorder",
            json={"phase_ids": [phase2["id"], phase1["id"]]},
        )
        assert r_reorder.status_code == 200
        reordered = r_reorder.json()
        assert [p["id"] for p in reordered] == [phase2["id"], phase1["id"]]
        assert [p["position"] for p in reordered] == [1, 2]

        # GET reflects new order.
        r_list2 = await client.get(f"/api/teaching/units/{unit['id']}/phases")
        assert r_list2.status_code == 200
        assert [p["id"] for p in r_list2.json()] == [phase2["id"], phase1["id"]]


@pytest.mark.anyio
async def test_unit_phases_rejects_linear_unit_invalid_unit_type():
    main.SESSION_STORE = SessionStore()
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    teacher = main.SESSION_STORE.create(sub="teacher-phases-2", name="Linear", roles=["teacher"])

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
async def test_unit_phases_reorder_rejects_edge_constraint_violation():
    """Reordering phases must fail-closed when it would invalidate existing edges."""
    main.SESSION_STORE = SessionStore()
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    teacher = main.SESSION_STORE.create(sub="teacher-phases-3", name="Edges", roles=["teacher"])

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
