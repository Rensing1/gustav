from __future__ import annotations

from datetime import datetime, timezone
import logging
import os
from dataclasses import dataclass

import pytest

from backend.learning.workers.process_learning_submission_jobs import FeedbackResult, VisionResult, run_once
from backend.learning.repo_db import DBLearningRepo
from backend.learning.usecases.submissions import CreateSubmissionInput, CreateSubmissionUseCase
from backend.tests.utils.db import require_db_or_skip as _require_db_or_skip

pytest.importorskip("psycopg")


def _dsn() -> str:
    host = os.getenv("TEST_DB_HOST", "127.0.0.1")
    port = os.getenv("TEST_DB_PORT", "54322")
    user = os.getenv("APP_DB_USER", "gustav_app")
    password = os.getenv("APP_DB_PASSWORD", "CHANGE_ME_DEV")
    return (
        os.getenv("LEARNING_DATABASE_URL")
        or os.getenv("DATABASE_URL")
        or f"postgresql://{user}:{password}@{host}:{port}/postgres"
    )


@dataclass
class _Vision:
    text_md: str

    def extract(self, *, submission: dict, job_payload: dict) -> VisionResult:
        return VisionResult(text_md=self.text_md, raw_metadata={"adapter": "privacy-stub"})


@dataclass
class _Feedback:
    feedback_md: str

    def analyze(self, *, text_md: str, criteria):
        return FeedbackResult(
            feedback_md=self.feedback_md,
            analysis_json={"schema": "criteria.v2", "score": 3, "criteria_results": []},
        )


@pytest.mark.anyio
async def test_worker_logs_do_not_include_text_body(caplog):
    """Privacy: worker logs must not contain student text or raw bytes."""
    _require_db_or_skip()

    # Create a pending submission with memorable content.
    from backend.tests.test_learning_api_contract import _prepare_learning_fixture  # type: ignore
    fixture = await _prepare_learning_fixture()
    dsn = _dsn()
    repo = DBLearningRepo(dsn=dsn)
    usecase = CreateSubmissionUseCase(repo)
    secret_text = "SUPER-SECRET-STUDENT-CONTENT"
    submission = usecase.execute(
        CreateSubmissionInput(
            course_id=fixture.course_id,
            task_id=fixture.task["id"],
            student_sub=fixture.student_sub,
            kind="text",
            text_body=secret_text,
            storage_key=None,
            mime_type=None,
            size_bytes=None,
            sha256=None,
            idempotency_key="privacy-logs",
        )
    )

    # Enable broad capture.
    caplog.set_level(logging.DEBUG)

    # Process once.
    processed = run_once(
        dsn=os.getenv("SERVICE_ROLE_DSN") or dsn,
        vision_adapter=_Vision(text_md=secret_text),
        feedback_adapter=_Feedback(feedback_md="OK"),
        now=datetime.now(tz=timezone.utc),
    )
    assert processed is True

    # Ensure logs do not leak the secret text.
    rendered = "\n".join(r.getMessage() for r in caplog.records)
    assert secret_text not in rendered
