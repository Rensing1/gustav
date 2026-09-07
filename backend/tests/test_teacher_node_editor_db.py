"""Real-DB content editor parity and ownership tests with run-owned cleanup."""

import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx
import psycopg
import pytest
from httpx import ASGITransport

from backend.teaching.repo_db import DBTeachingRepo
from backend.tests.utils.db import is_safe_db_test_dsn, require_db_or_skip
from backend.web.main import create_app

pytestmark = [pytest.mark.anyio("asyncio"), pytest.mark.db_write]


@pytest.fixture
def app():
    require_db_or_skip()
    claims = {}
    app = create_app(access_token_verifier=lambda token, cfg: claims)
    app.state.claims = claims
    app.state.owner = f"editor-{uuid4()}"
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


async def _create_unit(client, app, *, title, unit_type="linear", summary=None):
    response = await client.post(
        "/api/teaching/units",
        json={"title": title, "unit_type": unit_type, "summary": summary},
        headers={"Origin": "http://test"},
    )
    assert response.status_code == 201, response.text
    unit_id = response.json()["id"]
    app.state.unit_ids.append(unit_id)
    return unit_id


@pytest.mark.parametrize(
    "unit_type,module_kind", [("linear", None), ("modular", "learning"), ("modular", "practice")]
)
async def test_editor_empty_nodes_and_owner_unit_boundaries(app, unit_type, module_kind):
    headers = _mock_bearer_auth(app, sub=app.state.owner, roles=["teacher"], name="Ada")
    session = app.state.runtime.session_store.create(
        sub=app.state.owner, roles=["teacher"], name="Ada", ttl_seconds=60
    )
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Origin": "http://test", **headers},
    ) as client:
        client.cookies.set("gustav_session", session.session_id)
        units, nodes = [], []
        for index in range(2):
            unit_id = await _create_unit(client, app, title=f"Einheit {index}", unit_type=unit_type)
            units.append(unit_id)
            unit_nodes = []
            if unit_type == "modular":
                phases = await client.get(f"/api/teaching/units/{unit_id}/phases")
                assert phases.status_code == 200
                phase_id = phases.json()[0]["id"]
            for title in ("Anfang", "Ende"):
                if unit_type == "modular":
                    response = await client.post(
                        f"/api/teaching/units/{unit_id}/modules",
                        json={"title": title, "phase_id": phase_id, "module_kind": module_kind},
                    )
                else:
                    response = await client.post(
                        f"/api/teaching/units/{unit_id}/sections", json={"title": title}
                    )
                assert response.status_code == 201, response.text
                node_id = response.json()["id"]
                unit_nodes.append(node_id)
                view = await client.get(
                    f"/api/teaching/views/units/{unit_id}/nodes/{node_id}/editor"
                )
                assert view.status_code == 200
                assert view.json()["node"]["title"] == title
                assert view.json()["materials"] == view.json()["tasks"] == []
                if module_kind:
                    assert view.json()["settings"]["module_kind"] == module_kind
            nodes.append(unit_nodes)

        cross_unit = await client.get(
            f"/api/teaching/views/units/{units[0]}/nodes/{nodes[1][0]}/editor"
        )
        assert cross_unit.status_code == 404
        missing_node = await client.get(
            f"/api/teaching/views/units/{units[0]}/nodes/{uuid4()}/editor"
        )
        assert missing_node.status_code == 404
        client.cookies.clear()
        headers = _mock_bearer_auth(app, sub=f"foreign-{uuid4()}", roles=["teacher"], name="Test")
        foreign_unit = await client.get(
            f"/api/teaching/views/units/{units[0]}/nodes/{nodes[0][0]}/editor", headers=headers
        )
        missing_unit = await client.get(
            f"/api/teaching/views/units/{uuid4()}/nodes/{nodes[0][0]}/editor", headers=headers
        )
        assert foreign_unit.status_code == 403
        assert missing_unit.status_code == 404
        for response in (cross_unit, missing_node, foreign_unit, missing_unit):
            assert response.headers["Cache-Control"] == "private, no-store"


@pytest.mark.anyio
async def test_teacher_unit_node_editor_returns_linear_section_content(
    app,
) -> None:
    store = app.state.runtime.session_store
    repo = DBTeachingRepo()
    owner = app.state.owner
    session = store.create(sub=owner, roles=["teacher"], name="Ada", ttl_seconds=60)
    headers = _mock_bearer_auth(app, sub=owner, roles=["teacher"], name="Ada")

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
        node_id = section.json()["id"]

        material = await client.post(
            f"/api/teaching/units/{unit_id}/sections/{node_id}/materials",
            json={"title": "Quellentext", "body_md": "Material"},
            headers={"Origin": "http://test"},
        )
        assert material.status_code == 201

        intent_id, material_id = str(uuid4()), str(uuid4())
        intent = repo.create_file_upload_intent(
            unit_id,
            node_id,
            owner,
            intent_id=intent_id,
            material_id=material_id,
            storage_key="materials/test/source.pdf",
            filename="quelle.pdf",
            mime_type="application/pdf",
            size_bytes=1024,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
        )
        assert intent["intent_id"] == intent_id
        file_material, created = repo.finalize_upload_intent_create_material(
            intent_id,
            unit_id,
            node_id,
            owner,
            title="Originalquelle",
            alt_text="PDF Quelle",
            sha256="a" * 64,
        )
        assert created is True
        assert file_material["id"] == material_id

        task = await client.post(
            f"/api/teaching/units/{unit_id}/sections/{node_id}/tasks",
            json={
                "instruction_md": "Fasse die Quelle zusammen.",
                "criteria": ["Inhalt", "Struktur"],
                "teacher_context_md": "Nutze nur den Quellentext.",
                "model_solution_md": None,
                "due_at": "2026-05-01T08:00:00+00:00",
                "max_attempts": 2,
                "scratch": {},
            },
            headers={"Origin": "http://test"},
        )
        assert task.status_code == 201

        dialog_config = {
            "partner_name": "Dr. Dialog",
            "partner_description_md": "Eine sichtbare Kurzbeschreibung.",
            "role_md": "Stelle präzise Rückfragen.",
            "learning_goal_md": "Argumente begründet prüfen.",
            "opening_message_md": "Welche Position vertrittst du?",
            "response_mode": "hybrid",
            "max_rounds": 7,
            "closing_prompt_md": "Fasse dein Ergebnis zusammen.",
        }
        dialog_task = await client.post(
            f"/api/teaching/units/{unit_id}/sections/{node_id}/tasks",
            json={
                "instruction_md": "Führe einen prüfenden Dialog.",
                "criteria": ["Begründete Antworten"],
                "teacher_context_md": "Interner Fachkontext.",
                "model_solution_md": None,
                "max_attempts": 3,
                "dialog": dialog_config,
            },
            headers={"Origin": "http://test"},
        )
        assert dialog_task.status_code == 201

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
            "id": material_id,
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
            "model_solution_md": None,
            "due_at": "2026-05-01T08:00:00+00:00",
            "max_attempts": 2,
            "position": 1,
            "kind": "scratch",
            "h5p": None,
            "visual": None,
            "scratch": {},
            "calliope": None,
            "filius": None,
            "dialog": None,
        },
        {
            "id": dialog_task.json()["id"],
            "instruction_md": "Führe einen prüfenden Dialog.",
            "criteria": ["Begründete Antworten"],
            "teacher_context_md": "Interner Fachkontext.",
            "model_solution_md": None,
            "due_at": None,
            "max_attempts": 3,
            "position": 2,
            "kind": "dialog",
            "h5p": None,
            "visual": None,
            "scratch": None,
            "calliope": None,
            "filius": None,
            "dialog": dialog_config,
        },
    ]
    assert payload["settings"]["kind"] == "section"


@pytest.mark.anyio
async def test_teacher_unit_node_editor_returns_modular_module_content(
    app,
) -> None:
    store = app.state.runtime.session_store
    repo = DBTeachingRepo()
    owner = app.state.owner
    session = store.create(sub=owner, roles=["teacher"], name="Ada", ttl_seconds=60)
    headers = _mock_bearer_auth(app, sub=owner, roles=["teacher"], name="Ada")

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        client.cookies.set("gustav_session", session.session_id)
        unit_id = await _create_unit(client, app, title="Scratch Grundlagen", unit_type="modular")
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

        backing = repo.get_unit_module_for_author(
            unit_id=unit_id, module_id=node_id, author_id=owner
        )
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
                "h5p": {"content_id": None, "display_options": {}},
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
        "backing_section_id": section_id,
        "module_kind": "learning",
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
            "model_solution_md": None,
            "due_at": None,
            "max_attempts": None,
            "position": 1,
            "kind": "h5p",
            "h5p": {"content_id": None, "display_options": {}},
            "visual": None,
            "scratch": None,
            "calliope": None,
            "filius": None,
            "dialog": None,
        }
    ]
    assert payload["settings"] == {
        "kind": "module",
        "required_prereq_count": 0,
        "module_kind": "learning",
    }
