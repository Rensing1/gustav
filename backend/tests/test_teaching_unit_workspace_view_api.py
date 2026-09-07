"""API tests for the teacher unit graph workspace views."""

from __future__ import annotations

import os
from uuid import uuid4

import httpx
import psycopg
import pytest
from httpx import ASGITransport

from backend.tests.utils.db import is_safe_db_test_dsn, require_db_or_skip
from backend.web.main import create_app

pytestmark = [pytest.mark.anyio("asyncio"), pytest.mark.db_write]


@pytest.fixture
def app():
    require_db_or_skip()
    claims = {}
    app = create_app(access_token_verifier=lambda token, cfg: claims)
    app.state.claims = claims
    app.state.owner = f"workspace-{uuid4()}"
    app.state.unit_ids = []
    yield app
    dsn = os.environ["RLS_TEST_SERVICE_DSN"]
    assert is_safe_db_test_dsn(dsn)
    with psycopg.connect(dsn) as conn:
        conn.execute("delete from public.units where id = any(%s::uuid[])", (app.state.unit_ids,))


def _mock_bearer_auth(app, *, sub, roles, name):
    app.state.claims.clear()
    app.state.claims.update({"sub": sub, "name": name, "realm_access": {"roles": roles}})
    return {"Authorization": "Bearer test.jwt"}


async def _create_unit(
    client: httpx.AsyncClient,
    app,
    *,
    title: str,
    unit_type: str = "linear",
    summary: str | None = None,
) -> str:
    response = await client.post(
        "/api/teaching/units",
        json={"title": title, "summary": summary, "unit_type": unit_type},
        headers={"Origin": "http://test"},
    )
    assert response.status_code == 201
    unit_id = response.json()["id"]
    app.state.unit_ids.append(unit_id)
    return unit_id


@pytest.mark.anyio
async def test_teacher_unit_workspace_returns_linear_graph_and_section_selection(
    app,
) -> None:
    store = app.state.runtime.session_store
    session = store.create(sub=app.state.owner, roles=["teacher"], name="Ada", ttl_seconds=60)
    headers = _mock_bearer_auth(app, sub=app.state.owner, roles=["teacher"], name="Ada")

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        client.cookies.set("gustav_session", session.session_id)
        unit_id = await _create_unit(
            client, app, title="Weimarer Republik", summary="Aufbau und Krisen"
        )
        section = await client.post(
            f"/api/teaching/units/{unit_id}/sections",
            json={"title": "Krisenjahre"},
            headers={"Origin": "http://test"},
        )
        assert section.status_code == 201
        section_id = section.json()["id"]

        response = await client.get(
            f"/api/teaching/views/units/{unit_id}/workspace",
            params={"section_id": section_id},
            headers=headers,
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["graph"]["kind"] == "linear"
    assert payload["graph"]["nodes"] == [
        {
            "id": section_id,
            "title": "Krisenjahre",
            "position": 1,
            "materials_count": 0,
            "tasks_count": 0,
            "editor_href": f"/teaching/units/{unit_id}/nodes/{section_id}",
        }
    ]
    assert payload["selection"] == {
        "kind": "section",
        "section": {
            "id": section_id,
            "title": "Krisenjahre",
            "position": 1,
            "editor_href": f"/teaching/units/{unit_id}/nodes/{section_id}",
        },
    }


@pytest.mark.anyio
async def test_teacher_unit_workspace_returns_modular_graph_and_edge_selection(
    app,
) -> None:
    store = app.state.runtime.session_store
    session = store.create(sub=app.state.owner, roles=["teacher"], name="Ada", ttl_seconds=60)
    headers = _mock_bearer_auth(app, sub=app.state.owner, roles=["teacher"], name="Ada")

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        client.cookies.set("gustav_session", session.session_id)
        unit_id = await _create_unit(client, app, title="Scratch Grundlagen", unit_type="modular")

        phases = await client.get(f"/api/teaching/units/{unit_id}/phases")
        assert phases.status_code == 200
        phase_one = phases.json()[0]["id"]

        phase_two_response = await client.post(
            f"/api/teaching/units/{unit_id}/phases",
            json={"title": "Vertiefung"},
            headers={"Origin": "http://test"},
        )
        assert phase_two_response.status_code == 201
        phase_two = phase_two_response.json()["id"]

        intro = await client.post(
            f"/api/teaching/units/{unit_id}/modules",
            json={"title": "Figuren bewegen", "phase_id": phase_one},
            headers={"Origin": "http://test"},
        )
        assert intro.status_code == 201
        intro_module = intro.json()["id"]

        project = await client.post(
            f"/api/teaching/units/{unit_id}/modules",
            json={"title": "Mini-Spiel", "phase_id": phase_two},
            headers={"Origin": "http://test"},
        )
        assert project.status_code == 201
        project_module = project.json()["id"]

        phase_selection = await client.get(
            f"/api/teaching/views/units/{unit_id}/workspace",
            params={"phase_id": phase_two},
            headers=headers,
        )
        assert phase_selection.status_code == 200
        assert phase_selection.json()["selection"] == {
            "kind": "phase",
            "phase": {"id": phase_two, "title": "Vertiefung", "position": 2},
        }

        edge = await client.post(
            f"/api/teaching/units/{unit_id}/modules/edges",
            json={"from_module_id": intro_module, "to_module_id": project_module},
            headers={"Origin": "http://test"},
        )
        assert edge.status_code == 201

        response = await client.get(
            f"/api/teaching/views/units/{unit_id}/workspace",
            params={
                "module_id": project_module,
                "edge_from_module_id": intro_module,
                "edge_to_module_id": project_module,
            },
            headers=headers,
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["graph"]["kind"] == "modular"
    assert len(payload["graph"]["phases"]) == 2
    assert payload["graph"]["edges"] == [{"from": intro_module, "to": project_module}]
    assert payload["selection"] == {
        "kind": "edge",
        "edge": {
            "from_id": intro_module,
            "to_id": project_module,
            "from_title": "Figuren bewegen",
            "to_title": "Mini-Spiel",
            "exists": True,
        },
    }


@pytest.mark.anyio
async def test_teacher_unit_workspace_forbids_students(app) -> None:
    headers = _mock_bearer_auth(app, sub="student-view", roles=["student"], name="Lena")

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/teaching/views/units/11111111-1111-1111-1111-111111111111/workspace",
            headers=headers,
        )

    assert response.status_code == 403
    assert response.json() == {"error": "forbidden"}


@pytest.mark.parametrize("unit_type", ["linear", "modular"])
async def test_workspace_empty_first_last_and_real_ownership_boundaries(app, unit_type):
    headers = _mock_bearer_auth(app, sub=app.state.owner, roles=["teacher"], name="Test")
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Origin": "http://test", **headers},
    ) as client:
        unit_id = await _create_unit(client, app, title="Auswahl prüfen", unit_type=unit_type)
        path = f"/api/teaching/views/units/{unit_id}/workspace"
        empty = await client.get(path)
        assert empty.status_code == 200
        assert empty.json()["selection"] == {"kind": "none"}
        assert empty.json()["counts"]["modules_count"] == 0
        assert empty.json()["counts"]["sections_count"] == 0
        if unit_type == "modular":
            phases = empty.json()["graph"]["phases"]
            assert len(phases) == 1 and phases[0]["modules"] == []
            phase_id = phases[0]["id"]
        else:
            assert empty.json()["graph"]["nodes"] == []

        nodes = []
        for title in ("Anfang", "Ende"):
            suffix = "modules" if unit_type == "modular" else "sections"
            data = {"title": title}
            if unit_type == "modular":
                data["phase_id"] = phase_id
            node = await client.post(f"/api/teaching/units/{unit_id}/{suffix}", json=data)
            assert node.status_code == 201, node.text
            nodes.append(node.json()["id"])
        selection_key = "module" if unit_type == "modular" else "section"
        default = await client.get(path)
        assert default.json()["selection"][selection_key]["id"] == nodes[0]
        last = await client.get(path, params={f"{selection_key}_id": nodes[-1]})
        assert last.json()["selection"][selection_key]["id"] == nodes[-1]
        unknown = await client.get(path, params={f"{selection_key}_id": str(uuid4())})
        assert unknown.status_code == 200
        assert unknown.json()["selection"] == {"kind": "none"}

        section_id = nodes[0]
        if unit_type == "modular":
            target = await client.get(
                f"/api/teaching/units/{unit_id}/modules/{nodes[0]}/content-target"
            )
            assert target.status_code == 200
            section_id = target.json()["section_id"]
        content_base = f"/api/teaching/units/{unit_id}/sections/{section_id}"
        material = await client.post(
            f"{content_base}/materials", json={"title": "Material", "body_md": "Inhalt"}
        )
        task = await client.post(
            f"{content_base}/tasks",
            json={
                "instruction_md": "Aufgabe",
                "criteria": [],
                "teacher_context_md": "Privater Workspace-Testkontext",
            },
        )
        assert material.status_code == task.status_code == 201
        populated = await client.get(path)
        graph = populated.json()["graph"]
        graph_nodes = graph["phases"][0]["modules"] if unit_type == "modular" else graph["nodes"]
        assert graph_nodes[0]["materials_count"] == graph_nodes[0]["tasks_count"] == 1
        assert graph_nodes[1]["materials_count"] == graph_nodes[1]["tasks_count"] == 0
        assert "Privater Workspace-Testkontext" not in populated.text

        # Only the author can read the teaching workspace, even with an admin role.
        for role in ("teacher", "admin"):
            _mock_bearer_auth(app, sub=f"foreign-{uuid4()}", roles=[role], name="Test")
            foreign = await client.get(path)
            missing = await client.get(f"/api/teaching/views/units/{uuid4()}/workspace")
            assert foreign.status_code == 403
            assert missing.status_code == 404
            for response in (foreign, missing):
                assert response.headers["Cache-Control"] == "private, no-store"
