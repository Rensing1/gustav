"""
OpenAPI contract tests for include parameter style/explode.

Checks that Learning endpoints using `include` declare style=form and explode=false
to ensure consistent client generation for CSV semantics.
"""
from __future__ import annotations

from pathlib import Path
import yaml


def _load_spec() -> dict:
    root = Path(__file__).resolve().parents[2]
    return yaml.safe_load((root / "api" / "openapi.yml").read_text(encoding="utf-8"))


def _find_param(params: list[dict], name: str) -> dict | None:
    for p in params or []:
        if p.get("name") == name and p.get("in") == "query":
            return p
    return None


def test_include_params_use_csv_style_form():
    spec = _load_spec()
    paths = spec.get("paths", {})

    for path in (
        "/api/learning/courses/{course_id}/sections",
        "/api/learning/courses/{course_id}/units/{unit_id}/sections",
    ):
        assert path in paths, f"missing path {path} in openapi.yml"
        get_op = paths[path]["get"]
        params = get_op.get("parameters", [])
        inc = _find_param(params, "include")
        assert inc is not None, f"missing include param for {path}"
        assert inc.get("style") == "form", f"include style must be form for {path}"
        assert inc.get("explode") is False, f"include explode must be false for {path}"


def test_learning_section_core_requires_unit_id():
    spec = _load_spec()
    core = spec["components"]["schemas"]["LearningSectionCore"]
    required = set(core.get("required") or [])
    assert "unit_id" in required, "unit_id should be required on LearningSectionCore"


def test_learning_courses_limit_defaults():
    spec = _load_spec()
    params = spec["paths"]["/api/learning/courses"]["get"].get("parameters", [])
    limit = next(p for p in params if p.get("name") == "limit")
    schema = limit.get("schema", {})
    assert schema.get("maximum") == 100
    assert schema.get("default") == 50
