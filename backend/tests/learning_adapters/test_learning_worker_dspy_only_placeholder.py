"""
Placeholder test module for future worker + DB DSPy-only integration tests.

Intent:
    This file is added as a planning marker for the next TDD step once the
    DSPy-only feedback adapter behaviour is implemented. It deliberately
    contains no executable tests yet, to avoid coupling worker behaviour to
    a pipeline that is still under refactoring.

Next steps:
    - Add integration tests that verify `learning_submissions` rows are
      updated with `criteria.v2` analysis_json and DSPy-generated feedback_md
      without any legacy LM calls.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest

pytest.importorskip("psycopg")
import psycopg  # type: ignore

from backend.learning.workers.process_learning_submission_jobs import (  # type: ignore
    FeedbackResult,
    VisionAdapterProtocol,
    VisionResult,
    run_once,
)
from backend.learning.repo_db import DBLearningRepo  # type: ignore
from backend.learning.usecases import CreateSubmissionInput, CreateSubmissionUseCase  # type: ignore
from backend.tests.test_learning_api_contract import _prepare_learning_fixture  # type: ignore
from backend.tests.test_learning_worker_jobs import _dsn  # type: ignore


class _ExplodingVisionAdapter(VisionAdapterProtocol):
    """Ensures the worker bypasses Vision for text submissions."""

    def __init__(self):
        self.called = False

    def extract(self, *, submission: dict, job_payload: dict) -> VisionResult:  # pragma: no cover - must not be called
        self.called = True
        raise AssertionError("Vision must not be called for text submissions")


class _StubFeedbackAdapter:
    """Simulates a DSPy-backed feedback adapter returning criteria.v2."""

    def __init__(self):
        self.called = False

    def analyze(self, *, text_md: str, criteria: list[str]) -> FeedbackResult:
        self.called = True
        return FeedbackResult(
            feedback_md="DSPy Feedback",
            analysis_json={"schema": "criteria.v2", "score": 3, "criteria_results": []},
            parse_status="parsed_structured",
        )


@pytest.mark.anyio
async def test_worker_persists_dspy_feedback_without_legacy_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Worker should persist criteria.v2 + feedback_md when feedback adapter succeeds (DSPy path).
    """

    fixture = await _prepare_learning_fixture()
    dsn = _dsn()
    monkeypatch.setenv("SERVICE_ROLE_DSN", dsn)

    # Clean queue for determinism.
    with psycopg.connect(dsn) as conn:  # type: ignore[arg-type]
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
            text_body="Kurzer Text",
            storage_key=None,
            mime_type=None,
            size_bytes=None,
            sha256=None,
            idempotency_key=f"dspy-worker-integration-{os.urandom(4).hex()}",
        )
    )

    vision = _ExplodingVisionAdapter()
    feedback = _StubFeedbackAdapter()

    processed = run_once(
        dsn=os.getenv("SERVICE_ROLE_DSN") or dsn,
        vision_adapter=vision,
        feedback_adapter=feedback,
        now=datetime.now(tz=timezone.utc),
    )

    assert processed is True
    assert vision.called is False
    assert feedback.called is True

    # Verify persistence on the submission row
    with psycopg.connect(dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute(
                "select feedback_md, analysis_json from public.learning_submissions where id = %s",
                (submission["id"],),
            )
            row = cur.fetchone()
    assert row is not None
    feedback_md, analysis_json = row
    assert feedback_md == "DSPy Feedback"
    assert isinstance(analysis_json, dict)
    assert analysis_json.get("schema") == "criteria.v2"
    assert analysis_json.get("score") == 3
