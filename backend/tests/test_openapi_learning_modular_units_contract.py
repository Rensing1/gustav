"""
OpenAPI contract: modular learning units (graph + module content endpoints).

Why:
    Prevent regressions in the contract-first plan for modular units:
    - student can fetch graph payload (advance organizer)
    - student can fetch module content (materials/tasks) when unlocked

Checks:
    - paths exist
    - GET responses document 200/400/401/403/404
"""

from __future__ import annotations

from pathlib import Path

import yaml


def _load_spec() -> dict:
    root = Path(__file__).resolve().parents[2]
    return yaml.safe_load((root / "api" / "openapi.yml").read_text(encoding="utf-8"))


def test_openapi_learning_modular_units_paths_exist() -> None:
    spec = _load_spec()
    paths = spec.get("paths", {})
    assert "/api/learning/courses/{course_id}/units/{unit_id}/modules/graph" in paths
    assert "/api/learning/courses/{course_id}/units/{unit_id}/modules/{module_id}" in paths


def test_openapi_learning_modular_graph_has_standard_error_responses() -> None:
    spec = _load_spec()
    op = spec["paths"]["/api/learning/courses/{course_id}/units/{unit_id}/modules/graph"]["get"]
    responses = op.get("responses", {})
    for code in ("200", "400", "401", "403", "404", "503"):
        assert code in responses, f"Missing {code} response for modular graph endpoint"


def test_openapi_learning_modular_module_content_has_standard_error_responses() -> None:
    spec = _load_spec()
    op = spec["paths"]["/api/learning/courses/{course_id}/units/{unit_id}/modules/{module_id}"]["get"]
    responses = op.get("responses", {})
    for code in ("200", "400", "401", "403", "404", "503"):
        assert code in responses, f"Missing {code} response for module content endpoint"
