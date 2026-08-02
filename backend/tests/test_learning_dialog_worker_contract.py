"""Worker contract tests for typed dialog assessment inputs."""

from backend.learning.workers.process_learning_submission_jobs import _resolve_analysis_mode


def test_dialog_submission_uses_dedicated_analysis_mode() -> None:
    assert (
        _resolve_analysis_mode(
            payload={"analysis_mode": "dialog"},
            internal_metadata={},
            task_kind="dialog",
            submission_kind="dialog",
        )
        == "dialog"
    )


def test_dialog_kind_fails_safe_to_dialog_mode_without_payload_hint() -> None:
    assert (
        _resolve_analysis_mode(
            payload={}, internal_metadata={}, task_kind="dialog", submission_kind="dialog"
        )
        == "dialog"
    )
