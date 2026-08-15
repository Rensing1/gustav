"""
Learning submission worker: leases queued jobs and persists analysis results.

Intent:
    Provide a minimal, framework-free worker that:
      1. Leases the next visible job from `learning_submission_jobs`.
      2. Runs Vision + Feedback adapters.
      3. Marks the submission as completed (or failed in later iterations).
      4. Acknowledges the job by deleting it.

    The worker is invoked from docker-compose via:
        python -m backend.learning.workers.process_learning_submission_jobs
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
import os
from typing import Optional, Sequence
import inspect
from dataclasses import dataclass
from uuid import uuid4
from importlib import import_module
from concurrent.futures import ThreadPoolExecutor

from . import runtime_config, telemetry
from .course_lifecycle_jobs import (
    build_storage_adapter_from_env,
    process_deletion_once,
    process_expired_export_once,
    process_export_once,
)
from backend.learning.adapters.ports import (
    FeedbackAdapterProtocol,
    FeedbackInvalidAnalysisError,
    FeedbackPermanentError,
    FeedbackResult,
    FeedbackTransientError,
    TokenUsageEvent,
    VisionAdapterProtocol,
    VisionPermanentError,
    VisionResult,
    VisionTransientError,
)
from backend.learning.practice.completion import (
    complete_worker_practice_attempt,
    fail_worker_practice_attempt,
)
from backend.teaching.course_invitation_mail import process_course_invitation_mail_once

try:  # pragma: no cover - optional dependency in some environments
    import psycopg
    from psycopg import Connection
    from psycopg.rows import dict_row
    from psycopg import sql as _sql
    HAVE_PSYCOPG = True
except Exception:  # pragma: no cover
    psycopg = None  # type: ignore
    Connection = object  # type: ignore
    HAVE_PSYCOPG = False

LOG = logging.getLogger(__name__)


def _exception_cause_class_name(exc: Exception) -> str | None:
    """Return the direct cause class name without leaking raw upstream payloads."""
    cause = getattr(exc, "__cause__", None)
    return cause.__class__.__name__ if cause is not None else None


def _require_psycopg() -> None:
    if not HAVE_PSYCOPG:
        raise RuntimeError("psycopg3 is required for the learning worker")


# Re-export ports for backwards-compatible imports in tests and adapters.
# This allows `from backend.learning.workers.process_learning_submission_jobs import VisionResult` to keep working.
__all__ = [
    "VisionResult",
    "FeedbackResult",
    "TokenUsageEvent",
    "VisionAdapterProtocol",
    "FeedbackAdapterProtocol",
    "VisionTransientError",
    "VisionPermanentError",
    "FeedbackTransientError",
    "FeedbackPermanentError",
    "FeedbackInvalidAnalysisError",
]


@dataclass
class QueuedJob:
    """Minimal snapshot of a job leased from the queue."""

    id: str
    submission_id: str
    retry_count: int
    payload: dict


MAX_RETRIES = int(os.getenv("WORKER_MAX_RETRIES", "3"))
MAX_CONCURRENCY = runtime_config.MAX_CONCURRENCY
_FEEDBACK_PERMANENT_INPUT_ERROR_CODES = frozenset(
    {"input_corrupt", "input_unsupported", "input_too_large"}
)


# Error classes now live in ports and are imported above.


def _backoff_seconds() -> int:
    """Return configured backoff seconds (>=1) with lenient parsing."""
    return runtime_config.backoff_seconds()


def _concurrency_limit() -> int:
    """Parse WORKER_CONCURRENCY with sane lower/upper bounds."""
    return runtime_config.concurrency_limit()


def _feedback_permanent_error_code(exc: FeedbackPermanentError) -> str:
    """Return the stable worker error code for deterministic Feedback failures."""
    if isinstance(exc, FeedbackInvalidAnalysisError):
        return "feedback_invalid_analysis"
    normalized = str(exc or "").strip()
    if normalized in _FEEDBACK_PERMANENT_INPUT_ERROR_CODES:
        return normalized
    return "feedback_failed"


def _lease_duration_seconds() -> int:
    """Compute the effective lease window to cover long-running Vision/Feedback jobs."""
    return runtime_config.lease_duration_seconds()


def run_once(
    *,
    dsn: str,
    vision_adapter: VisionAdapterProtocol,
    feedback_adapter: FeedbackAdapterProtocol,
    now: Optional[datetime] = None,
    test_run_id: str | None = None,
) -> bool:
    """
    Lease and process up to WORKER_CONCURRENCY pending submission jobs.

    Why:
        The background worker should pick submissions, run Vision and Feedback analysis,
        and either complete the submission or schedule retries. To reduce latency, the
        batch size is controlled via WORKER_CONCURRENCY (default 1).

    Parameters:
        dsn: Postgres connection string for the worker (`gustav_worker` login role).
        vision_adapter: Adapter that turns the queued submission into Markdown text.
        feedback_adapter: Adapter that generates criteria-based feedback for the Markdown text.
        now: Optional UTC timestamp used for deterministic tests; defaults to `datetime.now(timezone.utc)`.

    Behavior:
        - `False` is returned when no job is visible (`status='queued'` and `visible_at <= now`).
        - On success the submission is marked `completed` via `learning_worker_update_completed`
          and the job row is deleted.
        - On adapter failures the worker either re-queues the job with exponential backoff
          (transient errors) or marks the submission `failed` via `learning_worker_update_failed`.

    Permissions:
        The caller must authenticate as the dedicated worker login role (`gustav_worker`).
        This role has EXECUTE privileges on the `learning_worker_*` SECURITY DEFINER helpers
        and DML access to `learning_submission_jobs`. RLS remains active, therefore
        `app.current_sub` must be set before reading or writing submission rows.
    """
    _require_psycopg()
    tick = now or datetime.now(tz=timezone.utc)
    concurrency = _concurrency_limit()

    with psycopg.connect(dsn, row_factory=dict_row) as lease_conn:  # type: ignore[arg-type]
        lease_conn.autocommit = False

        jobs = _lease_jobs(lease_conn, now=tick, limit=concurrency, test_run_id=test_run_id)
        if not jobs:
            lease_conn.rollback()
            return False
        lease_conn.commit()

    if concurrency == 1:
        _process_job_with_new_connection(
            dsn=dsn,
            job=jobs[0],
            vision_adapter=vision_adapter,
            feedback_adapter=feedback_adapter,
            now=tick,
        )
        return True

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [
            executor.submit(
                _process_job_with_new_connection,
                dsn=dsn,
                job=job,
                vision_adapter=vision_adapter,
                feedback_adapter=feedback_adapter,
                now=tick,
            )
            for job in jobs
        ]
        # Propagate the first exception to surface failures.
        for future in futures:
            future.result()
    return True


def _lease_jobs(conn: Connection, *, now: datetime, limit: int, test_run_id: str | None = None) -> list[QueuedJob]:
    """Lease up to `limit` visible jobs from the queue."""
    lease_key = uuid4()
    lease_until = now + timedelta(seconds=_lease_duration_seconds())
    queue_table = _resolve_queue_table(conn)
    with conn.cursor() as cur:
        # Local dev quality-of-life: when developers run unit tests (in-process)
        # while also having the docker `learning-worker` running, the container
        # worker must not consume jobs created by pytest and mutate DB state.
        pytest_filter = _sql.SQL("")
        if _truthy_env("WORKER_SKIP_PYTEST_JOBS", default=False):
            pytest_filter = _sql.SQL("and coalesce(payload->>'_gustav_source', '') <> 'pytest'")
        run_filter = _sql.SQL("")
        params: list[object] = [now, now]
        active_test_run_id = test_run_id or os.getenv("WORKER_TEST_RUN_ID")
        if active_test_run_id:
            run_filter = _sql.SQL("and payload->>'_gustav_test_run_id' = %s")
            params.append(active_test_run_id)
        params.extend([limit, str(lease_key), lease_until])
        stmt = _sql.SQL(
            """
            with candidate as (
                select id,
                       submission_id,
                       payload,
                       retry_count
                  from public.{}
                 where (
                          (
                              status = 'queued'
                              and visible_at <= %s + interval '30 seconds'
                          )
                          or (
                              status = 'leased'
                              and leased_until is not null
                              and leased_until <= %s
                          )
                       )
                  {pytest_filter}
                  {run_filter}
                 order by visible_at asc, created_at asc
                 limit %s
                 for update skip locked
            )
            update public.{} as jobs
               set status = 'leased',
                   lease_key = %s::uuid,
                   leased_until = %s,
                   updated_at = now()
              from candidate
             where jobs.id = candidate.id
            returning jobs.id::text,
                     candidate.submission_id::text,
                     candidate.retry_count,
                     candidate.payload
            """
        ).format(
            _sql.Identifier(queue_table),
            _sql.Identifier(queue_table),
            pytest_filter=pytest_filter,
            run_filter=run_filter,
        )
        cur.execute(stmt, params)
        rows = cur.fetchall()
    jobs: list[QueuedJob] = []
    for row in rows or []:
        is_mapping = isinstance(row, dict)
        jobs.append(
            QueuedJob(
                id=row["id"] if is_mapping else row[0],
                submission_id=row["submission_id"] if is_mapping else row[1],
                retry_count=int(row["retry_count"] if is_mapping else row[2]),
                payload=row["payload"] if is_mapping else row[3],
            )
        )
    return jobs


def _lease_next_job(conn: Connection, *, now: datetime) -> QueuedJob | None:
    """Backwards-compatible helper: lease exactly one job or return None.

    Why:
        Older unit tests (and some external scripts) patch `_lease_next_job(...)`
        directly. The worker now leases in batches via `_lease_jobs(...)`, but we
        keep this wrapper so those tests can remain stable.
    """
    jobs = _lease_jobs(conn, now=now, limit=1)
    return jobs[0] if jobs else None


def _resolve_queue_table(conn: Connection) -> str:
    """
    Ensure the worker queue exists and return its canonical table name.

    Why:
        All downstream DML (_nack_retry/_delete_job) targets
        `public.learning_submission_jobs`. Falling back to the legacy OCR table would
        break retries, so we fail fast when migrations are missing.

    Parameters:
        conn: psycopg connection running as the dedicated worker role. The role only
              needs SELECT on the queue table to verify its existence.

    Behavior:
        - Queries `to_regclass('public.learning_submission_jobs')`.
        - Returns the canonical name when present, otherwise raises.

    Permissions:
        Requires SELECT on `pg_catalog.pg_class` (covered by default schema access) and
        visibility of the `public.learning_submission_jobs` relation.

    Raises:
        RuntimeError: when `public.learning_submission_jobs` is not present.
    """
    with conn.cursor() as cur:
        cur.execute("select to_regclass('public.learning_submission_jobs') as reg")
        reg = cur.fetchone()
    if reg:
        val = reg.get("reg") if isinstance(reg, dict) else reg[0]
        if val:
            return "learning_submission_jobs"
    raise RuntimeError("Queue table public.learning_submission_jobs missing; run migrations.")


def _process_job_with_new_connection(
    *,
    dsn: str,
    job: QueuedJob,
    vision_adapter: VisionAdapterProtocol,
    feedback_adapter: FeedbackAdapterProtocol,
    now: datetime,
) -> None:
    """Isolated job processing using its own DB connection (thread-safe)."""
    _require_psycopg()
    telemetry.adjust_gauge("analysis_jobs_inflight", delta=1)
    conn: Connection | None = None
    try:
        conn = psycopg.connect(dsn, row_factory=dict_row)  # type: ignore[arg-type]
        conn.autocommit = False
        _process_job(
            conn=conn,
            job=job,
            vision_adapter=vision_adapter,
            feedback_adapter=feedback_adapter,
            now=now,
        )
    except Exception:
        try:
            if conn:
                conn.rollback()
                _unlease_job(conn=conn, job_id=job.id)
                conn.commit()
        except Exception:
            pass
        raise
    finally:
        try:
            if conn and hasattr(conn, "close"):
                conn.close()
        finally:
            telemetry.adjust_gauge("analysis_jobs_inflight", delta=-1)


def _process_job(
    *,
    conn: Connection,
    job: QueuedJob,
    vision_adapter: VisionAdapterProtocol,
    feedback_adapter: FeedbackAdapterProtocol,
    now: datetime,
) -> None:
    """Fetch submission, run adapters, and branch into success, retry or failure.

    Transaction boundaries:
        The worker must never keep a DB transaction open while waiting for LLM/VLM
        calls. We therefore:
          1) read all required DB context in a short transaction,
          2) commit,
          3) call adapters (external I/O),
          4) persist results / retries in a second short transaction.
    """
    payload = job.payload if isinstance(job.payload, dict) else {}

    # ---------------------------------------------------------------------
    # Phase 1: DB reads (short transaction)
    # ---------------------------------------------------------------------
    _set_current_sub(conn, str(payload.get("student_sub") or ""))
    submission = _fetch_submission(conn, submission_id=job.submission_id)
    if submission is None:
        LOG.warning("Submission %s missing; deleting job %s", job.submission_id, job.id)
        _delete_job(conn, job_id=job.id)
        conn.commit()
        return

    student_sub = str(submission.get("student_sub") or payload.get("student_sub") or "")
    _set_current_sub(conn, student_sub)
    course_id = str(submission.get("course_id") or payload.get("course_id") or "")
    if course_id:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_course_id', %s, true)", (course_id,))

    # Accept both freshly queued and already extracted submissions (pages persisted).
    if submission.get("analysis_status") not in ("pending", "extracted"):
        LOG.debug(
            "Job %s skipped because submission %s already %s",
            job.id,
            job.submission_id,
            submission.get("analysis_status"),
        )
        _delete_job(conn, job_id=job.id)
        conn.commit()
        return

    task_kind = str(payload.get("task_kind") or "").strip().lower()
    submission_kind = str(submission.get("kind") or "").strip().lower()
    internal_metadata = submission.get("internal_metadata") if isinstance(submission, dict) else None
    analysis_mode = _resolve_analysis_mode(
        payload=payload,
        internal_metadata=internal_metadata if isinstance(internal_metadata, dict) else {},
        task_kind=task_kind,
        submission_kind=submission_kind,
    )
    task_context = _fetch_task_context(
        conn=conn,
        task_id=str(submission.get("task_id") or payload.get("task_id") or ""),
        is_practice_attempt=bool(payload.get("practice_attempt_id")),
    )
    instruction_md = payload.get("instruction_md") or task_context.get("instruction_md")
    teacher_context_md = task_context.get("teacher_context_md")
    if task_context.get("is_practice_attempt") and task_context.get("model_solution_md"):
        teacher_context_md = "\n\n".join(
            part
            for part in (
                str(teacher_context_md or "").strip(),
                "Verbindliche Musterlösung:\n"
                + str(task_context["model_solution_md"]).strip(),
            )
            if part
        )

    # End the transaction before any external I/O (ticket: avoid "idle in transaction").
    conn.commit()

    # ---------------------------------------------------------------------
    # Dialog tasks: keep learner performance and AI context typed separately.
    # ---------------------------------------------------------------------
    if analysis_mode == "dialog":
        try:
            analyze_dialog = getattr(feedback_adapter, "analyze_dialog", None)
            if not callable(analyze_dialog):
                raise FeedbackPermanentError("missing_dialog_feedback_adapter")
            feedback_result = analyze_dialog(
                student_performance=dict(payload.get("student_performance") or {}),
                conversation_context=dict(payload.get("conversation_context") or {}),
                criteria=list(payload.get("criteria") or []),
                instruction_md=str(instruction_md or ""),
            )
        except FeedbackPermanentError as exc:
            _set_current_sub(conn, student_sub)
            _persist_ai_usage_events(
                conn=conn,
                submission_id=job.submission_id,
                usage_events=_usage_events_from_exception(exc),
            )
            _handle_feedback_error(
                conn=conn,
                job=job,
                submission_id=job.submission_id,
                now=now,
                message=str(exc),
                error_code=_feedback_permanent_error_code(exc),
                transient=False,
            )
            conn.commit()
            return
        except FeedbackTransientError as exc:
            _set_current_sub(conn, student_sub)
            _persist_ai_usage_events(
                conn=conn,
                submission_id=job.submission_id,
                usage_events=_usage_events_from_exception(exc),
            )
            _handle_feedback_error(
                conn=conn,
                job=job,
                submission_id=job.submission_id,
                now=now,
                message=str(exc),
                transient=True,
            )
            conn.commit()
            return

        _set_current_sub(conn, student_sub)
        _persist_ai_usage_events(
            conn=conn,
            submission_id=job.submission_id,
            usage_events=list(getattr(feedback_result, "usage_events", []) or []),
        )
        _update_submission_completed(
            conn=conn,
            submission_id=job.submission_id,
            text_md=None,
            analysis_json=feedback_result.analysis_json,
            feedback_md=feedback_result.feedback_md,
        )
        if payload.get("practice_attempt_id") and not _complete_practice_attempt_or_fail(
                conn=conn,
                job=job,
                analysis_json=feedback_result.analysis_json,
                feedback_md=feedback_result.feedback_md,
        ):
            conn.commit()
            return
        telemetry.increment_counter("ai_worker_processed_total", status="completed")
        _delete_job(conn, job_id=job.id)
        conn.commit()
        return

    # ---------------------------------------------------------------------
    # Visual tasks: evaluate directly from image/PDF (no OCR pipeline)
    # ---------------------------------------------------------------------
    if analysis_mode == "visual_direct":
        try:
            analyze_visual = getattr(feedback_adapter, "analyze_visual", None)
            if not callable(analyze_visual):
                raise FeedbackPermanentError("missing_visual_feedback_adapter")

            analyze_kwargs = {
                "submission": submission,
                "job_payload": job.payload,
                "criteria": payload.get("criteria", []),
            }
            sig = None
            try:
                sig = inspect.signature(analyze_visual)
            except Exception:
                sig = None
            if sig and "instruction_md" in sig.parameters:
                analyze_kwargs["instruction_md"] = instruction_md
            if sig and "teacher_context_md" in sig.parameters:
                analyze_kwargs["teacher_context_md"] = teacher_context_md
            elif sig and "hints_md" in sig.parameters:
                analyze_kwargs["hints_md"] = teacher_context_md

            feedback_result = analyze_visual(**analyze_kwargs)
        except FeedbackPermanentError as exc:
            LOG.warning(
                "Feedback permanent error for submission=%s job=%s task_id=%s task_kind=%s intent=%s criteria_count=%s has_instruction=%s has_teacher_context=%s reason=%s cause_class=%s",
                job.submission_id,
                job.id,
                submission.get("task_id"),
                task_kind,
                submission.get("intent") or payload.get("intent") or "submit",
                len(payload.get("criteria", [])),
                bool(instruction_md),
                bool(teacher_context_md),
                str(exc),
                _exception_cause_class_name(exc),
            )
            _set_current_sub(conn, student_sub)
            _persist_ai_usage_events(
                conn=conn,
                submission_id=job.submission_id,
                usage_events=_usage_events_from_exception(exc),
            )
            _handle_feedback_error(
                conn=conn,
                job=job,
                submission_id=job.submission_id,
                now=now,
                message=str(exc),
                error_code=_feedback_permanent_error_code(exc),
                transient=False,
            )
            conn.commit()
            return
        except FeedbackTransientError as exc:
            LOG.info(
                "Feedback transient error for submission=%s job=%s task_id=%s task_kind=%s intent=%s criteria_count=%s has_instruction=%s has_teacher_context=%s reason=%s cause_class=%s",
                job.submission_id,
                job.id,
                submission.get("task_id"),
                task_kind,
                submission.get("intent") or payload.get("intent") or "submit",
                len(payload.get("criteria", [])),
                bool(instruction_md),
                bool(teacher_context_md),
                str(exc),
                _exception_cause_class_name(exc),
            )
            _set_current_sub(conn, student_sub)
            _persist_ai_usage_events(
                conn=conn,
                submission_id=job.submission_id,
                usage_events=_usage_events_from_exception(exc),
            )
            _handle_feedback_error(
                conn=conn,
                job=job,
                submission_id=job.submission_id,
                now=now,
                message=str(exc),
                transient=True,
            )
            conn.commit()
            return

        _set_current_sub(conn, student_sub)
        _persist_ai_usage_events(
            conn=conn,
            submission_id=job.submission_id,
            usage_events=list(getattr(feedback_result, "usage_events", []) or []),
        )
        _update_submission_completed(
            conn=conn,
            submission_id=job.submission_id,
            text_md=None,
            analysis_json=feedback_result.analysis_json,
            feedback_md=feedback_result.feedback_md,
        )
        if payload.get("practice_attempt_id") and not _complete_practice_attempt_or_fail(
                conn=conn,
                job=job,
                analysis_json=feedback_result.analysis_json,
                feedback_md=feedback_result.feedback_md,
        ):
            conn.commit()
            return
        telemetry.increment_counter("ai_worker_processed_total", status="completed")
        _delete_job(conn, job_id=job.id)
        conn.commit()
        return

    # ---------------------------------------------------------------------
    # Non-visual tasks: Vision/OCR (if needed) + Feedback
    # ---------------------------------------------------------------------
    cached_vision = _cached_vision_result(submission=submission, job=job)
    try:
        if cached_vision is not None:
            vision_result = cached_vision
        else:
            if submission_kind == "text":
                vision_result = VisionResult(
                    text_md=str(submission.get("text_body") or ""),
                    raw_metadata={"adapter": "worker", "backend": "pass_through", "reason": "text_submission"},
                )
            else:
                vision_result = vision_adapter.extract(submission=submission, job_payload=job.payload)
    except VisionPermanentError as exc:
        LOG.warning(
            "Vision permanent error for submission %s job %s: %s",
            job.submission_id,
            job.id,
            exc.__class__.__name__,
        )
        _set_current_sub(conn, student_sub)
        _persist_ai_usage_events(
            conn=conn,
            submission_id=job.submission_id,
            usage_events=_usage_events_from_exception(exc),
        )
        _handle_vision_error(
            conn=conn,
            job=job,
            submission_id=job.submission_id,
            now=now,
            message=str(exc),
            transient=False,
        )
        conn.commit()
        return
    except VisionTransientError as exc:
        LOG.info(
            "Vision transient error for submission %s job %s: %s",
            job.submission_id,
            job.id,
            exc.__class__.__name__,
        )
        _set_current_sub(conn, student_sub)
        _persist_ai_usage_events(
            conn=conn,
            submission_id=job.submission_id,
            usage_events=_usage_events_from_exception(exc),
        )
        _handle_vision_error(
            conn=conn,
            job=job,
            submission_id=job.submission_id,
            now=now,
            message=str(exc),
            transient=True,
        )
        conn.commit()
        return

    try:
        analyze_kwargs = {
            "text_md": vision_result.text_md,
            "criteria": payload.get("criteria", []),
        }
        sig = None
        try:
            sig = inspect.signature(feedback_adapter.analyze)  # type: ignore[attr-defined]
        except Exception:
            sig = None
        if sig and "instruction_md" in sig.parameters:
            analyze_kwargs["instruction_md"] = instruction_md
        if sig and "teacher_context_md" in sig.parameters:
            analyze_kwargs["teacher_context_md"] = teacher_context_md
        elif sig and "hints_md" in sig.parameters:
            analyze_kwargs["hints_md"] = teacher_context_md

        feedback_result = feedback_adapter.analyze(**analyze_kwargs)  # type: ignore[arg-type]
    except FeedbackPermanentError as exc:
        LOG.warning(
            "Feedback permanent error for submission=%s job=%s task_id=%s task_kind=%s intent=%s criteria_count=%s has_instruction=%s has_teacher_context=%s reason=%s cause_class=%s",
            job.submission_id,
            job.id,
            submission.get("task_id"),
            task_kind,
            submission.get("intent") or payload.get("intent") or "submit",
            len(payload.get("criteria", [])),
            bool(instruction_md),
            bool(teacher_context_md),
            str(exc),
            _exception_cause_class_name(exc),
            )
        _set_current_sub(conn, student_sub)
        _persist_ai_usage_events(
            conn=conn,
            submission_id=job.submission_id,
            usage_events=[
                *list(getattr(vision_result, "usage_events", []) or []),
                *_usage_events_from_exception(exc),
            ],
        )
        if cached_vision is None and (submission.get("kind") or "").strip() != "text":
            _persist_cached_vision(conn=conn, job_id=job.id, vision_result=vision_result)
        _handle_feedback_error(
            conn=conn,
            job=job,
            submission_id=job.submission_id,
            now=now,
            message=str(exc),
            error_code=_feedback_permanent_error_code(exc),
            transient=False,
        )
        conn.commit()
        return
    except FeedbackTransientError as exc:
        LOG.info(
            "Feedback transient error for submission=%s job=%s task_id=%s task_kind=%s intent=%s criteria_count=%s has_instruction=%s has_teacher_context=%s reason=%s cause_class=%s",
            job.submission_id,
            job.id,
            submission.get("task_id"),
            task_kind,
            submission.get("intent") or payload.get("intent") or "submit",
            len(payload.get("criteria", [])),
            bool(instruction_md),
            bool(teacher_context_md),
            str(exc),
            _exception_cause_class_name(exc),
        )
        _set_current_sub(conn, student_sub)
        _persist_ai_usage_events(
            conn=conn,
            submission_id=job.submission_id,
            usage_events=[
                *list(getattr(vision_result, "usage_events", []) or []),
                *_usage_events_from_exception(exc),
            ],
        )
        if cached_vision is None and (submission.get("kind") or "").strip() != "text":
            _persist_cached_vision(conn=conn, job_id=job.id, vision_result=vision_result)
        _handle_feedback_error(
            conn=conn,
            job=job,
            submission_id=job.submission_id,
            now=now,
            message=str(exc),
            transient=True,
        )
        conn.commit()
        return

    _set_current_sub(conn, student_sub)
    _persist_ai_usage_events(
        conn=conn,
        submission_id=job.submission_id,
        usage_events=[
            *list(getattr(vision_result, "usage_events", []) or []),
            *list(getattr(feedback_result, "usage_events", []) or []),
        ],
    )
    _update_submission_completed(
        conn=conn,
        submission_id=job.submission_id,
        text_md=vision_result.text_md,
        analysis_json=feedback_result.analysis_json,
        feedback_md=feedback_result.feedback_md,
    )
    if payload.get("practice_attempt_id") and not _complete_practice_attempt_or_fail(
            conn=conn,
            job=job,
            analysis_json=feedback_result.analysis_json,
            feedback_md=feedback_result.feedback_md,
    ):
        conn.commit()
        return
    telemetry.increment_counter("ai_worker_processed_total", status="completed")
    _delete_job(conn, job_id=job.id)
    conn.commit()


def _complete_practice_attempt_or_fail(
    *, conn: Connection, job: QueuedJob, analysis_json: dict, feedback_md: str
) -> bool:
    """Complete a practice attempt or persist invalid AI output as a terminal failure.

    A malformed criteria result is a technical analysis error. It must remain
    auditable, reopen the item for a fresh submission and never mutate the
    scheduler. Unexpected completion errors still propagate to the worker's
    ordinary transaction rollback path.
    """

    try:
        complete_worker_practice_attempt(
            conn=conn,
            submission_id=job.submission_id,
            analysis_json=analysis_json,
            feedback_md=feedback_md,
        )
    except ValueError as exc:
        if str(exc) != "invalid_practice_analysis":
            raise
        error_code = "practice_analysis_invalid"
        _update_submission_failed(
            conn=conn,
            submission_id=job.submission_id,
            error_code=error_code,
            message="Practice analysis did not satisfy the ten-point criteria contract.",
        )
        fail_worker_practice_attempt(
            conn=conn,
            submission_id=job.submission_id,
            error_code=error_code,
        )
        _mark_job_failed(conn=conn, job_id=job.id, error_code=error_code)
        telemetry.increment_counter("ai_worker_failed_total", error_code=error_code)
        return False
    return True


def _resolve_analysis_mode(
    *,
    payload: dict,
    internal_metadata: dict,
    task_kind: str,
    submission_kind: str,
) -> str:
    """Return the processing mode for this submission attempt.

    Why:
        Task kind describes the pedagogical task family, but file uploads on
        native tasks now use the same direct visual-analysis path as visual
        tasks. Keeping this decision in one helper prevents drift between queue
        payloads, persisted metadata, and legacy fallbacks.
    """
    explicit = str(payload.get("analysis_mode") or internal_metadata.get("analysis_mode") or "").strip().lower()
    if explicit in {"text_direct", "visual_direct", "ocr_text", "dialog"}:
        return explicit
    if submission_kind == "dialog" or task_kind == "dialog":
        return "dialog"
    if submission_kind == "text":
        return "text_direct"
    if task_kind in {"native", "visual"}:
        return "visual_direct"
    return "ocr_text"


def _fetch_submission(conn: Connection, *, submission_id: str) -> Optional[dict]:
    with conn.cursor() as cur:
        cur.execute(
            """
            select id::text,
                   student_sub,
                   course_id::text,
                   task_id::text,
                   kind,
                   text_body,
                   mime_type,
                   size_bytes,
                   storage_key,
                   sha256,
                   analysis_status,
                   internal_metadata
             from public.learning_submissions
            where id = %s::uuid
            """,
            (submission_id,),
        )
        row = cur.fetchone()
    return dict(row) if row else None


def _fetch_task_context(
    conn: Connection, *, task_id: str, is_practice_attempt: bool = False
) -> dict[str, str | bool | None]:
    """Fetch task context needed for feedback generation.

    Notes:
        This runs under the submission's student RLS context (`app.current_sub`)
        so the SELECT must remain safe for students. We intentionally load the
        teacher-only AI context from the tasks table but never expose it through
        the Learning API surface.
    """
    if not task_id:
        return {
            "instruction_md": None,
            "teacher_context_md": None,
            "model_solution_md": None,
            "is_practice_attempt": False,
        }
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                select task.instruction_md,
                       task.teacher_context_md,
                       task.model_solution_md
                  from public.unit_tasks task
                 where task.id = %s::uuid
                """,
                (task_id,),
            )
            row = cur.fetchone()
    except Exception as exc:
        LOG.warning("Task context lookup failed task_id=%s reason=%s", task_id, exc.__class__.__name__)
        return {
            "instruction_md": None,
            "teacher_context_md": None,
            "model_solution_md": None,
            "is_practice_attempt": False,
        }
    if not row:
        return {
            "instruction_md": None,
            "teacher_context_md": None,
            "model_solution_md": None,
            "is_practice_attempt": False,
        }
    # psycopg rows may be tuple-like or dict-like depending on row_factory.
    # The worker uses `row_factory=dict_row`, while some tests use defaults.
    try:
        instruction_md = row["instruction_md"]  # type: ignore[index]
        teacher_context_md = row["teacher_context_md"]  # type: ignore[index]
        model_solution_md = row["model_solution_md"]  # type: ignore[index]
    except Exception:
        instruction_md = row[0] if len(row) > 0 else None  # type: ignore[index]
        teacher_context_md = row[1] if len(row) > 1 else None  # type: ignore[index]
        model_solution_md = row[2] if len(row) > 2 else None  # type: ignore[index]
    return {
        "instruction_md": instruction_md,
        "teacher_context_md": teacher_context_md,
        "model_solution_md": model_solution_md,
        "is_practice_attempt": bool(is_practice_attempt),
    }


def _set_current_sub(conn: Connection, sub: str) -> None:
    if not sub:
        return
    with conn.cursor() as cur:
        cur.execute("select set_config('app.current_sub', %s, true)", (sub,))


def _usage_events_from_exception(exc: Exception) -> list[TokenUsageEvent]:
    """Return adapter-captured usage events without depending on concrete error types."""
    events = getattr(exc, "usage_events", None)
    if not isinstance(events, list):
        return []
    return [event for event in events if isinstance(event, TokenUsageEvent)]


def _persist_ai_usage_events(
    *,
    conn: Connection,
    submission_id: str,
    usage_events: Sequence[TokenUsageEvent],
) -> None:
    """Persist technical AI usage events through the worker DB helper.

    Why:
        The worker should not write derived course/student context directly.
        The database helper derives that context from `submission_id`, keeping
        spoofable identifiers out of this boundary.

    Permissions:
        Requires EXECUTE on `learning_worker_record_ai_usage` for the
        dedicated `gustav_worker` role.
    """
    if not usage_events:
        return
    with conn.cursor() as cur:
        for event in usage_events:
            cur.execute(
                """
                select public.learning_worker_record_ai_usage(
                    %s::uuid,
                    %s::uuid,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                """,
                (
                    submission_id,
                    event.event_key,
                    event.model,
                    event.stage,
                    event.modality,
                    event.call_kind,
                    event.usage_known,
                    event.input_tokens,
                    event.output_tokens,
                    event.total_tokens,
                    event.unknown_reason,
                ),
            )


def _update_submission_completed(
    *,
    conn: Connection,
    submission_id: str,
    text_md: str | None,
    analysis_json: dict,
    feedback_md: str,
) -> None:
    """Persist the final analysis results via the security-definer helper."""
    import json as _json

    analysis_param = _json.dumps(analysis_json)
    json_placeholder = "%s::jsonb"

    with conn.cursor() as cur:
        cur.execute(
            f"""
            select public.learning_worker_update_completed(
                %s::uuid,
                %s,
                %s,
                {json_placeholder}
            )
            """,
            (
                submission_id,
                text_md,
                feedback_md,
                analysis_param,
            ),
        )


def _cached_vision_result(*, submission: dict, job: QueuedJob) -> VisionResult | None:
    """Return cached OCR text when submission is already extracted and payload carries text."""
    status = (submission.get("analysis_status") or "").strip()
    payload = job.payload if isinstance(job.payload, dict) else {}
    cached_text = payload.get("cached_text_md") if isinstance(payload, dict) else None
    if status != "extracted" or not cached_text:
        return None
    raw_meta = payload.get("cached_raw_metadata") if isinstance(payload, dict) else None
    raw_meta = raw_meta if isinstance(raw_meta, dict) else {"source": "cached_payload"}
    return VisionResult(text_md=str(cached_text), raw_metadata=raw_meta)


def _persist_cached_vision(*, conn: Connection, job_id: str, vision_result: VisionResult) -> None:
    """Store OCR text/metadata on the job payload so retries can skip Vision."""
    import json as _json
    cache = {
        "cached_text_md": vision_result.text_md,
        "cached_raw_metadata": vision_result.raw_metadata,
    }
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                update public.learning_submission_jobs
                   set payload = payload || %s::jsonb,
                       updated_at = now()
                 where id = %s::uuid
                """,
                (_json.dumps(cache), job_id),
            )
    except (AttributeError, AssertionError):
        # Fallback for monkeypatched or non-DB test connections; caching is optional for tests.
        LOG.debug("Skipping cached vision persistence for job %s (test double without cursor)", job_id)


def _unlease_job(*, conn: Connection, job_id: str) -> None:
    """Return a leased job to the queue after unexpected processing errors."""
    with conn.cursor() as cur:
        cur.execute(
            """
            update public.learning_submission_jobs
               set status = 'queued',
                   lease_key = null,
                   leased_until = null,
                   updated_at = now(),
                   visible_at = now()
             where id = %s::uuid
            """,
            (job_id,),
        )


def _handle_vision_error(
    *,
    conn: Connection,
    job: QueuedJob,
    submission_id: str,
    now: datetime,
    message: str,
    transient: bool,
) -> None:
    """Handle Vision adapter failures with retries/backoff or failure marking."""
    truncated = _truncate_error_message(message)
    if transient and job.retry_count < MAX_RETRIES:
        _mark_submission_retry(conn=conn, submission_id=submission_id, now=now, message=truncated)
        telemetry.increment_counter("ai_worker_retry_total", phase="vision")
        next_visible = _nack_retry(conn=conn, job=job, now=now)
        LOG.warning(
            "Vision retry scheduled for submission=%s job=%s retry=%s next_visible_at=%s reason=%s",
            submission_id,
            job.id,
            job.retry_count + 1,
            next_visible.isoformat(),
            truncated,
        )
        return

    _update_submission_failed(
        conn=conn,
        submission_id=submission_id,
        error_code="vision_failed",
        message=truncated,
    )
    if isinstance(job.payload, dict) and job.payload.get("practice_attempt_id"):
        fail_worker_practice_attempt(
            conn=conn, submission_id=submission_id, error_code="vision_failed"
        )
    # Record the terminal failure on the job row for observability/audit dashboards.
    _mark_job_failed(conn=conn, job_id=job.id, error_code="vision_failed")
    telemetry.increment_counter("ai_worker_failed_total", error_code="vision_failed")


def _handle_feedback_error(
    *,
    conn: Connection,
    job: QueuedJob,
    submission_id: str,
    now: datetime,
    message: str,
    error_code: str = "feedback_failed",
    transient: bool,
) -> None:
    """Handle Feedback adapter failures with retries/backoff or failure marking."""
    truncated = _truncate_error_message(message)
    if transient and job.retry_count < MAX_RETRIES:
        _mark_feedback_retry(conn=conn, submission_id=submission_id, now=now, message=truncated)
        telemetry.increment_counter("ai_worker_retry_total", phase="feedback")
        next_visible = _nack_retry(conn=conn, job=job, now=now)
        LOG.warning(
            "Feedback retry scheduled for submission=%s job=%s retry=%s next_visible_at=%s reason=%s",
            submission_id,
            job.id,
            job.retry_count + 1,
            next_visible.isoformat(),
            truncated,
        )
        return

    _update_submission_failed(
        conn=conn,
        submission_id=submission_id,
        error_code=error_code,
        message=truncated,
    )
    if isinstance(job.payload, dict) and job.payload.get("practice_attempt_id"):
        fail_worker_practice_attempt(
            conn=conn, submission_id=submission_id, error_code=error_code
        )
    # Preserve the terminal failure on the queue row so operators can inspect past errors.
    _mark_job_failed(conn=conn, job_id=job.id, error_code=error_code)
    telemetry.increment_counter("ai_worker_failed_total", error_code=error_code)


def _mark_submission_retry(*, conn: Connection, submission_id: str, now: datetime, message: str) -> None:
    """Update retry bookkeeping on the submission while keeping status pending."""
    _mark_retry_metadata(
        conn=conn,
        submission_id=submission_id,
        phase="vision",
        attempted_at=now,
        message=message,
    )


def _mark_feedback_retry(*, conn: Connection, submission_id: str, now: datetime, message: str) -> None:
    """Persist feedback retry metadata while staying pending."""
    _mark_retry_metadata(
        conn=conn,
        submission_id=submission_id,
        phase="feedback",
        attempted_at=now,
        message=message,
    )


def _mark_retry_metadata(
    *,
    conn: Connection,
    submission_id: str,
    phase: str,
    attempted_at: datetime,
    message: str,
) -> None:
    """
    Delegate retry bookkeeping to the SECURITY DEFINER helper.

    Why:
        Retry metadata should be recorded through `learning_worker_mark_retry` so the worker
        does not require broad UPDATE privileges on `learning_submissions`.

    Parameters:
        conn: Active psycopg connection authenticated as the dedicated worker role.
        submission_id: Submission being processed.
        phase: Either ``vision`` or ``feedback`` to route to the correct retry branch.
        attempted_at: UTC timestamp of the adapter invocation.
        message: Sanitised error message describing the transient failure.

    Behavior:
        - Calls into the Postgres helper which increments attempt counters and timestamps.
        - Keeps the submission in `analysis_status='pending'` while surfacing `*_retrying`.

    Permissions:
        Requires EXECUTE on `learning_worker_mark_retry`, granted to the `gustav_worker` role.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            select public.learning_worker_mark_retry(
                %s::uuid,
                %s,
                %s,
                %s
            )
            """,
            (submission_id, phase, message, attempted_at),
        )


def _nack_retry(*, conn: Connection, job: QueuedJob, now: datetime) -> datetime:
    """Requeue the job with exponential backoff and return the next visibility timestamp."""
    delay_seconds = _backoff_seconds() * (2 ** job.retry_count)
    next_visible = now + timedelta(seconds=delay_seconds)
    with conn.cursor() as cur:
        # Reset to queued so that the worker sees it again after the backoff window expires.
        cur.execute(
            """
            update public.learning_submission_jobs
               set status = 'queued',
                   retry_count = %s,
                   visible_at = %s,
                   lease_key = null,
                   leased_until = null,
                   error_code = null,
                   updated_at = now()
             where id = %s::uuid
            """,
            (job.retry_count + 1, next_visible, job.id),
        )
    return next_visible


def _mark_job_failed(*, conn: Connection, job_id: str, error_code: str) -> None:
    """
    Persist a terminal failure for the leased job.

    Why:
        Keep an auditable record in `learning_submission_jobs` when a submission cannot be
        processed successfully so operators can trace failure causes later on.

    Parameters:
        conn: Open psycopg connection with access to the worker queue table.
        job_id: Primary key of the job that just failed.
        error_code: Normalized failure code (`vision_failed` or `feedback_failed`).

    Behavior:
        - Marks the job `status='failed'` and stores the error code.
        - Clears the lease metadata so the row is immutable afterwards.

    Permissions:
        Invoked under the dedicated worker role which has `UPDATE` privileges on
        `learning_submission_jobs` (no RLS guard on the queue table).
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            update public.learning_submission_jobs
               set status = 'failed',
                   error_code = %s,
                   lease_key = null,
                   leased_until = null,
                   updated_at = now()
             where id = %s::uuid
            """,
            (error_code, job_id),
        )


def _update_submission_failed(
    *,
    conn: Connection,
    submission_id: str,
    error_code: str,
    message: str,
) -> None:
    """Delegate to the SECURITY DEFINER helper for failed submissions."""
    with conn.cursor() as cur:
        cur.execute(
            """
            select public.learning_worker_update_failed(
                %s::uuid,
                %s,
                %s
            )
            """,
            (submission_id, error_code, message),
        )


def _truncate_error_message(message: str, limit: int = 1024) -> str:
    """Trim error messages to a safe length for storage."""
    text = (message or "").strip()
    if len(text) <= limit:
        return text
    return f"{text[: limit - 3]}..."


def _delete_job(conn: Connection, *, job_id: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "delete from public.learning_submission_jobs where id = %s::uuid",
            (job_id,),
        )
        LOG.debug("Deleted job %s rowcount=%s", job_id, cur.rowcount)


def run_forever(
    *,
    dsn: str,
    vision_adapter: VisionAdapterProtocol,
    feedback_adapter: FeedbackAdapterProtocol,
    poll_interval: float = 0.5,
    lifecycle_storage_adapter=None,
    course_invite_mail_processor=process_course_invitation_mail_once,
    mail_poll_interval: float = 5.0,
) -> None:
    """Continuously process learning, lifecycle and Teaching mail queues.

    The invitation queue is polled on its own small cadence so an idle learning
    queue does not require a second service, while also avoiding extra database
    sessions on every half-second learning poll.
    """
    import time

    next_mail_poll = 0.0
    while True:
        processed = run_once(
            dsn=dsn,
            vision_adapter=vision_adapter,
            feedback_adapter=feedback_adapter,
        )
        if lifecycle_storage_adapter is not None:
            processed = run_lifecycle_once(
                dsn=dsn,
                storage_adapter=lifecycle_storage_adapter,
            ) or processed
        now_monotonic = time.monotonic()
        if now_monotonic >= next_mail_poll:
            try:
                processed = course_invite_mail_processor(dsn=dsn) or processed
            except Exception as exc:
                # Teaching mail is best-effort and must never stop learning jobs.
                LOG.error(
                    "course_invite_mail.processor_failed error=%s",
                    type(exc).__name__,
                )
            next_mail_poll = now_monotonic + max(0.0, mail_poll_interval)
        if not processed:
            time.sleep(poll_interval)


def run_lifecycle_once(*, dsn: str, storage_adapter) -> bool:
    """Process each lifecycle queue once without letting cleanup starve deletion.

    Expired exports can require repeated storage cleanup attempts. Course
    deletion therefore runs before that best-effort cleanup, while new exports
    retain first priority.
    """

    processed = process_export_once(dsn=dsn, storage_adapter=storage_adapter)
    processed = process_deletion_once(dsn=dsn, storage_adapter=storage_adapter) or processed
    processed = process_expired_export_once(dsn=dsn, storage_adapter=storage_adapter) or processed
    return processed


def _dsn_username(dsn: str) -> str:
    return runtime_config.dsn_username(dsn)


def _resolve_worker_dsn() -> str:
    """
    Resolve the Postgres DSN for the learning worker with least-privilege guards.

    Behavior:
        - Favors explicit worker overrides
          (LEARNING_WORKER_DATABASE_URL/LEARNING_WORKER_DB_URL).
        - Falls back to legacy learning overrides
          (LEARNING_DATABASE_URL/LEARNING_DB_URL) for backwards compatibility.
        - Falls back to the dedicated worker login role derived from
          LEARNING_WORKER_DB_USER/LEARNING_WORKER_DB_PASSWORD.
        - Rejects service-role/superuser accounts (postgres, service_role) unless
          ALLOW_SERVICE_DSN_FOR_TESTING=true (opt-in for local debugging).
    """

    return runtime_config.resolve_worker_dsn()


def _truthy_env(name: str, *, default: bool = False) -> bool:
    return runtime_config.truthy_env(name, default=default)


def main() -> None:
    """CLI entrypoint for the worker."""
    level_name = os.getenv("LOG_LEVEL", "INFO")
    normalized_level = level_name.strip().upper() or "INFO"
    logging.basicConfig(level=normalized_level)
    dsn = _resolve_worker_dsn()

    from backend.learning.config import load_learning_adapter_config

    cfg = load_learning_adapter_config()
    vision_path = cfg.vision_adapter_path
    feedback_path = cfg.feedback_adapter_path
    LOG.info("learning.adapters.selected vision=%s feedback=%s", vision_path, feedback_path)

    vision_module = import_module(vision_path)
    feedback_module = import_module(feedback_path)

    vision_adapter = vision_module.build()  # type: ignore[attr-defined]
    feedback_adapter = feedback_module.build()  # type: ignore[attr-defined]

    poll_interval = float(os.getenv("WORKER_POLL_INTERVAL", "0.5"))
    lifecycle_storage_adapter = build_storage_adapter_from_env()
    if lifecycle_storage_adapter is None:
        LOG.warning("Course export and deletion jobs are disabled because private storage is not configured")
    run_forever(
        dsn=dsn,
        vision_adapter=vision_adapter,
        feedback_adapter=feedback_adapter,
        poll_interval=poll_interval,
        lifecycle_storage_adapter=lifecycle_storage_adapter,
    )


if __name__ == "__main__":
    main()
