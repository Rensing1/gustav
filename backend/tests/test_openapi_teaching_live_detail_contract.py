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
    assert {"200", "204", "403", "404", "500", "503"}.issubset(responses)
    assert responses["500"]["$ref"] == "#/components/responses/InternalServerError500"
    assert responses["503"]["$ref"] == "#/components/responses/TeachingRepositoryUnavailable503"
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


def test_openapi_latest_submission_file_documents_repository_outage() -> None:
    """The stable file route must distinguish a DB outage from a missing file."""

    repo_root = Path(__file__).resolve().parents[2]
    spec = yaml.safe_load((repo_root / "api" / "openapi.yml").read_text(encoding="utf-8"))
    target = (
        "/api/teaching/courses/{course_id}/units/{unit_id}/tasks/{task_id}/"
        "students/{student_sub}/submissions/latest/file"
    )
    responses = spec["paths"][target]["get"]["responses"]

    unavailable = responses["503"]
    schema = unavailable["content"]["application/json"]["schema"]
    assert schema["$ref"] == "#/components/schemas/Error"


def test_latest_submission_endpoints_document_private_internal_errors() -> None:
    """Unexpected failures must not masquerade as empty domain results."""

    repo_root = Path(__file__).resolve().parents[2]
    spec = yaml.safe_load((repo_root / "api" / "openapi.yml").read_text(encoding="utf-8"))
    component = spec["components"]["responses"]["InternalServerError500"]
    assert component["headers"]["Cache-Control"]["schema"]["example"] == "private, no-store"
    assert component["headers"]["Vary"]["schema"]["example"] == "Origin"
    assert component["content"]["application/json"]["schema"]["$ref"] == "#/components/schemas/Error"
    assert component["content"]["application/json"]["examples"]["default"]["value"] == {
        "error": "internal_error"
    }

    targets = (
        "/api/teaching/courses/{course_id}/units/{unit_id}/tasks/{task_id}/"
        "students/{student_sub}/submissions/latest",
        "/api/teaching/courses/{course_id}/units/{unit_id}/tasks/{task_id}/"
        "students/{student_sub}/submissions/latest/file",
    )
    for target in targets:
        assert spec["paths"][target]["get"]["responses"]["500"]["$ref"] == (
            "#/components/responses/InternalServerError500"
        )
