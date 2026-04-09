"""
OpenAPI contract test: learner submissions declare the submission intent.

Why:
    The learner workspace distinguishes informal feedback requests from formal
    submissions. The public contract must therefore document the request field
    and the history response field explicitly.
"""

from __future__ import annotations

from pathlib import Path

import yaml


def _load_spec() -> dict:
    root = Path(__file__).resolve().parents[2]
    return yaml.safe_load((root / "api" / "openapi.yml").read_text(encoding="utf-8"))


def test_learning_submission_request_variants_document_optional_intent_with_submit_default() -> None:
    spec = _load_spec()
    post_op = spec["paths"]["/api/learning/courses/{course_id}/tasks/{task_id}/submissions"]["post"]
    variants = (
        post_op["requestBody"]["content"]["application/json"]["schema"]["oneOf"]
    )

    for variant in variants:
        required = set(variant.get("required") or [])
        assert "intent" not in required
        intent = (variant.get("properties") or {}).get("intent") or {}
        assert intent.get("enum") == ["feedback", "submit"]
        assert intent.get("default") == "submit"


def test_learning_submission_schema_exposes_intent() -> None:
    spec = _load_spec()
    schema = spec["components"]["schemas"]["LearningSubmission"]

    required = set(schema["allOf"][1]["required"])
    assert "intent" in required
    intent = schema["allOf"][1]["properties"]["intent"]
    assert intent["enum"] == ["feedback", "submit"]
