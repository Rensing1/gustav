"""Unit tests for deterministic Feedback error-code mapping in the worker."""

from __future__ import annotations

from backend.learning.workers import process_learning_submission_jobs as worker


def test_feedback_permanent_input_too_large_maps_to_input_too_large() -> None:
    """Oversized visual inputs should keep the precise public error code."""

    exc = worker.FeedbackPermanentError("input_too_large")

    assert worker._feedback_permanent_error_code(exc) == "input_too_large"  # type: ignore[attr-defined]


def test_feedback_invalid_analysis_keeps_specific_error_code() -> None:
    """Invalid structured analysis remains distinguishable from generic failures."""

    exc = worker.FeedbackInvalidAnalysisError("feedback_invalid_analysis")

    assert worker._feedback_permanent_error_code(exc) == "feedback_invalid_analysis"  # type: ignore[attr-defined]


def test_unknown_feedback_permanent_error_maps_to_feedback_failed() -> None:
    """Unexpected permanent Feedback errors keep the established generic code."""

    exc = worker.FeedbackPermanentError("invalid_feedback_format")

    assert worker._feedback_permanent_error_code(exc) == "feedback_failed"  # type: ignore[attr-defined]
