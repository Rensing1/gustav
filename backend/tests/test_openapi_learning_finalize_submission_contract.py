from pathlib import Path

import yaml


def _spec() -> dict:
    root = Path(__file__).resolve().parents[2]
    return yaml.safe_load((root / "api" / "openapi.yml").read_text(encoding="utf-8"))


def test_openapi_has_finalize_learning_submission_path() -> None:
    spec = _spec()
    path_item = spec["paths"].get("/api/learning/courses/{course_id}/tasks/{task_id}/submissions/finalize")
    assert path_item is not None
    assert "post" in path_item


def test_openapi_finalize_learning_submission_returns_learning_submission() -> None:
    spec = _spec()
    operation = spec["paths"]["/api/learning/courses/{course_id}/tasks/{task_id}/submissions/finalize"]["post"]
    responses = operation["responses"]
    success_schema = responses["201"]["content"]["application/json"]["schema"]
    assert success_schema["$ref"] == "#/components/schemas/LearningSubmission"
    assert "409" in responses


def test_openapi_finalize_learning_submission_binds_the_reviewed_feedback_draft() -> None:
    spec = _spec()
    operation = spec["paths"]["/api/learning/courses/{course_id}/tasks/{task_id}/submissions/finalize"]["post"]
    request_body = operation["requestBody"]
    schema = request_body["content"]["application/json"]["schema"]

    assert request_body["required"] is True
    assert schema["required"] == ["feedback_submission_id"]
    assert schema["properties"]["feedback_submission_id"] == {"type": "string", "format": "uuid"}
    assert schema["additionalProperties"] is False
