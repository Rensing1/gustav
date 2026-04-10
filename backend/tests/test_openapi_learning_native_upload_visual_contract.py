"""
OpenAPI contract: native upload submissions are evaluated directly by the visual model.

Why:
    Native tasks still accept text and upload submissions, but upload submissions
    no longer go through OCR. The public contract must explain that `text_body`
    may stay empty after completed file/image analyses.
"""

from __future__ import annotations

from pathlib import Path

import yaml


def _load_spec() -> dict:
    root = Path(__file__).resolve().parents[2]
    return yaml.safe_load((root / "api" / "openapi.yml").read_text(encoding="utf-8"))


def test_learning_submission_description_documents_native_uploads_use_visual_analysis() -> None:
    spec = _load_spec()
    post_op = spec["paths"]["/api/learning/courses/{course_id}/tasks/{task_id}/submissions"]["post"]
    description = str(post_op.get("description") or "")

    assert "For `Task.kind=native`, `kind=image|file` is accepted." in description
    assert "processed directly by the visual feedback pipeline" in description
    assert "do not run through OCR first" in description


def test_learning_submission_text_body_description_allows_completed_file_submissions_without_text() -> None:
    spec = _load_spec()
    schema = spec["components"]["schemas"]["LearningSubmission"]
    text_body = schema["allOf"][1]["properties"]["text_body"]
    description = str(text_body.get("description") or "")

    assert "may remain empty for completed visual-direct file analyses" in description

