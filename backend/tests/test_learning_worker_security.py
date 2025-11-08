"""
Security-definer functions for the learning worker must enforce pending guards.

Why:
    The worker updates submissions outside of the regular web request flow.
    We require deterministic helpers that respect RLS and only allow the worker
    to transition pending submissions to completed/failed states.
"""
from __future__ import annotations

import os
import uuid

import pytest

from datetime import datetime, timezone

from backend.learning.repo_db import DBLearningRepo
from backend.learning.usecases.submissions import CreateSubmissionInput, CreateSubmissionUseCase
from backend.tests.test_learning_api_contract import _prepare_learning_fixture  # type: ignore
from backend.tests.utils.db import require_db_or_skip as _require_db_or_skip

pytest.importorskip("psycopg")

import psycopg  # type: ignore  # noqa: E402
from psycopg.types.json import Json  # type: ignore  # noqa: E402


def _dsn() -> str:
    host = os.getenv("TEST_DB_HOST", "127.0.0.1")
    port = os.getenv("TEST_DB_PORT", "54322")
    user = os.getenv("APP_DB_USER", "gustav_app")
    password = os.getenv("APP_DB_PASSWORD", "CHANGE_ME_DEV")
    return (
        os.getenv("SERVICE_ROLE_DSN")
        or os.getenv("DATABASE_URL")
        or f"postgresql://{user}:{password}@{host}:{port}/postgres"
    )


async def _create_pending_submission(*, idempotency_key: str) -> tuple[str, str, str]:
    """Create a pending submission via the use case."""
    fixture = await _prepare_learning_fixture()
    repo = DBLearningRepo(dsn=_dsn())
    usecase = CreateSubmissionUseCase(repo)
    unique_key = f"{idempotency_key}-{uuid.uuid4()}"
    submission = usecase.execute(
        CreateSubmissionInput(
            course_id=fixture.course_id,
            task_id=fixture.task["id"],
            student_sub=fixture.student_sub,
            kind="text",
            text_body="Pending submission for security function",
            storage_key=None,
            mime_type=None,
            size_bytes=None,
            sha256=None,
            idempotency_key=unique_key,
        )
    )
    return submission["id"], fixture.student_sub, fixture.course_id


@pytest.mark.anyio
async def test_learning_worker_update_completed_sets_fields():
    """Security-definer helper should transition a pending submission to completed."""

    _require_db_or_skip()
    submission_id, student_sub, _ = await _create_pending_submission(
        idempotency_key="security-completed"
    )
    dsn = _dsn()

    analysis_payload = {
        "schema": "criteria.v2",
        "score": 4,
        "criteria_results": [],
    }

    with psycopg.connect(dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (student_sub,))
            cur.execute(
                """
                select public.learning_worker_update_completed(
                    %s::uuid,
                    %s,
                    %s,
                    %s
                )
                """,
                (
                    submission_id,
                    "## Processed Markdown",
                    "### Short feedback body",
                    Json(analysis_payload),
                ),
            )
            cur.fetchone()

            cur.execute(
                """
                select analysis_status,
                       text_body,
                       feedback_md,
                       analysis_json,
                       error_code
                  from public.learning_submissions
                 where id = %s::uuid
                """,
                (submission_id,),
            )
            status, text_body, feedback_md, analysis_json, error_code = cur.fetchone()

    assert status == "completed"
    assert text_body == "## Processed Markdown"
    assert feedback_md == "### Short feedback body"
    assert isinstance(analysis_json, dict)
    assert analysis_json["schema"] == "criteria.v2"
    assert error_code is None


@pytest.mark.anyio
async def test_learning_worker_update_failed_requires_valid_error_code():
    """Invalid error codes should raise while valid codes mark the submission as failed."""

    _require_db_or_skip()
    submission_id, student_sub, _ = await _create_pending_submission(
        idempotency_key="security-failed"
    )
    dsn = _dsn()

    with psycopg.connect(dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (student_sub,))

            with pytest.raises(psycopg.errors.RaiseException):
                cur.execute(
                    "select public.learning_worker_update_failed(%s::uuid, %s, %s)",
                    (submission_id, "invalid_code", "not allowed"),
                )
            conn.rollback()
            cur = conn.cursor()
            cur.execute("select set_config('app.current_sub', %s, true)", (student_sub,))

            cur.execute(
                "select public.learning_worker_update_failed(%s::uuid, %s, %s)",
                (submission_id, "vision_failed", "permanent failure"),
            )
            cur.fetchone()

            cur.execute(
                """
                select analysis_status,
                       error_code,
                       vision_last_error
                  from public.learning_submissions
                 where id = %s::uuid
                """,
                (submission_id,),
            )
            status, error_code, last_error = cur.fetchone()

    assert status == "failed"
    assert error_code == "vision_failed"
    assert "permanent failure" in last_error


@pytest.mark.anyio
async def test_learning_worker_mark_retry_updates_metadata():
    """Retry helper should update phase-specific metadata while keeping status pending."""

    _require_db_or_skip()
    submission_id, student_sub, _ = await _create_pending_submission(
        idempotency_key="security-retry"
    )
    dsn = _dsn()
    attempt_ts = datetime.now(tz=timezone.utc)

    with psycopg.connect(dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (student_sub,))
            cur.execute(
                """
                select public.learning_worker_mark_retry(
                    %s::uuid,
                    %s,
                    %s,
                    %s
                )
                """,
                (
                    submission_id,
                    "vision",
                    "temporary vision outage",
                    attempt_ts,
                ),
            )
            cur.fetchone()
            cur.execute(
                "select analysis_status, error_code, vision_attempts, vision_last_error from public.learning_submissions where id = %s::uuid",
                (submission_id,),
            )
            status, error_code, attempts, last_error = cur.fetchone()
            assert status == "pending"
            assert error_code == "vision_retrying"
            assert attempts == 1
            assert "temporary vision outage" in last_error

            cur.execute("select set_config('app.current_sub', %s, true)", (student_sub,))
            cur.execute(
                """
                select public.learning_worker_mark_retry(
                    %s::uuid,
                    %s,
                    %s,
                    %s
                )
                """,
                (
                    submission_id,
                    "feedback",
                    "temporary feedback issue",
                    attempt_ts,
                ),
            )
            cur.fetchone()
            cur.execute(
                """
                select analysis_status,
                       error_code,
                       feedback_last_error,
                       feedback_last_attempt_at,
                       vision_attempts
                  from public.learning_submissions
                 where id = %s::uuid
                """,
                (submission_id,),
            )
            (
                status,
                error_code,
                feedback_last_error,
                feedback_last_attempt_at,
                vision_attempts,
            ) = cur.fetchone()

    assert status == "pending"
    assert error_code == "feedback_retrying"
    assert "temporary feedback issue" in feedback_last_error
    assert feedback_last_attempt_at is not None
    assert vision_attempts == 1
