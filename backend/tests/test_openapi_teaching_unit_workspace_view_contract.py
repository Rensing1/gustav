"""OpenAPI contract tests for the teacher unit workspace read-model."""

from __future__ import annotations

from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_spec() -> dict:
    with (REPO_ROOT / "api" / "openapi.yml").open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def test_teacher_unit_workspace_path_exists() -> None:
    spec = _load_spec()

    path_item = spec["paths"]["/api/teaching/views/units/{unit_id}/workspace"]["get"]

    assert path_item["operationId"] == "getTeacherUnitWorkspace"
    assert [parameter["name"] for parameter in path_item["parameters"]] == [
        "unit_id",
        "section_id",
        "phase_id",
        "module_id",
        "edge_from_module_id",
        "edge_to_module_id",
    ]
    assert path_item["responses"]["200"]["content"]["application/json"]["schema"]["$ref"] == (
        "#/components/schemas/TeacherUnitWorkspaceView"
    )


def test_teacher_unit_workspace_schema_is_graph_driven() -> None:
    spec = _load_spec()
    schemas = spec["components"]["schemas"]

    workspace = schemas["TeacherUnitWorkspaceView"]
    assert workspace["required"] == ["user", "unit", "counts", "graph", "selection"]
    assert workspace["properties"]["graph"]["$ref"] == "#/components/schemas/TeacherUnitWorkspaceGraph"
    assert workspace["properties"]["selection"]["$ref"] == "#/components/schemas/TeacherUnitWorkspaceSelection"

    graph = schemas["TeacherUnitWorkspaceGraph"]
    assert graph["properties"]["kind"]["enum"] == ["linear", "modular"]

    selection = schemas["TeacherUnitWorkspaceSelection"]
    assert selection["required"] == ["kind"]
    assert selection["properties"]["kind"]["enum"] == ["none", "section", "phase", "module", "edge"]


def test_teacher_unit_node_editor_contract_exists() -> None:
    spec = _load_spec()

    path_item = spec["paths"]["/api/teaching/views/units/{unit_id}/nodes/{node_id}/editor"]["get"]
    assert path_item["operationId"] == "getTeacherUnitNodeEditor"
    assert [parameter["name"] for parameter in path_item["parameters"]] == ["unit_id", "node_id"]
    assert path_item["responses"]["200"]["content"]["application/json"]["schema"]["$ref"] == (
        "#/components/schemas/TeacherUnitNodeEditorView"
    )

    node_editor = spec["components"]["schemas"]["TeacherUnitNodeEditorView"]
    assert node_editor["required"] == ["user", "unit", "node", "materials", "tasks", "settings"]

    material = spec["components"]["schemas"]["TeacherUnitNodeEditorMaterial"]
    assert material["required"] == ["id", "title", "kind", "position"]
    assert material["properties"]["kind"]["enum"] == ["markdown", "file"]
    assert material["properties"]["body_md"]["nullable"] is True
    assert material["properties"]["position"]["type"] == "integer"
    assert material["properties"]["mime_type"]["nullable"] is True
    assert material["properties"]["size_bytes"]["nullable"] is True
    assert material["properties"]["filename_original"]["nullable"] is True
    assert material["properties"]["alt_text"]["nullable"] is True

    task = spec["components"]["schemas"]["TeacherUnitNodeEditorTask"]
    assert task["required"] == ["id", "instruction_md", "criteria", "kind", "position"]
    assert task["properties"]["instruction_md"]["type"] == "string"
    assert task["properties"]["criteria"]["type"] == "array"
    assert task["properties"]["kind"]["enum"] == [
        "native",
        "h5p",
        "visual",
        "scratch",
        "calliope",
        "filius",
        "dialog",
    ]
    assert task["properties"]["position"]["type"] == "integer"
    assert task["properties"]["teacher_context_md"]["nullable"] is True
    assert task["properties"]["due_at"]["nullable"] is True
    assert task["properties"]["max_attempts"]["nullable"] is True
    assert task["properties"]["h5p"]["nullable"] is True
    assert task["properties"]["visual"]["nullable"] is True
    assert task["properties"]["scratch"]["nullable"] is True
    assert task["properties"]["calliope"]["nullable"] is True
