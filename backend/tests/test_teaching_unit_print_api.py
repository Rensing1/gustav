"""Contract and API tests for transient teacher-authored print PDFs."""

from __future__ import annotations

import importlib
from pathlib import Path

import httpx
import pytest
import yaml
from httpx import ASGITransport

import backend.web.main as main
from backend.tests.runtime_auth_helpers import install_session_store


teaching_routes = importlib.import_module("backend.web.routes.teaching")
pytestmark = pytest.mark.anyio("asyncio")


def _spec() -> dict:
    return yaml.safe_load(Path("api/openapi.yml").read_text(encoding="utf-8"))


def test_openapi_declares_print_selection_and_binary_pdf_contract() -> None:
    spec = _spec()
    selection = spec["paths"]["/api/teaching/units/{unit_id}/printable-content"]["get"]
    export = spec["paths"]["/api/teaching/units/{unit_id}/printable-pdf"]["post"]

    assert selection["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/TeachingUnitPrintableContent"
    }
    assert export["requestBody"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/TeachingUnitPrintRequest"
    }
    assert export["responses"]["200"]["content"]["application/pdf"]["schema"]["format"] == "binary"
    assert set(export["responses"]) >= {"200", "400", "401", "403", "404", "413", "422", "503"}


async def _create_linear_content(client: httpx.AsyncClient) -> tuple[str, str, str, str]:
    unit = await client.post(
        "/api/teaching/units",
        json={"title": "Netzwerke verstehen", "summary": "Grundlagen", "unit_type": "linear"},
        headers={"Origin": "http://test"},
    )
    assert unit.status_code == 201
    unit_id = unit.json()["id"]
    section = await client.post(
        f"/api/teaching/units/{unit_id}/sections",
        json={"title": "Einstieg"},
        headers={"Origin": "http://test"},
    )
    assert section.status_code == 201
    section_id = section.json()["id"]
    material = await client.post(
        f"/api/teaching/units/{unit_id}/sections/{section_id}/materials",
        json={"title": "Merkblatt", "body_md": "Ein **Netzwerk** verbindet Geräte."},
        headers={"Origin": "http://test"},
    )
    assert material.status_code == 201
    task = await client.post(
        f"/api/teaching/units/{unit_id}/sections/{section_id}/tasks",
        json={
            "instruction_md": "Erkläre den Begriff Netzwerk.",
            "criteria": ["Begriff korrekt"],
            "teacher_context_md": "Nur intern",
            "model_solution_md": "Geräte sind verbunden.",
            "due_at": "2026-09-10T08:00:00+00:00",
            "max_attempts": 2,
        },
        headers={"Origin": "http://test"},
    )
    assert task.status_code == 201
    return unit_id, section_id, material.json()["id"], task.json()["id"]


async def test_printable_content_lists_ordered_student_safe_selection_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = install_session_store(monkeypatch, main)
    teaching_routes.set_repo(teaching_routes._Repo())
    session = store.create(sub="print-author", roles=["teacher"], name="Ada", ttl_seconds=60)

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set("gustav_session", session.session_id)
        unit_id, section_id, material_id, task_id = await _create_linear_content(client)
        response = await client.get(f"/api/teaching/units/{unit_id}/printable-content")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    payload = response.json()
    assert payload["unit"] == {"id": unit_id, "title": "Netzwerke verstehen", "unit_type": "linear"}
    assert payload["modular_phases"] == []
    assert payload["limits"] == {
        "max_selected_items": 200,
        "max_source_bytes": 52_428_800,
        "max_output_bytes": 52_428_800,
        "max_pages": 200,
    }
    assert payload["linear_sections"] == [
        {
            "id": section_id,
            "kind": "section",
            "title": "Einstieg",
            "position": 1,
            "materials": [
                {
                    "id": material_id,
                    "content_type": "material",
                    "kind": "markdown",
                    "label": "Merkblatt",
                    "position": 1,
                    "mime_type": None,
                    "filename_original": None,
                    "size_bytes": None,
                }
            ],
            "tasks": [
                {
                    "id": task_id,
                    "content_type": "task",
                    "kind": "native",
                    "label": "Erkläre den Begriff Netzwerk.",
                    "position": 1,
                    "mime_type": None,
                    "filename_original": None,
                    "size_bytes": None,
                }
            ],
        }
    ]


async def test_print_endpoints_require_the_authoring_teacher(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = install_session_store(monkeypatch, main)
    teaching_routes.set_repo(teaching_routes._Repo())
    owner = store.create(sub="print-owner", roles=["teacher"], name="Ada", ttl_seconds=60)
    student = store.create(sub="print-student", roles=["student"], name="Ben", ttl_seconds=60)
    other_teacher = store.create(sub="print-other", roles=["teacher"], name="Cem", ttl_seconds=60)

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set("gustav_session", owner.session_id)
        unit_id, _section_id, material_id, _task_id = await _create_linear_content(client)

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        anonymous_list = await client.get(f"/api/teaching/units/{unit_id}/printable-content")
        anonymous_export = await client.post(
            f"/api/teaching/units/{unit_id}/printable-pdf",
            json={"material_ids": [material_id], "task_ids": []},
            headers={"Origin": "http://test"},
        )

        client.cookies.set("gustav_session", student.session_id)
        student_list = await client.get(f"/api/teaching/units/{unit_id}/printable-content")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set("gustav_session", other_teacher.session_id)
        foreign_list = await client.get(f"/api/teaching/units/{unit_id}/printable-content")
        foreign_export = await client.post(
            f"/api/teaching/units/{unit_id}/printable-pdf",
            json={"material_ids": [material_id], "task_ids": []},
            headers={"Origin": "http://test"},
        )

    assert anonymous_list.status_code == 401
    assert anonymous_export.status_code == 401
    assert student_list.status_code == 403
    assert foreign_list.status_code == 403
    assert foreign_export.status_code == 403


async def test_printable_pdf_requires_non_empty_same_origin_author_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = install_session_store(monkeypatch, main)
    teaching_routes.set_repo(teaching_routes._Repo())
    session = store.create(sub="print-author", roles=["teacher"], name="Ada", ttl_seconds=60)

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set("gustav_session", session.session_id)
        unit_id, _section_id, material_id, task_id = await _create_linear_content(client)

        empty = await client.post(
            f"/api/teaching/units/{unit_id}/printable-pdf",
            json={"material_ids": [], "task_ids": []},
            headers={"Origin": "http://test"},
        )
        csrf = await client.post(
            f"/api/teaching/units/{unit_id}/printable-pdf",
            json={"material_ids": [material_id], "task_ids": [task_id]},
        )

    assert empty.status_code == 400
    assert empty.json()["detail"] == "empty_print_selection"
    assert csrf.status_code == 403
    assert csrf.json()["detail"] == "csrf_violation"


async def test_printable_pdf_returns_transient_binary_and_rejects_foreign_item(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    print_routes = importlib.import_module("backend.web.routes.teaching_unit_prints")

    class Renderer:
        def render(self, document, *, policy):  # type: ignore[no-untyped-def]
            assert document["title"] == "Netzwerke verstehen"
            assert document["nodes"][0]["items"][0]["body_md"] == "Ein **Netzwerk** verbindet Geräte."
            return b"%PDF-1.7\nstudent-copy"

    store = install_session_store(monkeypatch, main)
    teaching_routes.set_repo(teaching_routes._Repo())
    monkeypatch.setattr(print_routes, "PDF_RENDERER", Renderer())
    session = store.create(sub="print-author", roles=["teacher"], name="Ada", ttl_seconds=60)

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set("gustav_session", session.session_id)
        unit_id, _section_id, material_id, _task_id = await _create_linear_content(client)
        exported = await client.post(
            f"/api/teaching/units/{unit_id}/printable-pdf",
            json={"material_ids": [material_id], "task_ids": []},
            headers={"Origin": "http://test"},
        )
        foreign = await client.post(
            f"/api/teaching/units/{unit_id}/printable-pdf",
            json={"material_ids": ["00000000-0000-4000-8000-000000000001"], "task_ids": []},
            headers={"Origin": "http://test"},
        )

    assert exported.status_code == 200
    assert exported.content.startswith(b"%PDF")
    assert exported.headers["content-type"] == "application/pdf"
    assert exported.headers["cache-control"] == "private, no-store"
    assert exported.headers["content-disposition"] == 'attachment; filename="gustav-netzwerke-verstehen-druckfassung.pdf"'
    assert foreign.status_code == 400
    assert foreign.json() == {"error": "bad_request", "detail": "invalid_print_selection"}
