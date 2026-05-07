"""
OpenAPI Contract -- Filius FLS tasks (contract-first).

Intent:
    Filius tasks are upload-only network simulation tasks. The public API must
    expose the task kind, marker config, FLS MIME type, and stable validation
    detail codes before backend implementation follows.
"""

from __future__ import annotations

import yaml


FILIUS_MIME = "application/x.filius.fls"


def load_spec() -> dict:
    with open("api/openapi.yml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_openapi_has_filius_task_config_and_task_field() -> None:
    spec = load_spec()
    schemas = spec.get("components", {}).get("schemas", {})

    assert "FiliusTaskConfig" in schemas
    filius = schemas["FiliusTaskConfig"]
    assert filius.get("type") == "object"
    assert filius.get("additionalProperties") is False

    task_props = (schemas["Task"].get("properties") or {})
    assert "filius" in task_props


def test_openapi_task_kind_enums_include_filius_where_applicable() -> None:
    spec = load_spec()
    schemas = spec.get("components", {}).get("schemas", {})

    for schema_name in ("Task", "LearningTask", "TeacherUnitNodeEditorTask"):
        assert schema_name in schemas, f"{schema_name} schema should exist"
        kind_enum = (((schemas[schema_name].get("properties") or {}).get("kind") or {}).get("enum") or [])
        assert "filius" in kind_enum


def test_openapi_learning_submission_file_mime_includes_filius_fls() -> None:
    spec = load_spec()
    endpoint = (spec.get("paths", {}) or {}).get("/api/learning/courses/{course_id}/tasks/{task_id}/submissions", {}) or {}
    post = endpoint.get("post", {}) or {}
    schema = (((post.get("requestBody") or {}).get("content") or {}).get("application/json") or {}).get("schema") or {}
    variants = schema.get("oneOf") or []
    assert isinstance(variants, list) and variants, "Expected oneOf payload for submissions"

    file_variants = []
    for variant in variants:
        props = (variant.get("properties") or {}) if isinstance(variant, dict) else {}
        kind_enum = ((props.get("kind") or {}).get("enum") or []) if isinstance(props, dict) else []
        if isinstance(kind_enum, list) and "file" in kind_enum:
            file_variants.append(variant)
    assert file_variants, "Expected a file submission variant in createLearningSubmission oneOf"

    mime_type = (((file_variants[0].get("properties") or {}).get("mime_type") or {}).get("enum") or [])
    assert FILIUS_MIME in mime_type


def test_openapi_upload_intent_description_mentions_fls_for_filius() -> None:
    spec = load_spec()
    endpoint = (spec.get("paths", {}) or {}).get("/api/learning/courses/{course_id}/tasks/{task_id}/upload-intents", {}) or {}
    post = endpoint.get("post", {}) or {}
    description = str(post.get("description") or "")

    assert "filius" in description.lower()
    assert ".fls" in description.lower()
    assert FILIUS_MIME in description


def test_openapi_submission_errors_mention_filius_validation_detail_codes() -> None:
    spec = load_spec()
    endpoint = (spec.get("paths", {}) or {}).get("/api/learning/courses/{course_id}/tasks/{task_id}/submissions", {}) or {}
    post = endpoint.get("post", {}) or {}
    responses = post.get("responses", {}) or {}
    desc_400 = str((responses.get("400") or {}).get("description") or "")
    desc_503 = str((responses.get("503") or {}).get("description") or "")

    assert "invalid_filius_archive" in desc_400
    assert "missing_filius_configuration" in desc_400
    assert "invalid_filius_configuration" in desc_400
    assert "filius_configuration_too_large" in desc_400
    assert "filius_validation_unavailable" in desc_503
