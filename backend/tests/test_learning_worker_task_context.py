"""
Worker should propagate task context (instruction, hints) into the job payload
and pass it through to the Feedback adapter when supported.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Sequence

import pytest

pytest.importorskip("psycopg")
import psycopg  # type: ignore  # noqa: E402

from backend.tests.utils.db import require_db_or_skip as _require_db_or_skip  # noqa: E402
from backend.learning.repo_db import DBLearningRepo  # noqa: E402
from backend.learning.usecases.submissions import (  # noqa: E402
    CreateSubmissionInput,
    CreateSubmissionUseCase,
)
from backend.learning.workers.process_learning_submission_jobs import (  # noqa: E402
    FeedbackResult,
    VisionResult,
    run_once,
)
from backend.tests.test_learning_api_contract import _prepare_learning_fixture  # type: ignore  # noqa: E402


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


@pytest.mark.anyio
async def test_job_payload_contains_instruction_and_hints():
    _require_db_or_skip()
    fixture = await _prepare_learning_fixture()
    dsn = _dsn()
    worker_dsn = os.getenv("SERVICE_ROLE_DSN") or dsn

    # Reset queue
    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute("delete from public.learning_submission_jobs")
        conn.commit()

    # Enqueue a new submission
    repo = DBLearningRepo(dsn=dsn)
    create = CreateSubmissionUseCase(repo)
    submission = create.execute(
        CreateSubmissionInput(
            course_id=fixture.course_id,
            task_id=fixture.task["id"],
            student_sub=fixture.student_sub,
            kind="text",
            text_body="Antwort",
            storage_key=None,
            mime_type=None,
            size_bytes=None,
            sha256=None,
            idempotency_key="worker-payload-context",
        )
    )
    submission_id = submission["id"]

    # Inspect job payload
    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute(
                "select payload from public.learning_submission_jobs where submission_id = %s::uuid",
                (submission_id,),
            )
            row = cur.fetchone()
            assert row is not None, "Job row missing"
            payload = row[0]
            if isinstance(payload, str):
                payload = json.loads(payload)

    assert payload.get("instruction_md") == fixture.task.get("instruction_md")
    assert payload.get("hints_md") == fixture.task.get("hints_md")


@dataclass
class _Vision:
    text: str

    def extract(self, *, submission: dict, job_payload: dict) -> VisionResult:
        return VisionResult(text_md=self.text)


class _FeedbackCapturingAdapter:
    def __init__(self) -> None:
        self.last_kwargs: dict | None = None

    def analyze(self, *, text_md: str, criteria: Sequence[str], instruction_md=None, hints_md=None) -> FeedbackResult:  # type: ignore[no-untyped-def]
        # Capture context for assertions and return a minimal valid result
        self.last_kwargs = {
            "text_md": text_md,
            "criteria": list(criteria),
            "instruction_md": instruction_md,
            "hints_md": hints_md,
        }
        return FeedbackResult(
            feedback_md="Prosa-Feedback",
            analysis_json={"schema": "criteria.v2", "score": 3, "criteria_results": []},
        )


@pytest.mark.anyio
async def test_worker_passes_task_context_to_feedback_adapter():
    _require_db_or_skip()
    fixture = await _prepare_learning_fixture()
    dsn = _dsn()
    worker_dsn = os.getenv("SERVICE_ROLE_DSN") or dsn

    # Reset queue
    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute("delete from public.learning_submission_jobs")
        conn.commit()

    # Enqueue submission
    repo = DBLearningRepo(dsn=dsn)
    create = CreateSubmissionUseCase(repo)
    submission = create.execute(
        CreateSubmissionInput(
            course_id=fixture.course_id,
            task_id=fixture.task["id"],
            student_sub=fixture.student_sub,
            kind="text",
            text_body="Antwort",
            storage_key=None,
            mime_type=None,
            size_bytes=None,
            sha256=None,
            idempotency_key="worker-pass-context",
        )
    )
    sub_id = submission["id"]

    assert _job_pending(worker_dsn=worker_dsn, submission_id=sub_id)

    captured_kwargs: dict | None = None
    for attempt in range(10):
        adapter = _FeedbackCapturingAdapter()
        processed = run_once(
            dsn=worker_dsn,
            vision_adapter=_Vision(text="Text"),
            feedback_adapter=adapter,
            now=datetime.now(tz=timezone.utc),
        )
        assert processed is True
        if not _job_pending(worker_dsn=worker_dsn, submission_id=sub_id):
            captured_kwargs = adapter.last_kwargs
            break

    assert captured_kwargs is not None, "Worker did not process the targeted submission"
    assert captured_kwargs.get("instruction_md") == fixture.task.get("instruction_md")
    assert captured_kwargs.get("hints_md") == fixture.task.get("hints_md")
def _job_pending(*, worker_dsn: str, submission_id: str) -> bool:
    """Return True when a queue entry for the submission still exists."""
    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute(
                "select 1 from public.learning_submission_jobs where submission_id = %s::uuid limit 1",
                (submission_id,),
            )
            return cur.fetchone() is not None

