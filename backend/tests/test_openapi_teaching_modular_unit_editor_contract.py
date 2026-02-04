"""
OpenAPI contract: Teaching modular unit visual editor endpoints exist.

Why:
    The teacher visual editor requires dedicated Teaching API endpoints for
    graph loading, module creation, edge editing, and drag&drop reorder/move.
"""

from __future__ import annotations

import pathlib

import yaml


def test_openapi_has_teaching_modular_unit_editor_paths() -> None:
    spec = yaml.safe_load(pathlib.Path("api/openapi.yml").read_text(encoding="utf-8"))
    paths = spec.get("paths") or {}

    expected = [
        "/api/teaching/units/{unit_id}/modules/graph",
        "/api/teaching/units/{unit_id}/modules",
        "/api/teaching/units/{unit_id}/modules/{module_id}",
        "/api/teaching/units/{unit_id}/modules/edges",
        "/api/teaching/units/{unit_id}/phases/{phase_id}/modules/reorder",
    ]
    for path in expected:
        assert path in paths, f"missing {path} in openapi.yml"
