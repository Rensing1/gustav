"""
OpenAPI Contract — Latest submission detail for a student and task (teaching)

We verify that the new path is present with expected response schemas and
security annotations.
"""
from __future__ import annotations

from pathlib import Path

import yaml


def test_openapi_has_latest_submission_detail_path():
    repo_root = Path(__file__).resolve().parents[2]
    spec_path = repo_root / "api" / "openapi.yml"
    with spec_path.open("r", encoding="utf-8") as fh:
        spec = yaml.safe_load(fh)

    paths = spec.get("paths", {})
    target = "/api/teaching/courses/{course_id}/units/{unit_id}/tasks/{task_id}/students/{student_sub}/submissions/latest"
    assert target in paths, "latest submission detail path must exist in the contract"
    get = paths[target].get("get", {})
    assert any(t == "Teaching" for t in get.get("tags", [])), "tag Teaching expected"
    responses = get.get("responses", {})
    assert "200" in responses and "204" in responses and "403" in responses and "404" in responses
    # Schema reference present
    content = responses["200"].get("content", {}).get("application/json", {})
    schema = content.get("schema", {})
    assert schema.get("$ref", "").endswith("/TeachingLatestSubmission"), "schema ref expected"


def test_teaching_latest_submission_schema_supports_h5p_review_fields():
    """Contract: Teaching latest submission supports `kind=h5p` with score + review token."""
    repo_root = Path(__file__).resolve().parents[2]
    spec_path = repo_root / "api" / "openapi.yml"
    with spec_path.open("r", encoding="utf-8") as fh:
        spec = yaml.safe_load(fh)

    schemas = (spec.get("components") or {}).get("schemas", {})
    assert "TeachingLatestSubmission" in schemas
    sub = schemas["TeachingLatestSubmission"]
    props = sub.get("properties") or {}

    kind = (props.get("kind") or {})
    assert "h5p" in (kind.get("enum") or []), "TeachingLatestSubmission.kind must include 'h5p'"

    assert "score_raw" in props
    assert "score_max" in props
    assert "h5p" in props

    h5p = props["h5p"]
    assert h5p.get("type") == "object"
    h5p_props = h5p.get("properties") or {}
    assert "content_id" in h5p_props
    assert "review_token" in h5p_props
    assert "instruction_md" in props
    required = sub.get("required") or []
    assert "instruction_md" in required
