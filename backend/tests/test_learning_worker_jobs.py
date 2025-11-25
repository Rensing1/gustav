"""
Worker integration tests for the learning submission pipeline.

Why:
    Ensure the worker service processes queued submissions end-to-end:
    leasing a job, invoking Vision/Feedback adapters, and persisting
    the completed status back into Postgres while removing the job.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import logging
import os
import uuid
from typing import Sequence

import pytest

from backend.learning.repo_db import DBLearningRepo
from backend.learning.usecases.submissions import CreateSubmissionInput, CreateSubmissionUseCase
from backend.tests.utils.db import require_db_or_skip as _require_db_or_skip

pytest.importorskip("psycopg")

try:
    _require_db_or_skip()
except pytest.skip.Exception as exc:  # pragma: no cover - module level skip
    pytest.skip(str(exc), allow_module_level=True)

import psycopg  # type: ignore  # noqa: E402

from backend.tests.test_learning_api_contract import _prepare_learning_fixture  # type: ignore
from backend.learning.workers import process_learning_submission_jobs as worker_module  # noqa: E402  # type: ignore
from backend.learning.workers.process_learning_submission_jobs import (  # noqa: E402  # type: ignore
    FeedbackResult,
    VisionResult,
    run_once,
)
from backend.learning.workers import telemetry  # noqa: E402  # type: ignore


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
class _StubVisionAdapter:
    text_md: str

    def extract(self, *, submission: dict, job_payload: dict) -> VisionResult:
        """Return deterministic Markdown for the worker to persist."""
        return VisionResult(text_md=self.text_md, raw_metadata={"source": "stub"})


@dataclass
class _StubFeedbackAdapter:
    feedback_md: str
    base_score: int = 4

    def analyze(self, *, text_md: str, criteria: Sequence[str]) -> FeedbackResult:
        """Return deterministic feedback+analysis shaped like criteria.v2."""
        results = []
        for index, criterion in enumerate(criteria):
            results.append(
                {
                    "criterion": criterion,
                    "score": min(10, self.base_score + index),
                    "max_score": 10,
                    "explanation_md": f"Stub feedback for {criterion}",
                }
            )
        return FeedbackResult(
            feedback_md=self.feedback_md,
            analysis_json={
                "schema": "criteria.v2",
                "score": self.base_score,
                "criteria_results": results,
            },
        )


class _TransientVisionAdapter:
    """Raise a transient vision error to exercise the retry path."""

    def __init__(self, message: str = "temporary vision glitch"):
        self.calls = 0
        self.message = message

    def extract(self, *, submission: dict, job_payload: dict) -> VisionResult:
        self.calls += 1
        raise worker_module.VisionTransientError(self.message)  # type: ignore[attr-defined]


class _PermanentVisionAdapter:
    """Always raise a transient error to exhaust retries quickly."""

    def __init__(self, message: str = "permanent vision failure"):
        self.calls = 0
        self.message = message

    def extract(self, *, submission: dict, job_payload: dict) -> VisionResult:
        self.calls += 1
        raise worker_module.VisionTransientError(self.message)  # type: ignore[attr-defined]


class _TransientFeedbackAdapter:
    """Raise a transient feedback error to exercise feedback retry bookkeeping."""

    def __init__(self, message: str = "temporary feedback issue"):
        self.calls = 0
        self.message = message

    def analyze(self, *, text_md: str, criteria: Sequence[str]) -> FeedbackResult:
        self.calls += 1
        raise worker_module.FeedbackTransientError(self.message)  # type: ignore[attr-defined]


class _PermanentFeedbackAdapter:
    """Raise a permanent feedback error to ensure the worker records failures."""

    def __init__(self, message: str = "permanent feedback failure"):
        self.calls = 0
        self.message = message

    def analyze(self, *, text_md: str, criteria: Sequence[str]) -> FeedbackResult:
        self.calls += 1
        raise worker_module.FeedbackPermanentError(self.message)  # type: ignore[attr-defined]


class _CountingVisionAdapter:
    """Vision adapter that records invocations for OCR-reuse tests."""

    def __init__(self) -> None:
        self.calls = 0

    def extract(self, *, submission: dict, job_payload: dict) -> VisionResult:
        self.calls += 1
        return VisionResult(
            text_md="## Counting Vision\n\nShould be bypassed when cache is present.",
            raw_metadata={"source": "counting_adapter"},
        )


async def _prepare_submission_with_job(*, idempotency_key: str) -> tuple[dict, str, str, str]:
    """Create a pending submission and return (fixture, worker_dsn, job_id, submission_id)."""
    fixture = await _prepare_learning_fixture()
    dsn = _dsn()
    worker_dsn = os.getenv("SERVICE_ROLE_DSN") or dsn

    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute("delete from public.learning_submission_jobs")
        conn.commit()

    # Ensure membership exists (some suite orders may skip API add_member on errors)
    try:
        with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into public.course_memberships (course_id, student_id, role)
                    select %s::uuid, %s, 'student'
                    where not exists (
                        select 1 from public.course_memberships
                         where course_id = %s::uuid and student_id = %s
                    )
                    """,
                    (fixture.course_id, fixture.student_sub, fixture.course_id, fixture.student_sub),
                )
            conn.commit()
    except Exception:
        # Best-effort hardening; tests relying on API path still validate main behaviour
        pass

    repo = DBLearningRepo(dsn=dsn)
    usecase = CreateSubmissionUseCase(repo)
    submission = usecase.execute(
        CreateSubmissionInput(
            course_id=fixture.course_id,
            task_id=fixture.task["id"],
            student_sub=fixture.student_sub,
            kind="text",
            text_body="Pending answer for retry path",
            storage_key=None,
            mime_type=None,
            size_bytes=None,
            sha256=None,
            idempotency_key=idempotency_key,
        )
    )
    submission_id = submission["id"]

    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute(
                """
                select id::text
                  from public.learning_submission_jobs
                 where submission_id = %s::uuid
                 order by created_at desc
                """,
                (submission_id,),
            )
            row = cur.fetchone()
            if not row:
                # Fallback: insert a queued job deterministically for this submission.
                cur.execute(
                    """
                    insert into public.learning_submission_jobs (submission_id, payload, visible_at, status, retry_count)
                    values (%s::uuid, %s::jsonb, now(), 'queued', 0)
                    returning id::text
                    """,
                    (submission_id, {"student_sub": fixture.student_sub, "criteria": []}),
                )
                job_id = cur.fetchone()[0]
            else:
                job_id = row[0]
    return fixture, worker_dsn, job_id, submission_id


def _set_job_visibility(worker_dsn: str, job_id: str, *, visible_at: datetime) -> None:
    """Pin a job's visibility for deterministic leasing, clearing any previous lease."""
    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute(
                """
                update public.learning_submission_jobs
                   set visible_at = %s,
                       status = 'queued',
                       lease_key = null,
                       leased_until = null,
                       updated_at = now()
                 where id = %s::uuid
                """,
                (visible_at, job_id),
            )
        conn.commit()


def _force_submission_to_file(worker_dsn: str, submission_id: str) -> None:
    """Switch the stored submission to a non-text kind so Vision adapters run."""
    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute(
                """
                update public.learning_submissions
                   set kind = 'image',
                       mime_type = 'image/png',
                       text_body = null,
                       storage_key = coalesce(storage_key, 'learning/test.png'),
                       size_bytes = coalesce(size_bytes, 1),
                       sha256 = coalesce(sha256, repeat('0', 64))
                 where id = %s::uuid
                """,
                (submission_id,),
            )
        conn.commit()


def _counter_value(name: str, **labels: str) -> int:
    snapshot = telemetry.counter_snapshot(name)
    key = tuple(sorted(labels.items()))
    return snapshot.get(key, 0)


def _gauge_value(name: str, **labels: str) -> float:
    snapshot = telemetry.gauge_snapshot(name)
    key = tuple(sorted(labels.items()))
    return snapshot.get(key, 0.0)


@pytest.mark.anyio
async def test_worker_processes_pending_submission_to_completed():
    """Worker should mark a queued submission as completed and clear the job."""

    _require_db_or_skip()
    fixture = await _prepare_learning_fixture()
    dsn = _dsn()
    worker_dsn = os.getenv("SERVICE_ROLE_DSN") or dsn

    # Ensure a clean queue so the worker leases the job created in this test.
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
            text_body="Schülerantwort pending",
            storage_key=None,
            mime_type=None,
            size_bytes=None,
            sha256=None,
            idempotency_key="worker-happy-path",
        )
    )
    submission_id = submission["id"]
    # Ensure the submission row exists in the learning repo.
    history = repo.list_submissions(
        student_sub=fixture.student_sub,
        course_id=fixture.course_id,
        task_id=fixture.task["id"],
        limit=5,
        offset=0,
    )
    assert any(entry["id"] == submission_id for entry in history)

    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute(
                """
                select id::text
                  from public.learning_submission_jobs
                 where submission_id = %s::uuid
                 order by created_at desc
                """,
                (submission_id,),
            )
            job_row = cur.fetchone()
            if not job_row:
                pytest.fail("Submission did not enqueue a learning_submission_job")
            job_id = job_row[0]

    _force_submission_to_file(worker_dsn, submission_id)

    processed = run_once(
        dsn=worker_dsn,
        vision_adapter=_StubVisionAdapter(text_md="## Vision Extract\n\nStub content."),
        feedback_adapter=_StubFeedbackAdapter(feedback_md="### Feedback\n\n- Gut gemacht."),
        now=datetime.now(tz=timezone.utc),
    )

    assert processed is True

    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            try:
                cur.execute(
                    """
                    select analysis_status,
                           text_body,
                           analysis_json,
                           feedback_md,
                           vision_attempts,
                           vision_last_error
                      from public.learning_submissions
                     where id = %s::uuid
                    """,
                    (submission_id,),
                )
            except psycopg.errors.UndefinedColumn:  # type: ignore[attr-defined]
                cur.execute(
                    """
                    select analysis_status,
                           text_body,
                           analysis_json,
                           feedback_md,
                           ocr_attempts,
                           ocr_last_error
                      from public.learning_submissions
                     where id = %s::uuid
                    """,
                    (submission_id,),
                )
            row = cur.fetchone()
            assert row is not None
            analysis_status, text_body, analysis_json, feedback_md, attempts, last_error = row

            cur.execute(
                "select count(*) from public.learning_submission_jobs where id = %s::uuid", (job_id,)
            )
            remaining_jobs = int(cur.fetchone()[0])

    assert analysis_status == "completed"
    assert text_body == "## Vision Extract\n\nStub content."
    assert attempts == 1
    assert last_error is None
    assert remaining_jobs == 0

    assert isinstance(analysis_json, dict)
    assert analysis_json["schema"] == "criteria.v2"
    assert analysis_json["score"] == _StubFeedbackAdapter.base_score


@pytest.mark.anyio
async def test_worker_retries_vision_transient_error(monkeypatch):
    """Transient vision errors should requeue the job with backoff and keep submission pending."""

    _require_db_or_skip()
    _, worker_dsn, job_id, submission_id = await _prepare_submission_with_job(
        idempotency_key="worker-retry-path"
    )

    _force_submission_to_file(worker_dsn, submission_id)

    # Deterministic configuration for retries.
    monkeypatch.setenv("WORKER_BACKOFF_SECONDS", "2")
    worker_module.MAX_RETRIES = 3  # type: ignore[attr-defined]
    tick = datetime.now(tz=timezone.utc) + timedelta(hours=1)
    _set_job_visibility(worker_dsn, job_id, visible_at=tick)

    processed = run_once(
        dsn=worker_dsn,
        vision_adapter=_TransientVisionAdapter(),
        feedback_adapter=_StubFeedbackAdapter(feedback_md="unused"),
        now=tick,
    )

    assert processed is True

    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute(
                """
                select status,
                       retry_count,
                       visible_at,
                       error_code
                  from public.learning_submission_jobs
                 where id = %s::uuid
                """,
                (job_id,),
            )
            status, retry_count, visible_at, error_code = cur.fetchone()

            cur.execute(
                """
                select analysis_status,
                       error_code,
                       vision_attempts,
                       vision_last_error,
                       vision_last_attempt_at
                  from public.learning_submissions
                 where id = %s::uuid
                """,
                (submission_id,),
            )
            (
                submission_status,
                submission_error,
                vision_attempts,
                vision_last_error,
                last_attempt_at,
            ) = cur.fetchone()

    assert status == "queued"
    assert retry_count == 1
    assert error_code is None
    assert visible_at.tzinfo is not None
    assert visible_at >= tick + timedelta(seconds=2)

    assert submission_status == "pending"
    assert submission_error == "vision_retrying"
    assert vision_attempts == 1
    assert vision_last_error is not None
    assert "temporary vision glitch" in vision_last_error
    assert last_attempt_at is not None


@pytest.mark.anyio
async def test_worker_marks_failed_after_max_retries(monkeypatch):
    """After exhausting retries the worker should mark the submission as failed and keep the job for auditing."""

    _require_db_or_skip()
    _, worker_dsn, job_id, submission_id = await _prepare_submission_with_job(
        idempotency_key="worker-fail-path"
    )

    _force_submission_to_file(worker_dsn, submission_id)

    monkeypatch.setenv("WORKER_BACKOFF_SECONDS", "1")
    worker_module.MAX_RETRIES = 1  # type: ignore[attr-defined]

    tick = datetime.now(tz=timezone.utc) + timedelta(hours=1)
    _set_job_visibility(worker_dsn, job_id, visible_at=tick)
    run_once(
        dsn=worker_dsn,
        vision_adapter=_PermanentVisionAdapter(),
        feedback_adapter=_StubFeedbackAdapter(feedback_md="unused"),
        now=tick,
    )

    # Use a slightly larger offset than the nominal backoff to avoid
    # flakiness on slower CI/DB clocks. With WORKER_BACKOFF_SECONDS=1 and
    # first retry_count=0, visible_at = now + 1s; we wait 3s.
    second_tick = tick + timedelta(seconds=3)
    processed = run_once(
        dsn=worker_dsn,
        vision_adapter=_PermanentVisionAdapter(),
        feedback_adapter=_StubFeedbackAdapter(feedback_md="unused"),
        now=second_tick,
    )

    assert processed is True

    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute(
                """
                select status,
                       retry_count,
                       error_code
                  from public.learning_submission_jobs
                 where id = %s::uuid
                """,
                (job_id,),
            )
            status, retry_count, job_error = cur.fetchone()

            cur.execute(
                """
                select analysis_status,
                       error_code,
                       vision_attempts,
                       vision_last_error
                  from public.learning_submissions
                 where id = %s::uuid
                """,
                (submission_id,),
            )
            submission_status, submission_error, vision_attempts, vision_last_error = cur.fetchone()

    assert status == "failed"
    assert retry_count == 1
    assert job_error == "vision_failed"

    assert submission_status == "failed"
    assert submission_error == "vision_failed"
    assert vision_attempts == 2
    assert vision_last_error is not None
    assert "permanent vision failure" in vision_last_error


@pytest.mark.anyio
async def test_worker_retries_feedback_transient_error(monkeypatch):
    """Transient feedback errors should keep submission pending and record retry metadata."""

    _require_db_or_skip()
    _fixture, worker_dsn, job_id, submission_id = await _prepare_submission_with_job(
        idempotency_key="worker-feedback-retry"
    )

    monkeypatch.setenv("WORKER_BACKOFF_SECONDS", "3")
    worker_module.MAX_RETRIES = 3  # type: ignore[attr-defined]
    tick = datetime.now(tz=timezone.utc) + timedelta(hours=1)
    _set_job_visibility(worker_dsn, job_id, visible_at=tick)

    processed = run_once(
        dsn=worker_dsn,
        vision_adapter=_StubVisionAdapter(text_md="## Student answer\n\nContent."),
        feedback_adapter=_TransientFeedbackAdapter(),
        now=tick,
    )

    assert processed is True

    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute(
                """
                select status,
                       retry_count,
                       visible_at
                  from public.learning_submission_jobs
                 where id = %s::uuid
                """,
                (job_id,),
            )
            status, retry_count, visible_at = cur.fetchone()

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
                submission_status,
                submission_error,
                feedback_last_error,
                feedback_last_attempt_at,
                vision_attempts,
            ) = cur.fetchone()

    assert status == "queued"
    assert retry_count == 1
    assert visible_at.tzinfo is not None
    assert visible_at >= tick + timedelta(seconds=3)

    assert submission_status == "pending"
    assert submission_error == "feedback_retrying"
    assert feedback_last_error is not None
    assert "temporary feedback issue" in feedback_last_error
    assert feedback_last_attempt_at is not None
    assert vision_attempts == 0


@pytest.mark.anyio
async def test_worker_marks_feedback_failure_records_job_error(monkeypatch: pytest.MonkeyPatch):
    """Permanent feedback failures should persist error_code for audit trail."""

    _require_db_or_skip()
    # Ensure worker and app talk to the same database for this test
    monkeypatch.setenv("SERVICE_ROLE_DSN", _dsn())
    fixture, worker_dsn, job_id, submission_id = await _prepare_submission_with_job(
        idempotency_key="worker-feedback-fail"
    )

    tick = datetime.now(tz=timezone.utc)
    processed = run_once(
        dsn=worker_dsn,
        vision_adapter=_StubVisionAdapter(text_md="## Answer\n\nContent."),
        feedback_adapter=_PermanentFeedbackAdapter(),
        now=tick,
    )

    assert processed is True

    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute(
                """
                select status,
                       retry_count,
                       error_code
                  from public.learning_submission_jobs
                 where id = %s::uuid
                """,
                (job_id,),
            )
            status, retry_count, job_error_code = cur.fetchone()

            cur.execute(
                "select set_config('app.current_sub', %s, true)",
                (fixture.student_sub,),
            )
            cur.execute(
                """
                select analysis_status,
                       error_code,
                       feedback_last_error
                  from public.learning_submissions
                 where id = %s::uuid
                """,
                (submission_id,),
            )
            submission_status, submission_error, feedback_last_error = cur.fetchone()

    assert status == "failed"
    assert retry_count == 0
    assert job_error_code == "feedback_failed"

    assert submission_status == "failed"
    assert submission_error == "feedback_failed"
    assert feedback_last_error is not None
    assert "permanent feedback failure" in feedback_last_error


@pytest.mark.anyio
async def test_worker_success_updates_metrics_and_gauge():
    """Successful runs should increment processed counter and leave inflight gauge at zero."""

    _require_db_or_skip()
    telemetry.reset_for_tests()
    _fixture, worker_dsn, job_id, submission_id = await _prepare_submission_with_job(
        idempotency_key="worker-metrics-success"
    )

    tick = datetime.now(tz=timezone.utc) + timedelta(hours=1)
    _set_job_visibility(worker_dsn, job_id, visible_at=tick)
    processed = run_once(
        dsn=worker_dsn,
        vision_adapter=_StubVisionAdapter(text_md="# Metrics Success"),
        feedback_adapter=_StubFeedbackAdapter(feedback_md="Well done"),
        now=tick,
    )

    assert processed is True
    assert _counter_value("ai_worker_processed_total", status="completed") == 1
    assert _gauge_value("analysis_jobs_inflight") == 0.0


@pytest.mark.anyio
async def test_worker_retry_emits_retry_metric_and_warning(caplog: pytest.LogCaptureFixture):
    """Transient vision errors should bump retry metrics and emit structured warnings."""

    _require_db_or_skip()
    telemetry.reset_for_tests()
    _fixture, worker_dsn, job_id, submission_id = await _prepare_submission_with_job(
        idempotency_key="worker-metrics-retry"
    )
    _force_submission_to_file(worker_dsn, submission_id)

    caplog.set_level(logging.INFO, logger=worker_module.LOG.name)
    tick = datetime.now(tz=timezone.utc) + timedelta(hours=1)
    _set_job_visibility(worker_dsn, job_id, visible_at=tick)
    processed = run_once(
        dsn=worker_dsn,
        vision_adapter=_TransientVisionAdapter(message="temporary retry"),
        feedback_adapter=_StubFeedbackAdapter(feedback_md="unused"),
        now=tick,
    )

    assert processed is True
    assert _counter_value("ai_worker_retry_total", phase="vision") == 1
    assert _gauge_value("analysis_jobs_inflight") == 0.0

    warnings = [rec for rec in caplog.records if rec.levelname in ("WARNING", "INFO")]
    assert any("temporary retry" in rec.getMessage() and "next_visible_at" in rec.getMessage() for rec in warnings)


@pytest.mark.anyio
async def test_worker_concurrency_leases_multiple_jobs(monkeypatch: pytest.MonkeyPatch):
    """Worker should lease and process up to WORKER_CONCURRENCY jobs in one tick."""

    _require_db_or_skip()
    telemetry.reset_for_tests()
    monkeypatch.setenv("WORKER_CONCURRENCY", "2")

    worker_dsn = os.getenv("SERVICE_ROLE_DSN") or _dsn()
    teacher_sub = f"teacher-{uuid.uuid4()}"
    student_sub = f"student-{uuid.uuid4()}"

    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute("delete from public.learning_submission_jobs")

            cur.execute("select set_config('app.current_sub', %s, false)", (teacher_sub,))
            cur.execute(
                "insert into public.courses (title, teacher_id) values (%s, %s) returning id",
                ("Concurrency Course", teacher_sub),
            )
            course_id = cur.fetchone()[0]
            cur.execute(
                "insert into public.units (title, author_id) values (%s, %s) returning id",
                ("Concurrency Unit", teacher_sub),
            )
            unit_id = cur.fetchone()[0]
            cur.execute(
                "insert into public.unit_sections (unit_id, title, position) values (%s, %s, %s) returning id",
                (unit_id, "Section", 1),
            )
            section_id = cur.fetchone()[0]
            cur.execute(
                """
                insert into public.unit_tasks (unit_id, section_id, instruction_md, criteria, position)
                values (%s, %s, %s, %s::text[], %s) returning id
                """,
                (unit_id, section_id, "Beschreibe den Graphen", ["Kriterium A"], 1),
            )
            task_id = cur.fetchone()[0]

            submission_ids: list[str] = []
            payloads: list[dict] = []
            for idx in range(2):
                submission_id = str(uuid.uuid4())
                submission_ids.append(submission_id)
                attempt_nr = idx + 1
                cur.execute(
                    """
                    insert into public.learning_submissions (
                        id, course_id, task_id, student_sub, kind,
                        text_body, storage_key, mime_type, size_bytes, sha256,
                        attempt_nr, analysis_status, analysis_json
                    ) values (
                        %s::uuid, %s::uuid, %s::uuid, %s, 'text',
                        %s, null, null, null, null,
                        %s, 'pending', null
                    )
                    """,
                    (
                        submission_id,
                        course_id,
                        task_id,
                        student_sub,
                        f"Text answer {idx}",
                        attempt_nr,
                    ),
                )
                payload = {
                    "submission_id": submission_id,
                    "course_id": str(course_id),
                    "task_id": str(task_id),
                    "student_sub": student_sub,
                    "kind": "text",
                    "attempt_nr": attempt_nr,
                    "criteria": ["Kriterium A"],
                }
                payloads.append(payload)
                cur.execute(
                    "insert into public.learning_submission_jobs (submission_id, payload) values (%s::uuid, %s::jsonb)",
                    (submission_id, json.dumps(payload)),
                )
        conn.commit()

    processed = run_once(
        dsn=worker_dsn,
        vision_adapter=_StubVisionAdapter(text_md="## Vision Extract\n\nContent."),
        feedback_adapter=_StubFeedbackAdapter(feedback_md="Feedback"),
        now=datetime.now(tz=timezone.utc),
    )

    assert processed is True

    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute("select count(*) from public.learning_submission_jobs")
            remaining_jobs = int(cur.fetchone()[0])
            cur.execute(
                """
                select analysis_status, text_body from public.learning_submissions
                where id = any(%s::uuid[])
                """,
                (submission_ids,),
            )
            rows = cur.fetchall()

    assert remaining_jobs == 0
    assert {row[0] for row in rows} == {"completed"}
    assert _gauge_value("analysis_jobs_inflight") == 0.0


@pytest.mark.anyio
async def test_worker_feedback_retry_uses_cached_ocr(monkeypatch: pytest.MonkeyPatch):
    """When OCR text is cached in the job, Vision should not run again."""

    _require_db_or_skip()
    telemetry.reset_for_tests()
    worker_dsn = os.getenv("SERVICE_ROLE_DSN") or _dsn()

    teacher_sub = f"teacher-{uuid.uuid4()}"
    student_sub = f"student-{uuid.uuid4()}"
    cached_text = "## Cached OCR\n\nLine A\nLine B"

    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute("delete from public.learning_submission_jobs")
            cur.execute("select set_config('app.current_sub', %s, false)", (teacher_sub,))
            cur.execute(
                "insert into public.courses (title, teacher_id) values (%s, %s) returning id",
                ("OCR Reuse Course", teacher_sub),
            )
            course_id = cur.fetchone()[0]
            cur.execute(
                "insert into public.units (title, author_id) values (%s, %s) returning id",
                ("Unit", teacher_sub),
            )
            unit_id = cur.fetchone()[0]
            cur.execute(
                "insert into public.unit_sections (unit_id, title, position) values (%s, %s, %s) returning id",
                (unit_id, "Section", 1),
            )
            section_id = cur.fetchone()[0]
            cur.execute(
                """
                insert into public.unit_tasks (unit_id, section_id, instruction_md, criteria, position)
                values (%s, %s, %s, %s::text[], %s) returning id
                """,
                (unit_id, section_id, "Beschreibe den Graphen", ["Kriterium A"], 1),
            )
            task_id = cur.fetchone()[0]

            submission_id = str(uuid.uuid4())
            cur.execute(
                """
                insert into public.learning_submissions (
                    id, course_id, task_id, student_sub, kind,
                    text_body, storage_key, mime_type, size_bytes, sha256,
                    attempt_nr, analysis_status, analysis_json
                ) values (
                    %s::uuid, %s::uuid, %s::uuid, %s, 'file',
                    null, 'dummy/storage', 'application/pdf', 1024, %s,
                    1, 'extracted', null
                )
                """,
                (submission_id, course_id, task_id, student_sub, "0" * 64),
            )
            payload = {
                "submission_id": submission_id,
                "course_id": str(course_id),
                "task_id": str(task_id),
                "student_sub": student_sub,
                "kind": "file",
                "attempt_nr": 1,
                "criteria": ["Kriterium A"],
                "cached_text_md": cached_text,
            }
            cur.execute(
                "insert into public.learning_submission_jobs (submission_id, payload) values (%s::uuid, %s::jsonb)",
                (submission_id, json.dumps(payload)),
            )
        conn.commit()

    counting_vision = _CountingVisionAdapter()
    processed = run_once(
        dsn=worker_dsn,
        vision_adapter=counting_vision,
        feedback_adapter=_StubFeedbackAdapter(feedback_md="Feedback"),
        now=datetime.now(tz=timezone.utc),
    )

    assert processed is True
    assert counting_vision.calls == 0

    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute("select count(*) from public.learning_submission_jobs")
            remaining_jobs = int(cur.fetchone()[0])
            cur.execute(
                """
                select analysis_status, text_body from public.learning_submissions
                where id = %s::uuid
                """,
                (submission_id,),
            )
            status, text_body = cur.fetchone()

    assert remaining_jobs == 0
    assert status == "completed"
    assert isinstance(text_body, str) and "Cached OCR" in text_body
    assert _gauge_value("analysis_jobs_inflight") == 0.0


@pytest.mark.anyio
async def test_worker_releases_job_when_processing_crashes(monkeypatch: pytest.MonkeyPatch):
    """If processing raises, the job should not remain leased indefinitely."""

    _require_db_or_skip()
    telemetry.reset_for_tests()
    monkeypatch.setenv("WORKER_CONCURRENCY", "1")
    monkeypatch.setenv("WORKER_LEASE_SECONDS", "60")

    worker_dsn = os.getenv("SERVICE_ROLE_DSN") or _dsn()
    teacher_sub = f"teacher-{uuid.uuid4()}"
    student_sub = f"student-{uuid.uuid4()}"

    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute("delete from public.learning_submission_jobs")
            cur.execute("select set_config('app.current_sub', %s, false)", (teacher_sub,))
            cur.execute(
                "insert into public.courses (title, teacher_id) values (%s, %s) returning id",
                ("Crash Course", teacher_sub),
            )
            course_id = cur.fetchone()[0]
            cur.execute(
                "insert into public.units (title, author_id) values (%s, %s) returning id",
                ("Unit", teacher_sub),
            )
            unit_id = cur.fetchone()[0]
            cur.execute(
                "insert into public.unit_sections (unit_id, title, position) values (%s, %s, %s) returning id",
                (unit_id, "Section", 1),
            )
            section_id = cur.fetchone()[0]
            cur.execute(
                """
                insert into public.unit_tasks (unit_id, section_id, instruction_md, criteria, position)
                values (%s, %s, %s, %s::text[], %s) returning id
                """,
                (unit_id, section_id, "Beschreibe den Graphen", ["Kriterium A"], 1),
            )
            task_id = cur.fetchone()[0]

            submission_id = str(uuid.uuid4())
            cur.execute(
                """
                insert into public.learning_submissions (
                    id, course_id, task_id, student_sub, kind,
                    text_body, storage_key, mime_type, size_bytes, sha256,
                    attempt_nr, analysis_status, analysis_json
                ) values (
                    %s::uuid, %s::uuid, %s::uuid, %s, 'text',
                    %s, null, null, null, null,
                    1, 'pending', null
                )
                """,
                (
                    submission_id,
                    course_id,
                    task_id,
                    student_sub,
                    "Crash submission",
                ),
            )
            payload = {
                "submission_id": submission_id,
                "course_id": str(course_id),
                "task_id": str(task_id),
                "student_sub": student_sub,
                "kind": "text",
                "attempt_nr": 1,
                "criteria": ["Kriterium A"],
            }
            cur.execute(
                "insert into public.learning_submission_jobs (submission_id, payload) values (%s::uuid, %s::jsonb)",
                (submission_id, json.dumps(payload)),
            )
        conn.commit()

    def _boom(**kwargs):
        raise RuntimeError("processing crashed")

    monkeypatch.setattr(worker_module, "_process_job", _boom)

    with pytest.raises(RuntimeError):
        run_once(
            dsn=worker_dsn,
            vision_adapter=_StubVisionAdapter(text_md="# boom"),
            feedback_adapter=_StubFeedbackAdapter(feedback_md="unused"),
            now=datetime.now(tz=timezone.utc),
        )

    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute(
                """
                select status, lease_key, leased_until
                  from public.learning_submission_jobs
                 where submission_id = %s::uuid
                """,
                (submission_id,),
            )
            status, lease_key, leased_until = cur.fetchone()

    assert status == "queued"
    assert lease_key is None
    assert leased_until is None


@pytest.mark.anyio
async def test_worker_concurrency_is_capped(monkeypatch: pytest.MonkeyPatch):
    """Extremely high WORKER_CONCURRENCY should be capped to a safe maximum."""

    _require_db_or_skip()
    telemetry.reset_for_tests()
    monkeypatch.setenv("WORKER_CONCURRENCY", "10")

    worker_dsn = os.getenv("SERVICE_ROLE_DSN") or _dsn()
    teacher_sub = f"teacher-{uuid.uuid4()}"
    student_sub = f"student-{uuid.uuid4()}"

    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute("delete from public.learning_submission_jobs")
            cur.execute("select set_config('app.current_sub', %s, false)", (teacher_sub,))
            cur.execute(
                "insert into public.courses (title, teacher_id) values (%s, %s) returning id",
                ("Capped Concurrency Course", teacher_sub),
            )
            course_id = cur.fetchone()[0]
            cur.execute(
                "insert into public.units (title, author_id) values (%s, %s) returning id",
                ("Unit", teacher_sub),
            )
            unit_id = cur.fetchone()[0]
            cur.execute(
                "insert into public.unit_sections (unit_id, title, position) values (%s, %s, %s) returning id",
                (unit_id, "Section", 1),
            )
            section_id = cur.fetchone()[0]
            cur.execute(
                """
                insert into public.unit_tasks (unit_id, section_id, instruction_md, criteria, position)
                values (%s, %s, %s, %s::text[], %s) returning id
                """,
                (unit_id, section_id, "Beschreibe den Graphen", ["Kriterium A"], 1),
            )
            task_id = cur.fetchone()[0]

            submission_ids: list[str] = []
            for idx in range(6):
                submission_id = str(uuid.uuid4())
                submission_ids.append(submission_id)
                cur.execute(
                    """
                    insert into public.learning_submissions (
                        id, course_id, task_id, student_sub, kind,
                        text_body, storage_key, mime_type, size_bytes, sha256,
                        attempt_nr, analysis_status, analysis_json
                    ) values (
                        %s::uuid, %s::uuid, %s::uuid, %s, 'text',
                        %s, null, null, null, null,
                        %s, 'pending', null
                    )
                    """,
                    (
                        submission_id,
                        course_id,
                        task_id,
                        student_sub,
                        f"Text answer {idx}",
                        idx + 1,
                    ),
                )
                payload = {
                    "submission_id": submission_id,
                    "course_id": str(course_id),
                    "task_id": str(task_id),
                    "student_sub": student_sub,
                    "kind": "text",
                    "attempt_nr": idx + 1,
                    "criteria": ["Kriterium A"],
                }
                cur.execute(
                    "insert into public.learning_submission_jobs (submission_id, payload) values (%s::uuid, %s::jsonb)",
                    (submission_id, json.dumps(payload)),
                )
        conn.commit()

    processed = run_once(
        dsn=worker_dsn,
        vision_adapter=_StubVisionAdapter(text_md="## Vision Extract\n\nContent."),
        feedback_adapter=_StubFeedbackAdapter(feedback_md="Feedback"),
        now=datetime.now(tz=timezone.utc),
    )

    assert processed is True

    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute("select count(*) from public.learning_submission_jobs")
            remaining_jobs = int(cur.fetchone()[0])

    assert remaining_jobs >= 2, "concurrency should be capped, leaving some jobs queued"
