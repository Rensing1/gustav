"""
OpenAPI Contract — Scratch SB3 tasks (contract-first)

Ensures the public API contract exposes:
- Task.kind includes 'scratch' as a possible backend value (read-only)
- ScratchTaskConfig marker schema
- Task/TaskCreate/TaskUpdate support a `scratch` config object
- Learning submissions accept SB3 MIME for file payloads
"""

from __future__ import annotations

import yaml


def load_spec() -> dict:
    with open("api/openapi.yml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_openapi_has_scratch_task_config_and_task_field() -> None:
    spec = load_spec()
    schemas = spec.get("components", {}).get("schemas", {})

    assert "ScratchTaskConfig" in schemas
    assert "Task" in schemas
    task_props = (schemas["Task"].get("properties") or {})
    assert "scratch" in task_props


def test_openapi_task_kind_enums_include_scratch_where_applicable() -> None:
    spec = load_spec()
    schemas = spec.get("components", {}).get("schemas", {})

    assert "LearningTask" in schemas, "LearningTask schema should exist"
    kind_enum = (((schemas["LearningTask"].get("properties") or {}).get("kind") or {}).get("enum") or [])
    assert "scratch" in kind_enum


def test_openapi_learning_submission_file_mime_includes_sb3() -> None:
    spec = load_spec()
    paths = spec.get("paths", {}) or {}
    endpoint = paths.get("/api/learning/courses/{course_id}/tasks/{task_id}/submissions", {}) or {}
    post = endpoint.get("post", {}) or {}
    schema = (((post.get("requestBody") or {}).get("content") or {}).get("application/json") or {}).get("schema") or {}
    variants = schema.get("oneOf") or []
    assert isinstance(variants, list) and variants, "Expected oneOf payload for submissions"

    file_variants = []
    for v in variants:
        props = (v.get("properties") or {}) if isinstance(v, dict) else {}
        kind = (props.get("kind") or {}) if isinstance(props, dict) else {}
        kind_enum = kind.get("enum") or []
        if kind_enum == ["file"] or (isinstance(kind_enum, list) and "file" in kind_enum):
            file_variants.append(v)
    assert file_variants, "Expected a file submission variant in createLearningSubmission oneOf"

    mime_type = (((file_variants[0].get("properties") or {}).get("mime_type") or {}).get("enum") or [])
    assert "application/x.scratch.sb3" in mime_type
