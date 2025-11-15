import types
from datetime import datetime, timezone

import pytest


@pytest.fixture()
def worker_module(monkeypatch):
    """Import the worker module and monkeypatch DB dependencies to fakes.

    We avoid requiring a real Postgres by:
    - Forcing HAVE_PSYCOPG=True
    - Replacing psycopg.connect with a dummy connection that supports context usage
    - Monkeypatching internal DB helpers to record calls
    """
    import importlib

    mod = importlib.import_module(
        "backend.learning.workers.process_learning_submission_jobs"
    )

    # Pretend psycopg is available and provide a fake connection
    monkeypatch.setattr(mod, "HAVE_PSYCOPG", True)

    class FakeConn:
        def __init__(self):
            self.autocommit = False

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def commit(self):
            pass

        def rollback(self):
            pass

        # Some helpers use cursor() directly; we won't hit them in patched code paths.
        def cursor(self):
            raise AssertionError("cursor should not be called in patched tests")

    psy = types.SimpleNamespace(connect=lambda *a, **k: FakeConn())
    monkeypatch.setattr(mod, "psycopg", psy)

    # Recorders for side effects
    calls = {
        "update_completed": [],
        "delete_job": [],
        "mark_retry": [],
        "nack_retry": [],
        "update_failed": [],
        "mark_job_failed": [],
    }

    # Patch helpers to record instead of touching DB
    monkeypatch.setattr(
        mod,
        "_update_submission_completed",
        lambda **kw: calls["update_completed"].append(kw),
    )
    # Avoid touching DB GUCs in tests
    monkeypatch.setattr(mod, "_set_current_sub", lambda *a, **k: None)
    monkeypatch.setattr(
        mod, "_delete_job", lambda *a, **k: calls["delete_job"].append(k)
    )
    monkeypatch.setattr(
        mod,
        "_mark_submission_retry",
        lambda **kw: calls["mark_retry"].append(kw),
    )
    monkeypatch.setattr(
        mod,
        "_nack_retry",
        lambda **kw: calls["nack_retry"].append(kw) or datetime.now(timezone.utc),
    )
    monkeypatch.setattr(
        mod,
        "_update_submission_failed",
        lambda **kw: calls["update_failed"].append(kw),
    )
    monkeypatch.setattr(
        mod,
        "_mark_job_failed",
        lambda **kw: calls["mark_job_failed"].append(kw),
    )

    # Provide a default leased job and submission fetch
    job = mod.QueuedJob(
        id="job-1", submission_id="sub-1", retry_count=0, payload={"student_sub": "s|1"}
    )
    monkeypatch.setattr(mod, "_lease_next_job", lambda *a, **k: job)

    class Box:
        pass

    box = Box()
    box.calls = calls
    box.mod = mod
    return box


class DummyVision:
    def __init__(self, mod, text="Hello MD"):
        self.mod = mod
        self.text = text

    def extract(self, *, submission, job_payload):
        return self.mod.VisionResult(text_md=self.text, raw_metadata={"ok": True})


class DummyFeedback:
    def __init__(self, mod):
        self.mod = mod

    def analyze(self, *, text_md, criteria):
        return self.mod.FeedbackResult(
            feedback_md=f"Feedback for: {text_md}", analysis_json={"criteria": list(criteria)}
        )


def _submission(status: str):
    return {
        "id": "sub-1",
        "student_sub": "s|1",
        "analysis_status": status,
        "kind": "file",
        "mime_type": "application/pdf",
    }


def test_worker_processes_when_status_is_extracted(worker_module, monkeypatch):
    # Given a submission already in 'extracted' status (pages persisted)
    mod = worker_module.mod
    monkeypatch.setattr(mod, "_fetch_submission", lambda *a, **k: _submission("extracted"))

    # And functioning adapters
    vision = DummyVision(mod, text="MD text")
    feedback = DummyFeedback(mod)

    processed = mod.run_once(
        dsn="postgresql://fake",
        vision_adapter=vision,
        feedback_adapter=feedback,
        now=datetime(2025, 11, 5, tzinfo=timezone.utc),
    )

    assert processed is True
    # Then the worker should update completed and delete the job
    assert worker_module.calls["update_completed"], "expected update_completed to be called"
    assert worker_module.calls["delete_job"], "expected delete_job to be called"


def test_worker_vision_transient_error_schedules_retry(worker_module, monkeypatch):
    mod = worker_module.mod
    # Given a pending submission
    monkeypatch.setattr(mod, "_fetch_submission", lambda *a, **k: _submission("pending"))

    class TransientVision:
        def extract(self, *, submission, job_payload):
            raise mod.VisionTransientError("temporary failure")

    feedback = DummyFeedback(mod)

    processed = mod.run_once(
        dsn="postgresql://fake",
        vision_adapter=TransientVision(),
        feedback_adapter=feedback,
        now=datetime(2025, 11, 5, tzinfo=timezone.utc),
    )
    assert processed is True
    # Then a retry is marked and the job is re-queued
    assert worker_module.calls["mark_retry"], "expected mark_retry to be called"
    assert worker_module.calls["nack_retry"], "expected nack_retry to be called"
    # And not completed/failed
    assert not worker_module.calls["update_completed"]
    assert not worker_module.calls["update_failed"]
    assert not worker_module.calls["mark_job_failed"]


def test_worker_vision_permanent_error_marks_failed(worker_module, monkeypatch):
    mod = worker_module.mod
    monkeypatch.setattr(mod, "_fetch_submission", lambda *a, **k: _submission("pending"))

    class PermanentVision:
        def extract(self, *, submission, job_payload):
            raise mod.VisionPermanentError("bad input")

    feedback = DummyFeedback(mod)

    processed = mod.run_once(
        dsn="postgresql://fake",
        vision_adapter=PermanentVision(),
        feedback_adapter=feedback,
        now=datetime(2025, 11, 5, tzinfo=timezone.utc),
    )
    assert processed is True
    # Then the submission is marked failed and the job is marked failed
    assert worker_module.calls["update_failed"], "expected update_failed to be called"
    assert worker_module.calls["mark_job_failed"], "expected mark_job_failed to be called"
    # And not completed
    assert not worker_module.calls["update_completed"]
