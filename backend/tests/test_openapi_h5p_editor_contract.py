"""
OpenAPI contract tests for the Phase-1 H5P editor integration.

Why:
    Phase 1 must support real authoring in the browser (create/load/save),
    but still enforce the trusted-content model (teacher/admin only).
"""

from __future__ import annotations

from pathlib import Path

import yaml


def _load_spec() -> dict:
    root = Path(__file__).resolve().parents[2]
    return yaml.safe_load((root / "api" / "openapi.yml").read_text(encoding="utf-8"))


def test_h5p_editor_model_and_save_endpoints_exist_in_openapi():
    spec = _load_spec()
    paths = spec.get("paths") or {}

    assert "/h5p/editor/model" in paths, "missing /h5p/editor/model in openapi.yml"
    assert "/h5p/contents" in paths, "missing /h5p/contents in openapi.yml"
    assert "/h5p/contents/{content_id}" in paths, "missing /h5p/contents/{content_id} in openapi.yml"
    assert "/api/teaching/units/{unit_id}/sections/{section_id}/tasks/{task_id}/h5p/editor-model" in paths
    assert "/api/teaching/units/{unit_id}/sections/{section_id}/tasks/{task_id}/h5p/import" in paths
    assert "/api/teaching/units/{unit_id}/sections/{section_id}/tasks/{task_id}/h5p/export" in paths
    assert "/api/teaching/units/{unit_id}/sections/{section_id}/tasks/{task_id}/h5p/reset" in paths


def test_h5p_editor_model_contract():
    spec = _load_spec()
    get_op = spec["paths"]["/h5p/editor/model"]["get"]

    schemas = (spec.get("components") or {}).get("schemas", {})
    assert "H5PEditorModelResponse" in schemas
    assert get_op.get("security"), "GET /h5p/editor/model must require authentication"
    perms = get_op.get("x-permissions") or {}
    assert perms.get("requiredRole") == "teacher", "GET /h5p/editor/model must document teacher-only permission"
    responses = get_op.get("responses") or {}
    assert "200" in responses, "GET /h5p/editor/model must define 200 response"

    # Invalid query shapes (e.g. repeated content_id) should be visible as 400 in the contract.
    assert "400" in responses, "GET /h5p/editor/model must define 400 response"
    schema = (responses["400"].get("content") or {}).get("application/json", {}).get("schema") or {}
    assert schema.get("$ref") == "#/components/schemas/Error"


def test_h5p_contents_create_contract():
    spec = _load_spec()
    post_op = spec["paths"]["/h5p/contents"]["post"]

    schemas = (spec.get("components") or {}).get("schemas", {})
    assert "H5PContentSaveRequest" in schemas
    assert "H5PContentSaveResponse" in schemas
    assert post_op.get("security"), "POST /h5p/contents must require authentication"

    rb = post_op.get("requestBody") or {}
    assert rb.get("required") is True
    content = rb.get("content") or {}
    assert "application/json" in content
    assert "201" in (post_op.get("responses") or {}), "POST /h5p/contents must define 201 response"


def test_h5p_contents_update_contract():
    spec = _load_spec()
    patch_op = spec["paths"]["/h5p/contents/{content_id}"]["patch"]

    schemas = (spec.get("components") or {}).get("schemas", {})
    assert "H5PContentSaveRequest" in schemas
    assert "H5PContentSaveResponse" in schemas
    assert patch_op.get("security"), "PATCH /h5p/contents/{content_id} must require authentication"

    rb = patch_op.get("requestBody") or {}
    assert rb.get("required") is True
    content = rb.get("content") or {}
    assert "application/json" in content
    assert "200" in (patch_op.get("responses") or {}), "PATCH /h5p/contents/{content_id} must define 200 response"


def test_task_centric_h5p_authoring_endpoints_are_teacher_only_in_openapi():
    spec = _load_spec()
    paths = spec.get("paths") or {}

    expectations = [
        ("/api/teaching/units/{unit_id}/sections/{section_id}/tasks/{task_id}/h5p/editor-model", "get"),
        ("/api/teaching/units/{unit_id}/sections/{section_id}/tasks/{task_id}/h5p/import", "post"),
        ("/api/teaching/units/{unit_id}/sections/{section_id}/tasks/{task_id}/h5p/export", "get"),
        ("/api/teaching/units/{unit_id}/sections/{section_id}/tasks/{task_id}/h5p/reset", "post"),
    ]

    for path, method in expectations:
        op = (paths.get(path) or {}).get(method)
        assert isinstance(op, dict), f"missing {method.upper()} {path} in openapi.yml"
        assert op.get("security"), f"{method.upper()} {path} must require authentication"
        perms = op.get("x-permissions") or {}
        assert perms.get("requiredRole") == "teacher", f"{method.upper()} {path} must document teacher-only permission"
