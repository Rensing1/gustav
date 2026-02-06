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


def test_openapi_modular_editor_endpoints_document_503_service_unavailable() -> None:
    """All modular editor endpoints must document repo-capability fallback (503)."""

    spec = _load_spec()
    paths = spec["paths"]
    expected_ops = [
        ("/api/teaching/units/{unit_id}/phases", "get"),
        ("/api/teaching/units/{unit_id}/phases", "post"),
        ("/api/teaching/units/{unit_id}/phases/{phase_id}", "patch"),
        ("/api/teaching/units/{unit_id}/phases/{phase_id}", "delete"),
        ("/api/teaching/units/{unit_id}/phases/reorder", "post"),
        ("/api/teaching/units/{unit_id}/modules/graph", "get"),
        ("/api/teaching/units/{unit_id}/modules", "post"),
        ("/api/teaching/units/{unit_id}/modules/{module_id}", "patch"),
        ("/api/teaching/units/{unit_id}/modules/{module_id}", "delete"),
        ("/api/teaching/units/{unit_id}/phases/{phase_id}/modules/reorder", "post"),
        ("/api/teaching/units/{unit_id}/modules/edges", "post"),
        ("/api/teaching/units/{unit_id}/modules/edges", "delete"),
        ("/api/teaching/units/{unit_id}/modules/{from_module_id}/edges/{to_module_id}", "delete"),
    ]
    for path, method in expected_ops:
        op = paths[path][method]
        assert "503" in (op.get("responses") or {}), f"{method.upper()} {path} must document 503"
