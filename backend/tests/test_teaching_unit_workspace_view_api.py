"""API tests for the teacher unit graph workspace and node editor views."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

import httpx
import pytest
from httpx import ASGITransport


REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))

import main  # type: ignore
from identity_access.stores import SessionStore  # type: ignore
from routes import teaching as teaching_routes  # type: ignore


pytestmark = pytest.mark.anyio("asyncio")


def _mock_bearer_auth(
    monkeypatch: pytest.MonkeyPatch,
    *,
    sub: str,
    roles: list[str],
    name: str,
) -> dict[str, str]:
    monkeypatch.setattr(
        main,
        "verify_bearer_token",
        lambda token, cfg: {
            "sub": sub,
            "name": name,
            "gustav_display_name": name,
            "realm_access": {"roles": roles},
            "exp": 4102444800,
        },
    )
    return {"Authorization": "Bearer test.jwt"}


async def _create_unit(
    client: httpx.AsyncClient,
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
    return response.json()["id"]


@pytest.mark.anyio
async def test_teacher_unit_workspace_returns_linear_graph_and_section_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = SessionStore()
    monkeypatch.setattr(main, "SESSION_STORE", store)
    teaching_routes.set_repo(teaching_routes._Repo())
    session = store.create(sub="teacher-unit-workspace", roles=["teacher"], name="Ada", ttl_seconds=60)
    headers = _mock_bearer_auth(monkeypatch, sub="teacher-unit-workspace", roles=["teacher"], name="Ada")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set("gustav_session", session.session_id)
        unit_id = await _create_unit(client, title="Weimarer Republik", summary="Aufbau und Krisen")
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
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = SessionStore()
    monkeypatch.setattr(main, "SESSION_STORE", store)
    repo = teaching_routes._Repo()
    teaching_routes.set_repo(repo)
    required_methods = (
        "list_unit_phases_for_author",
        "create_unit_phase",
        "create_unit_module_for_author",
        "list_unit_modules_for_author",
        "list_unit_module_edges_for_author",
    )
    if not all(hasattr(repo, method_name) for method_name in required_methods):
        pytest.skip("In-memory repo does not support modular unit workspace flows.")
    session = store.create(sub="teacher-unit-modular", roles=["teacher"], name="Ada", ttl_seconds=60)
    headers = _mock_bearer_auth(monkeypatch, sub="teacher-unit-modular", roles=["teacher"], name="Ada")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set("gustav_session", session.session_id)
        unit_id = await _create_unit(client, title="Scratch Grundlagen", unit_type="modular")

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
async def test_teacher_unit_node_editor_returns_linear_section_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = SessionStore()
    monkeypatch.setattr(main, "SESSION_STORE", store)
    repo = teaching_routes._Repo()
    teaching_routes.set_repo(repo)
    session = store.create(sub="teacher-unit-node", roles=["teacher"], name="Ada", ttl_seconds=60)
    headers = _mock_bearer_auth(monkeypatch, sub="teacher-unit-node", roles=["teacher"], name="Ada")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set("gustav_session", session.session_id)
        unit_id = await _create_unit(client, title="Weimarer Republik", summary="Aufbau und Krisen")
        section = await client.post(
            f"/api/teaching/units/{unit_id}/sections",
            json={"title": "Krisenjahre"},
            headers={"Origin": "http://test"},
        )
        assert section.status_code == 201
        node_id = section.json()["id"]

        material = await client.post(
            f"/api/teaching/units/{unit_id}/sections/{node_id}/materials",
            json={"title": "Quellentext", "body_md": "Material"},
            headers={"Origin": "http://test"},
        )
        assert material.status_code == 201

        intent = repo.create_file_upload_intent(
            unit_id,
            node_id,
            "teacher-unit-node",
            intent_id="11111111-1111-1111-1111-111111111111",
            material_id="22222222-2222-2222-2222-222222222222",
            storage_key="materials/test/source.pdf",
            filename="quelle.pdf",
            mime_type="application/pdf",
            size_bytes=1024,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
        )
        assert intent["intent_id"] == "11111111-1111-1111-1111-111111111111"
        file_material, created = repo.finalize_upload_intent_create_material(
            "11111111-1111-1111-1111-111111111111",
            unit_id,
            node_id,
            "teacher-unit-node",
            title="Originalquelle",
            alt_text="PDF Quelle",
            sha256="a" * 64,
        )
        assert created is True
        assert file_material["id"] == "22222222-2222-2222-2222-222222222222"

        task = await client.post(
            f"/api/teaching/units/{unit_id}/sections/{node_id}/tasks",
            json={
                "instruction_md": "Fasse die Quelle zusammen.",
                "criteria": ["Inhalt", "Struktur"],
                "teacher_context_md": "Nutze nur den Quellentext.",
                "due_at": "2026-05-01T08:00:00+00:00",
                "max_attempts": 2,
                "scratch": {},
            },
            headers={"Origin": "http://test"},
        )
        assert task.status_code == 201

        response = await client.get(
            f"/api/teaching/views/units/{unit_id}/nodes/{node_id}/editor",
            headers=headers,
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["node"] == {
        "id": node_id,
        "kind": "section",
        "title": "Krisenjahre",
        "editor_title": "Krisenjahre",
    }
    assert payload["materials"] == [
        {
            "id": material.json()["id"],
            "title": "Quellentext",
            "kind": "markdown",
            "body_md": "Material",
            "position": 1,
            "mime_type": None,
            "size_bytes": None,
            "filename_original": None,
            "alt_text": None,
        },
        {
            "id": "22222222-2222-2222-2222-222222222222",
            "title": "Originalquelle",
            "kind": "file",
            "body_md": "",
            "position": 2,
            "mime_type": "application/pdf",
            "size_bytes": 1024,
            "filename_original": "quelle.pdf",
            "alt_text": "PDF Quelle",
        },
    ]
    assert payload["tasks"] == [
        {
            "id": task.json()["id"],
            "instruction_md": "Fasse die Quelle zusammen.",
            "criteria": ["Inhalt", "Struktur"],
            "teacher_context_md": "Nutze nur den Quellentext.",
            "due_at": "2026-05-01T08:00:00+00:00",
            "max_attempts": 2,
            "position": 1,
            "kind": "scratch",
            "h5p": None,
            "visual": None,
            "scratch": {},
            "calliope": None,
        }
    ]
    assert payload["settings"]["kind"] == "section"


@pytest.mark.anyio
async def test_teacher_unit_node_editor_returns_modular_module_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = SessionStore()
    monkeypatch.setattr(main, "SESSION_STORE", store)
    repo = teaching_routes._Repo()
    teaching_routes.set_repo(repo)
    required_methods = (
        "list_unit_phases_for_author",
        "create_unit_phase",
        "create_unit_module_for_author",
        "list_unit_modules_for_author",
        "get_unit_module_for_author",
    )
    if not all(hasattr(repo, method_name) for method_name in required_methods):
        pytest.skip("In-memory repo does not support modular unit node editor flows.")
    session = store.create(sub="teacher-unit-node-modular", roles=["teacher"], name="Ada", ttl_seconds=60)
    headers = _mock_bearer_auth(monkeypatch, sub="teacher-unit-node-modular", roles=["teacher"], name="Ada")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set("gustav_session", session.session_id)
        unit_id = await _create_unit(client, title="Scratch Grundlagen", unit_type="modular")
        phases = await client.get(f"/api/teaching/units/{unit_id}/phases")
        assert phases.status_code == 200
        phase_id = phases.json()[0]["id"]

        module = await client.post(
            f"/api/teaching/units/{unit_id}/modules",
            json={"title": "Figuren bewegen", "phase_id": phase_id},
            headers={"Origin": "http://test"},
        )
        assert module.status_code == 201
        node_id = module.json()["id"]

        backing = repo.get_unit_module_for_author(unit_id=unit_id, module_id=node_id, author_id="teacher-unit-node-modular")
        section_id = str((backing or {}).get("section_id") or "")
        assert section_id

        material = await client.post(
            f"/api/teaching/units/{unit_id}/sections/{section_id}/materials",
            json={"title": "Scratch Karte", "body_md": "Material"},
            headers={"Origin": "http://test"},
        )
        assert material.status_code == 201
        task = await client.post(
            f"/api/teaching/units/{unit_id}/sections/{section_id}/tasks",
            json={
                "instruction_md": "Baue das Spiel nach.",
                "criteria": [],
                "h5p": {"content_id": "content-42", "display_options": {}},
            },
            headers={"Origin": "http://test"},
        )
        assert task.status_code == 201

        response = await client.get(
            f"/api/teaching/views/units/{unit_id}/nodes/{node_id}/editor",
            headers=headers,
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["node"] == {
        "id": node_id,
        "kind": "module",
        "title": "Figuren bewegen",
        "editor_title": "Figuren bewegen",
    }
    assert payload["materials"] == [
        {
            "id": material.json()["id"],
            "title": "Scratch Karte",
            "kind": "markdown",
            "body_md": "Material",
            "position": 1,
            "mime_type": None,
            "size_bytes": None,
            "filename_original": None,
            "alt_text": None,
        }
    ]
    assert payload["tasks"] == [
        {
            "id": task.json()["id"],
            "instruction_md": "Baue das Spiel nach.",
            "criteria": [],
            "teacher_context_md": None,
            "due_at": None,
            "max_attempts": None,
            "position": 1,
            "kind": "h5p",
            "h5p": {"content_id": "content-42", "display_options": {}},
            "visual": None,
            "scratch": None,
            "calliope": None,
        }
    ]
    assert payload["settings"] == {
        "kind": "module",
        "required_prereq_count": 0,
    }


@pytest.mark.anyio
async def test_teacher_unit_workspace_forbids_students(monkeypatch: pytest.MonkeyPatch) -> None:
    headers = _mock_bearer_auth(monkeypatch, sub="student-view", roles=["student"], name="Lena")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.get(
            "/api/teaching/views/units/11111111-1111-1111-1111-111111111111/workspace",
            headers=headers,
        )

    assert response.status_code == 403
    assert response.json() == {"error": "forbidden"}
