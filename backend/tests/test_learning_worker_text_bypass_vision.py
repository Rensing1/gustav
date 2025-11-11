"""
Worker should bypass Vision for text submissions and never mutate text.

Expectations:
- For `kind='text'` the worker must not call the Vision adapter at all.
- The feedback adapter still runs and the job is completed.
"""

from __future__ import annotations

import os
import pytest

pytest.importorskip("psycopg")
import psycopg  # type: ignore

from backend.learning.repo_db import DBLearningRepo  # type: ignore
from backend.learning.usecases import CreateSubmissionInput, CreateSubmissionUseCase  # type: ignore
from backend.tests.test_learning_api_contract import _prepare_learning_fixture  # type: ignore
from backend.tests.test_learning_worker_jobs import _dsn  # type: ignore
from backend.learning.workers.process_learning_submission_jobs import FeedbackResult, run_once  # type: ignore
from datetime import datetime, timezone
from uuid import uuid4


class _ExplodingVisionAdapter:
    def __init__(self):
        self.called = False

    def extract(self, *, submission: dict, job_payload: dict):  # pragma: no cover - must not be called
        self.called = True
        raise AssertionError("Vision adapter must not be called for text submissions")


class _StubFeedbackAdapter:
    def __init__(self):
        self.called = False

    def analyze(self, *, text_md: str, criteria: list[str]) -> FeedbackResult:
        self.called = True
        # Return minimal valid payload
        return FeedbackResult(feedback_md="OK", analysis_json={"schema": "criteria.v2", "criteria_results": []})


@pytest.mark.anyio
async def test_worker_bypasses_vision_for_text_and_preserves_text(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange DB fixture and create a text submission
    fixture = await _prepare_learning_fixture()
    dsn = _dsn()
    # Ensure worker and app use the same DSN (avoid cross-DB drift)
    monkeypatch.setenv("SERVICE_ROLE_DSN", dsn)
    worker_dsn = os.getenv("SERVICE_ROLE_DSN") or dsn
    # Keep queue deterministic for this test: remove any leftover jobs
    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute("delete from public.learning_submission_jobs")
        conn.commit()
    repo = DBLearningRepo(dsn=dsn)
    usecase = CreateSubmissionUseCase(repo)
    submission = usecase.execute(
            CreateSubmissionInput(
                course_id=fixture.course_id,
                task_id=fixture.task["id"],
                student_sub=fixture.student_sub,
                kind="text",
                text_body="Ich weiß es leider nicht",
                storage_key=None,
                mime_type=None,
                size_bytes=None,
                sha256=None,
                # Use a unique key per test run to avoid colliding with prior state
                idempotency_key=f"bypass-vision-text-{uuid4()}",
            )
        )

    # Act: run the worker once with a Vision adapter that fails if called
    exploding = _ExplodingVisionAdapter()
    feedback = _StubFeedbackAdapter()
    processed = run_once(
        dsn=worker_dsn,
        vision_adapter=exploding,
        feedback_adapter=feedback,
        now=datetime.now(tz=timezone.utc),
    )

    # Assert: job processed, vision not called, feedback called
    assert processed is True
    assert exploding.called is False
    assert feedback.called is True
