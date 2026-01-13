"""
OpenAPI contract test: Learning H5P content access-check endpoint.

Why:
    The H5P sidecar must verify (fail-closed) whether a student is allowed to
    load a given H5P content id within a specific course. We keep the contract
    explicit and minimal: `204 No Content` on allowed, `404` otherwise.
"""

from __future__ import annotations

from pathlib import Path

import yaml


def _load_spec() -> dict:
    root = Path(__file__).resolve().parents[2]
    return yaml.safe_load((root / "api" / "openapi.yml").read_text(encoding="utf-8"))


def test_learning_h5p_access_endpoint_exists_in_openapi() -> None:
    spec = _load_spec()
    paths = spec.get("paths") or {}
    assert (
        "/api/learning/courses/{course_id}/h5p/contents/{content_id}/access" in paths
    ), "missing learning h5p access-check endpoint in openapi.yml"


def test_learning_h5p_access_contract_has_fail_closed_responses() -> None:
    spec = _load_spec()
    get_op = spec["paths"]["/api/learning/courses/{course_id}/h5p/contents/{content_id}/access"]["get"]
    assert get_op.get("security"), "endpoint must require cookie auth"
    assert (get_op.get("x-permissions") or {}).get("requiredRole") == "student"

    responses = get_op.get("responses") or {}
    for code in ("204", "400", "401", "403", "404"):
        assert code in responses, f"missing response {code}"

    params = get_op.get("parameters") or []
    course = next(p for p in params if p.get("name") == "course_id")
    assert (course.get("schema") or {}).get("format") == "uuid"
    content = next(p for p in params if p.get("name") == "content_id")
    assert (content.get("schema") or {}).get("pattern") == "^[0-9]+$"

