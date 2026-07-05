"""
DBLearningRepo._row_to_submission helper guards our public contract.

These unit tests exercise the pure-Python mapping logic so we cover the
sanitization and branching behaviour (pending vs. completed) without relying on
PostgreSQL fixtures.
"""
from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any, Iterable, Optional
import uuid

from backend.learning.repo_db import DBLearningRepo

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPO_SOURCE = PROJECT_ROOT / "backend" / "learning" / "repo_db.py"
MAPPING_SOURCE = PROJECT_ROOT / "backend" / "learning" / "repo_submission_mapping.py"


def test_submission_mapping_helpers_live_outside_learning_repo_hotspot() -> None:
    repo_db = importlib.import_module("backend.learning.repo_db")
    mapping = importlib.import_module("backend.learning.repo_submission_mapping")
    repo_source = REPO_SOURCE.read_text(encoding="utf-8")
    mapping_source = MAPPING_SOURCE.read_text(encoding="utf-8")

    assert "def _sanitize_error_message(" not in repo_source
    assert "def _row_to_submission(" not in repo_source
    assert "def sanitize_error_message(" in mapping_source
    assert "def row_to_submission(" in mapping_source
    assert repo_db._sanitize_error_message is mapping.sanitize_error_message
    assert DBLearningRepo._row_to_submission is mapping.row_to_submission


def _sample_row(
    *,
    intent: str = "submit",
    status: str = "pending",
    kind: str = "file",
    score_raw: Optional[int] = None,
    score_max: Optional[int] = None,
    analysis_json: Optional[str] = None,
    feedback_md: Optional[str] = "Great job",
    vision_attempts: Optional[int] = None,
    vision_last_error: Optional[str] = None,
    feedback_last_attempt_at: Optional[str] = "2025-11-08T12:00:00+00:00",
    feedback_last_error: Optional[str] = None,
    created_at: str = "2025-11-08T11:00:00+00:00",
    completed_at: Optional[str] = None,
) -> Iterable[Any]:
    """Construct a tuple shaped like the SQL result consumed by `_row_to_submission`.

    The mapping expects the same column order as the `SELECT ...` statements in
    `DBLearningRepo` (id, attempt_nr, kind, score_raw, score_max, ... timestamps).
    """
    submission_id = str(uuid.uuid4())
    return (
        submission_id,
        1,  # attempt_nr
        intent,
        kind,
        score_raw,
        score_max,
        "raw student text",
        "application/pdf",
        2048,
        "submissions/course/task/student/file.pdf",
        "0" * 64,
        status,
        analysis_json,
        feedback_md,
        None,  # error_code
        vision_attempts,
        vision_last_error,
        feedback_last_attempt_at,
        feedback_last_error,
        created_at,
        completed_at,
    )


def test_row_to_submission_pending_hides_analysis_and_sanitizes_errors():
    """Pending rows keep analysis_json/feedback hidden and scrub telemetry errors."""
    row = _sample_row(
        status="pending",
        analysis_json='{"text":"should stay private"}',
        vision_attempts=None,
        vision_last_error="Vision failure secret_token=abc123 from adapter",
        feedback_last_error="Feedback KEY=my-secret=xyz",
        feedback_md="Should not be exposed yet",
    )

    submission = DBLearningRepo._row_to_submission(row)

    assert submission["analysis_status"] == "pending"
    assert submission["intent"] == "submit"
    assert submission["analysis_json"] is None
    assert submission["feedback_md"] is None, "pending submissions must hide feedback markdown"
    assert submission["vision_attempts"] == 0, "missing attempts fall back to zero"

    vision_error = submission["vision_last_error"] or ""
    feedback_error = submission["feedback_last_error"] or ""
    assert "[redacted]" in vision_error and "secret_token" not in vision_error
    assert "[redacted]" in feedback_error and "KEY" not in feedback_error


def test_row_to_submission_completed_truncates_long_errors_and_preserves_feedback():
    """Completed rows expose analysis/feedback while enforcing max error length."""
    long_error = "adapter stack trace " + ("x" * 400)
    row = _sample_row(
        status="completed",
        analysis_json='{"text": "well done"}',
        feedback_md="Great job",
        vision_attempts=3,
        vision_last_error=long_error,
        feedback_last_attempt_at="2025-11-08T13:37:00+00:00",
        feedback_last_error=long_error,
        completed_at="2025-11-08T13:38:00+00:00",
    )

    submission = DBLearningRepo._row_to_submission(row)

    assert submission["analysis_status"] == "completed"
    assert submission["intent"] == "submit"
    assert submission["analysis_json"] == {"text": "well done"}
    assert submission["feedback_md"] == "Great job"
    assert submission["vision_attempts"] == 3
    assert submission["feedback_last_attempt_at"] == "2025-11-08T13:37:00+00:00"

    assert submission["vision_last_error"] is not None
    assert len(submission["vision_last_error"]) <= 256
    assert submission["vision_last_error"].endswith("...")
    assert len(submission["feedback_last_error"]) <= 256


def test_row_to_submission_preserves_feedback_intent() -> None:
    """History rows must expose whether a learner asked for feedback or submitted formally."""
    row = _sample_row(intent="feedback", status="completed", analysis_json='{"text": "revise me"}')

    submission = DBLearningRepo._row_to_submission(row)

    assert submission["intent"] == "feedback"
