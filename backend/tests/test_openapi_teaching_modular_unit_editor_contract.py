"""
OpenAPI contract: Teaching modular unit visual editor endpoints exist.

Why:
    The teacher visual editor requires dedicated Teaching API endpoints for
    graph loading, module creation, edge editing, and drag&drop reorder/move.
"""

from __future__ import annotations

import pathlib

import yaml


def _load_spec() -> dict:
    return yaml.safe_load(pathlib.Path("api/openapi.yml").read_text(encoding="utf-8"))


def test_openapi_has_teaching_modular_unit_editor_paths() -> None:
    spec = _load_spec()
    paths = spec.get("paths") or {}

    expected = [
        "/api/teaching/units/{unit_id}/modules/graph",
        "/api/teaching/units/{unit_id}/modules",
        "/api/teaching/units/{unit_id}/modules/{module_id}",
        "/api/teaching/units/{unit_id}/modules/edges",
        "/api/teaching/units/{unit_id}/modules/{from_module_id}/edges/{to_module_id}",
        "/api/teaching/units/{unit_id}/phases/{phase_id}/modules/reorder",
    ]
    for path in expected:
        assert path in paths, f"missing {path} in openapi.yml"


def test_openapi_edge_delete_400_documents_invalid_unit_type() -> None:
    spec = _load_spec()
    path = "/api/teaching/units/{unit_id}/modules/edges"
    desc = spec["paths"][path]["delete"]["responses"]["400"]["description"]
    assert "invalid_unit_type" in desc


def test_openapi_edge_create_409_documents_duplicate_edge() -> None:
    spec = _load_spec()
    path = "/api/teaching/units/{unit_id}/modules/edges"
    conflict = spec["paths"][path]["post"]["responses"]["409"]
    content = conflict["content"]["application/json"]
    assert content["schema"]["$ref"] == "#/components/schemas/Error"
    examples = content.get("examples") or {}
    duplicate = examples.get("duplicate_edge") or {}
    value = duplicate.get("value") or {}
    assert value.get("detail") == "duplicate_edge"
