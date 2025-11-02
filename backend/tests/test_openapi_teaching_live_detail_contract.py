"""
OpenAPI Contract — Latest submission detail for a student and task (teaching)

We verify that the new path is present with expected response schemas and
security annotations.
"""
from __future__ import annotations

import os
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

