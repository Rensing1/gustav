"""
OpenAPI — Teaching student live overview (contract-first)
"""
from __future__ import annotations

from pathlib import Path

import yaml


def _load_spec() -> dict:
    root = Path(__file__).resolve().parents[2]
    return yaml.safe_load((root / "api" / "openapi.yml").read_text(encoding="utf-8"))


def test_openapi_has_student_live_overview_path() -> None:
    spec = _load_spec()
    path = "/api/teaching/courses/{course_id}/students/{student_sub}/submissions/overview"
    assert path in spec["paths"], "student live overview path missing"
    op = spec["paths"][path]["get"]
    assert any(tag == "Teaching" for tag in op.get("tags", []))
    params = {p["name"]: p for p in op.get("parameters", [])}
    assert "course_id" in params
    assert "student_sub" in params
    assert "unit_ids" in params
    responses = op.get("responses", {})
    assert {"200", "400", "401", "403", "404"} <= set(responses.keys())
    ref = responses["200"]["content"]["application/json"]["schema"]["$ref"]
    assert ref.endswith("/TeachingStudentLiveOverview")


def test_openapi_has_student_live_overview_schemas() -> None:
    spec = _load_spec()
    schemas = spec["components"]["schemas"]
    assert "TeachingStudentLiveOverview" in schemas
    assert "TeachingStudentLiveOverviewUnit" in schemas
    assert "TeachingStudentLiveOverviewTask" in schemas
    overview = schemas["TeachingStudentLiveOverview"]
    assert set(overview.get("required", [])) >= {"student", "units"}
    unit = schemas["TeachingStudentLiveOverviewUnit"]
    assert set(unit.get("required", [])) >= {"id", "title", "tasks"}
    task = schemas["TeachingStudentLiveOverviewTask"]
    assert set(task.get("required", [])) >= {"id", "instruction_md", "position", "kind", "has_submission"}
