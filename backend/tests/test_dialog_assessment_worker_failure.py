"""Malformed dialog results fail through the real adapter and worker boundary."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

from backend.learning.adapters import local_feedback
from backend.learning.adapters.dspy import dialog_assessment_program
from backend.learning.workers import process_learning_submission_jobs as worker


def test_malformed_dialog_output_fails_instead_of_persisting_a_grade(monkeypatch):
    monkeypatch.setattr(
        dialog_assessment_program.dspy,
        "Predict",
        lambda _signature: lambda **_kwargs: SimpleNamespace(
            criteria_results=[{}], feedback_md="Ihre Begründung ist überzeugend."
        ),
    )
    adapter = local_feedback._LocalFeedbackAdapter()
    monkeypatch.setattr(adapter, "_get_text_analysis_lm", lambda: None)
    monkeypatch.setattr(local_feedback, "capture_dspy_usage", lambda operation, **_kwargs: (operation(), []))
    conn = MagicMock()
    monkeypatch.setattr(worker, "_set_current_sub", MagicMock())
    monkeypatch.setattr(worker, "_fetch_submission", lambda *_args, **_kwargs: {
        "analysis_status": "pending", "kind": "dialog", "task_id": "task",
        "student_sub": "student", "course_id": "course",
    })
    monkeypatch.setattr(worker, "_fetch_task_context", lambda **_kwargs: {})
    completed = MagicMock()
    failed = MagicMock()
    job_failed = MagicMock()
    retry = MagicMock()
    monkeypatch.setattr(worker, "_update_submission_completed", completed)
    monkeypatch.setattr(worker, "_update_submission_failed", failed)
    monkeypatch.setattr(worker, "_mark_job_failed", job_failed)
    monkeypatch.setattr(worker, "_nack_retry", retry)

    worker._process_job(
        conn=conn,
        job=worker.QueuedJob(id="job", submission_id="submission", retry_count=0, payload={
            "criteria": ["Begründen"], "instruction_md": "Begründen Sie.",
            "student_performance": {"messages": [{"text": "Meine Begründung"}]},
            "conversation_context": {"assistant_messages": ["Eine Rückfrage"]},
        }),
        vision_adapter=MagicMock(), feedback_adapter=adapter, now=datetime.now(timezone.utc),
    )

    completed.assert_not_called()
    retry.assert_not_called()
    failed.assert_called_once_with(
        conn=conn, submission_id="submission", error_code="feedback_invalid_analysis",
        message="feedback_invalid_analysis",
    )
    job_failed.assert_called_once_with(conn=conn, job_id="job", error_code="feedback_invalid_analysis")
    assert conn.commit.call_count == 2
