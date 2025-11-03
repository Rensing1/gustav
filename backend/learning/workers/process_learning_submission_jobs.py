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

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging
import os
from typing import Optional, Protocol, Sequence
from uuid import UUID, uuid4

from . import telemetry

try:  # pragma: no cover - optional dependency in some environments
    import psycopg
    from psycopg import Connection
    from psycopg.rows import dict_row
    HAVE_PSYCOPG = True
except Exception:  # pragma: no cover
    psycopg = None  # type: ignore
    Connection = object  # type: ignore
    HAVE_PSYCOPG = False

LOG = logging.getLogger(__name__)


def _require_psycopg() -> None:
    if not HAVE_PSYCOPG:
        raise RuntimeError("psycopg3 is required for the learning worker")


@dataclass
class VisionResult:
    """Vision adapter response."""

    text_md: str
    raw_metadata: Optional[dict] = None


@dataclass
class FeedbackResult:
    """Feedback adapter response."""

    feedback_md: str
    analysis_json: dict


class VisionAdapterProtocol(Protocol):
    """Vision adapter turns submissions into Markdown text."""

    def extract(self, *, submission: dict, job_payload: dict) -> VisionResult:
        ...


class FeedbackAdapterProtocol(Protocol):
    """Feedback adapter generates formative feedback for Markdown text."""

    def analyze(self, *, text_md: str, criteria: Sequence[str]) -> FeedbackResult:
        ...


@dataclass
class QueuedJob:
    """Minimal snapshot of a job leased from the queue."""

    id: str
    submission_id: str
    retry_count: int
    payload: dict


LEASE_SECONDS = int(os.getenv("WORKER_LEASE_SECONDS", "45"))
MAX_RETRIES = int(os.getenv("WORKER_MAX_RETRIES", "3"))


class VisionError(Exception):
    """Base class for Vision adapter failures."""


class VisionTransientError(VisionError):
    """Recoverable Vision error; worker should retry with backoff."""


class VisionPermanentError(VisionError):
    """Non-recoverable Vision error; worker marks submission failed."""


class FeedbackError(Exception):
    """Base class for Feedback adapter failures."""


class FeedbackTransientError(FeedbackError):
    """Recoverable Feedback error; worker should retry."""


class FeedbackPermanentError(FeedbackError):
    """Non-recoverable Feedback error; worker marks submission failed."""


def _backoff_seconds() -> int:
    """Return configured backoff seconds (>=1) with lenient parsing."""
    raw = os.getenv("WORKER_BACKOFF_SECONDS", "10")
    try:
        value = int(raw)
    except ValueError:
        LOG.warning("Invalid WORKER_BACKOFF_SECONDS=%s, defaulting to 10 seconds", raw)
        return 10
    return max(1, value)


def run_once(
    *,
    dsn: str,
    vision_adapter: VisionAdapterProtocol,
    feedback_adapter: FeedbackAdapterProtocol,
    now: Optional[datetime] = None,
) -> bool:
    """
    Lease and process at most one pending submission job.

    Why:
        The background worker should pick a single submission, run Vision and
        Feedback analysis, and either complete the submission or schedule a retry.

    Parameters:
        dsn: Postgres connection string for the worker (service role with function EXECUTE grants).
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
        The caller must authenticate as the dedicated worker role (`gustav_worker`) which has
        EXECUTE privileges on the `learning_worker_*` SECURITY DEFINER helpers and DML access
        to `learning_submission_jobs`. RLS remains active, therefore `app.current_sub` must be
        set before reading or writing submission rows.
    """
    _require_psycopg()
    tick = now or datetime.now(tz=timezone.utc)

    with psycopg.connect(dsn, row_factory=dict_row) as conn:  # type: ignore[arg-type]
        conn.autocommit = False

        job = _lease_next_job(conn, now=tick)
        if job is None:
            conn.rollback()
            return False

        telemetry.adjust_gauge("analysis_jobs_inflight", delta=1)
        try:
            _process_job(
                conn=conn,
                job=job,
                vision_adapter=vision_adapter,
                feedback_adapter=feedback_adapter,
                now=tick,
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            telemetry.adjust_gauge("analysis_jobs_inflight", delta=-1)
    return True


def _lease_next_job(conn: Connection, *, now: datetime) -> Optional[QueuedJob]:
    """Lease the next visible job using `SELECT ... FOR UPDATE SKIP LOCKED`."""
    lease_key = uuid4()
    lease_until = now + timedelta(seconds=LEASE_SECONDS)
    with conn.cursor() as cur:
        cur.execute(
            """
            with candidate as (
                select id,
                       submission_id,
                       payload,
                       retry_count
                  from public.learning_submission_jobs
                 where status = 'queued'
                   and visible_at <= %s
                 order by visible_at asc, created_at asc
                 limit 1
                 for update skip locked
            )
            update public.learning_submission_jobs as jobs
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
            """,
            (now, str(lease_key), lease_until),
        )
        row = cur.fetchone()
    if not row:
        return None
    return QueuedJob(
        id=row["id"],
        submission_id=row["submission_id"],
        retry_count=int(row["retry_count"]),
        payload=row["payload"],
    )


def _process_job(
    *,
    conn: Connection,
    job: QueuedJob,
    vision_adapter: VisionAdapterProtocol,
    feedback_adapter: FeedbackAdapterProtocol,
    now: datetime,
) -> None:
    """Fetch submission, run adapters, and branch into success, retry or failure."""
    # Impersonate the student before selecting so RLS exposes the row.
    _set_current_sub(conn, job.payload.get("student_sub", ""))
    submission = _fetch_submission(conn, submission_id=job.submission_id)
    if submission is None:
        LOG.warning("Submission %s missing; deleting job %s", job.submission_id, job.id)
        _delete_job(conn, job_id=job.id)
        return
    # Ensure RLS context remains set for update (submission includes student_sub).
    _set_current_sub(conn, submission.get("student_sub", job.payload.get("student_sub", "")))

    if submission.get("analysis_status") != "pending":
        LOG.debug(
            "Job %s skipped because submission %s already %s",
            job.id,
            job.submission_id,
            submission.get("analysis_status"),
        )
        _delete_job(conn, job_id=job.id)
        return

    try:
        vision_result = vision_adapter.extract(submission=submission, job_payload=job.payload)
    except VisionPermanentError as exc:
        LOG.warning(
            "Vision permanent error for submission %s job %s: %s",
            job.submission_id,
            job.id,
            exc,
        )
        _handle_vision_error(
            conn=conn,
            job=job,
            submission_id=job.submission_id,
            now=now,
            message=str(exc),
            transient=False,
        )
        return
    except VisionTransientError as exc:
        LOG.info(
            "Vision transient error for submission %s job %s: %s",
            job.submission_id,
            job.id,
            exc,
        )
        _handle_vision_error(
            conn=conn,
            job=job,
            submission_id=job.submission_id,
            now=now,
            message=str(exc),
            transient=True,
        )
        return

    try:
        feedback_result = feedback_adapter.analyze(
            text_md=vision_result.text_md, criteria=job.payload.get("criteria", [])
        )
    except FeedbackPermanentError as exc:
        LOG.warning(
            "Feedback permanent error for submission %s job %s: %s",
            job.submission_id,
            job.id,
            exc,
        )
        _handle_feedback_error(
            conn=conn,
            job=job,
            submission_id=job.submission_id,
            now=now,
            message=str(exc),
            transient=False,
        )
        return
    except FeedbackTransientError as exc:
        LOG.info(
            "Feedback transient error for submission %s job %s: %s",
            job.submission_id,
            job.id,
            exc,
        )
        _handle_feedback_error(
            conn=conn,
            job=job,
            submission_id=job.submission_id,
            now=now,
            message=str(exc),
            transient=True,
        )
        return

    _update_submission_completed(
        conn=conn,
        submission_id=job.submission_id,
        text_md=vision_result.text_md,
        analysis_json=feedback_result.analysis_json,
        feedback_md=feedback_result.feedback_md,
    )
    telemetry.increment_counter("ai_worker_processed_total", status="completed")
    _delete_job(conn, job_id=job.id)


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
                   analysis_status
              from public.learning_submissions
             where id = %s::uuid
            """,
            (submission_id,),
        )
        row = cur.fetchone()
    return dict(row) if row else None


def _set_current_sub(conn: Connection, sub: str) -> None:
    if not sub:
        return
    with conn.cursor() as cur:
        cur.execute("select set_config('app.current_sub', %s, true)", (sub,))


def _update_submission_completed(
    *,
    conn: Connection,
    submission_id: str,
    text_md: str,
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
        error_code="feedback_failed",
        message=truncated,
    )
    # Preserve the terminal failure on the queue row so operators can inspect past errors.
    _mark_job_failed(conn=conn, job_id=job.id, error_code="feedback_failed")
    telemetry.increment_counter("ai_worker_failed_total", error_code="feedback_failed")


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
) -> None:
    """Continuously process jobs until interrupted."""
    import time

    while True:
        processed = run_once(
            dsn=dsn,
            vision_adapter=vision_adapter,
            feedback_adapter=feedback_adapter,
        )
        if not processed:
            time.sleep(poll_interval)


def _default_dsn() -> str:
    env = os.getenv("LEARNING_DATABASE_URL") or os.getenv("DATABASE_URL")
    if env:
        return env
    host = os.getenv("TEST_DB_HOST", "127.0.0.1")
    port = os.getenv("TEST_DB_PORT", "54322")
    user = os.getenv("APP_DB_USER", "gustav_app")
    password = os.getenv("APP_DB_PASSWORD", "CHANGE_ME_DEV")
    return f"postgresql://{user}:{password}@{host}:{port}/postgres"


def main() -> None:
    """CLI entrypoint for the worker."""
    level_name = os.getenv("LOG_LEVEL", "INFO")
    normalized_level = level_name.strip().upper() or "INFO"
    logging.basicConfig(level=normalized_level)
    dsn = _default_dsn()

    from importlib import import_module

    vision_path = os.getenv("LEARNING_VISION_ADAPTER", "backend.learning.adapters.stub_vision")
    feedback_path = os.getenv("LEARNING_FEEDBACK_ADAPTER", "backend.learning.adapters.stub_feedback")

    vision_module = import_module(vision_path)
    feedback_module = import_module(feedback_path)

    vision_adapter = vision_module.build()  # type: ignore[attr-defined]
    feedback_adapter = feedback_module.build()  # type: ignore[attr-defined]

    poll_interval = float(os.getenv("WORKER_POLL_INTERVAL", "0.5"))
    run_forever(
        dsn=dsn,
        vision_adapter=vision_adapter,
        feedback_adapter=feedback_adapter,
        poll_interval=poll_interval,
    )


if __name__ == "__main__":
    main()
