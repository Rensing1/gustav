"""
OpenAPI — Teaching Live Unit view (contract-first)

Checks that the new unit-level live endpoints and schemas are present and
document privacy headers for 200 responses.
"""
from __future__ import annotations

from pathlib import Path
import yaml


def _load_spec() -> dict:
    root = Path(__file__).resolve().parents[2]
    return yaml.safe_load((root / "api" / "openapi.yml").read_text(encoding="utf-8"))


def test_openapi_has_unit_live_summary_path_and_cache_header():
    spec = _load_spec()
    path = "/api/teaching/courses/{course_id}/units/{unit_id}/submissions/summary"
    assert path in spec["paths"], "summary path missing in OpenAPI"
    op = spec["paths"][path]["get"]
    resp200 = op["responses"]["200"]
    headers = resp200.get("headers", {})
    assert "Cache-Control" in headers, "200 must document Cache-Control header"
    # Basic response shape
    schema = resp200["content"]["application/json"]["schema"]
    assert schema["type"] == "object"
    assert set(schema["required"]) >= {"tasks", "rows", "cursor"}
    # Task list in the summary must include the task kind so UIs can render
    # H5P cells differently from native/visual tasks.
    task_items = schema["properties"]["tasks"]["items"]
    assert "kind" in task_items.get("required", []), "summary tasks must include kind"
    assert schema["properties"]["cursor"]["type"] == "string"
    assert schema["properties"]["cursor"]["format"] == "date-time"
    cursor_description = schema["properties"]["cursor"]["description"]
    assert "database clock" in cursor_description
    assert "host/database skew" in cursor_description
    assert "same database snapshot" not in cursor_description
    resp503 = op["responses"]["503"]
    assert "summary_cursor_unavailable" in resp503["description"]
    assert "Cache-Control" in resp503.get("headers", {})
    assert "non-integer" in op["responses"]["400"]["description"]


def test_openapi_has_unit_live_delta_path():
    spec = _load_spec()
    path = "/api/teaching/courses/{course_id}/units/{unit_id}/submissions/delta"
    assert path in spec["paths"], "delta path missing in OpenAPI"
    op = spec["paths"][path]["get"]
    assert "updated_since" in {p["name"] for p in op["parameters"]}
    resp200 = op["responses"]["200"]
    content = resp200.get("content", {})
    assert "application/json" in content, "delta must return JSON payload"
    schema = content["application/json"]["schema"]
    assert "cells" in schema.get("required", []), "delta payload must include cells list"


def test_openapi_teaching_live_schemas_present():
    spec = _load_spec()
    schemas = spec["components"]["schemas"]
    assert "TeachingStudentRef" in schemas
    assert "TeachingUnitTaskCell" in schemas
    assert "TeachingUnitLiveRow" in schemas
    assert "TeachingUnitDeltaCell" in schemas

    # H5P tasks keep `h5p_completed` but also expose the latest raw score.
    task_cell = schemas["TeachingUnitTaskCell"]
    assert "h5p_completed" in task_cell.get("properties", {}), "TeachingUnitTaskCell must expose h5p_completed"
    assert "score_raw" in task_cell.get("properties", {}), "TeachingUnitTaskCell must expose score_raw"
    assert "score_max" in task_cell.get("properties", {}), "TeachingUnitTaskCell must expose score_max"
    assert "created_at" in task_cell.get("properties", {}), "TeachingUnitTaskCell must expose created_at"
    delta_cell = schemas["TeachingUnitDeltaCell"]
    assert "h5p_completed" in delta_cell.get("properties", {}), "TeachingUnitDeltaCell must expose h5p_completed"
    assert "score_raw" in delta_cell.get("properties", {}), "TeachingUnitDeltaCell must expose score_raw"
    assert "score_max" in delta_cell.get("properties", {}), "TeachingUnitDeltaCell must expose score_max"
