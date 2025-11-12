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
import re
from typing import Optional, Sequence
import inspect
from dataclasses import dataclass
from uuid import UUID, uuid4
from importlib import import_module

from . import telemetry
from backend.learning.adapters.ports import (
    FeedbackAdapterProtocol,
    FeedbackPermanentError,
    FeedbackResult,
    FeedbackTransientError,
    VisionAdapterProtocol,
    VisionPermanentError,
    VisionResult,
    VisionTransientError,
)

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


def _require_psycopg() -> None:
    if not HAVE_PSYCOPG:
        raise RuntimeError("psycopg3 is required for the learning worker")


# Re-export ports for backwards-compatible imports in tests and adapters.
# This allows `from backend.learning.workers.process_learning_submission_jobs import VisionResult` to keep working.
__all__ = [
    "VisionResult",
    "FeedbackResult",
    "VisionAdapterProtocol",
    "FeedbackAdapterProtocol",
    "VisionTransientError",
    "VisionPermanentError",
    "FeedbackTransientError",
    "FeedbackPermanentError",
]


@dataclass
class QueuedJob:
    """Minimal snapshot of a job leased from the queue."""

    id: str
    submission_id: str
    retry_count: int
    payload: dict


LEASE_SECONDS = int(os.getenv("WORKER_LEASE_SECONDS", "45"))
MAX_RETRIES = int(os.getenv("WORKER_MAX_RETRIES", "3"))


# Error classes now live in ports and are imported above.


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
    """Lease the next visible job from the available queue table.

    Supports both the new `learning_submission_jobs` and the legacy
    `learning_submission_ocr_jobs` table to remain compatible with different
    migration baselines.
    """
    lease_key = uuid4()
    lease_until = now + timedelta(seconds=LEASE_SECONDS)
    queue_table = _resolve_queue_table(conn)
    if not queue_table:
        return None
    with conn.cursor() as cur:
        stmt = _sql.SQL(
            """
            with candidate as (
                select id,
                       submission_id,
                       payload,
                       retry_count
                  from public.{}
                 where (
                          status = 'queued'
                          and visible_at <= %s + interval '5 seconds'
                       )
                    or (
                          status = 'leased'
                          and leased_until is not null
                          and leased_until <= %s
                       )
                 order by visible_at asc, created_at asc
                 limit 1
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
        ).format(_sql.Identifier(queue_table), _sql.Identifier(queue_table))
        cur.execute(stmt, (now, now, str(lease_key), lease_until))
        row = cur.fetchone()
    if not row:
        return None
    return QueuedJob(
        id=row["id"],
        submission_id=row["submission_id"],
        retry_count=int(row["retry_count"]),
        payload=row["payload"],
    )


def _resolve_queue_table(conn: Connection) -> Optional[str]:
    """Return available queue table name (new or legacy) if present."""
    for name in ("learning_submission_jobs", "learning_submission_ocr_jobs"):
        with conn.cursor() as cur:
            cur.execute("select to_regclass(%s) as reg", (f"public.{name}",))
            reg = cur.fetchone()
            if reg:
                # Support both dict_row and tuple rows
                val = reg.get("reg") if isinstance(reg, dict) else reg[0]
                if val:
                    return name
    return None


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

    # Accept both freshly queued and already extracted submissions (pages persisted).
    if submission.get("analysis_status") not in ("pending", "extracted"):
        LOG.debug(
            "Job %s skipped because submission %s already %s",
            job.id,
            job.submission_id,
            submission.get("analysis_status"),
        )
        _delete_job(conn, job_id=job.id)
        return

    try:
        # For plain text submissions we never invoke Vision/OCR/LLM. Preserve the
        # original student text verbatim to avoid unintended transformations.
        if (submission.get("kind") or "").strip() == "text":
            from backend.learning.adapters.ports import VisionResult as _VR  # local import to avoid cycles
            vision_result = _VR(
                text_md=str(submission.get("text_body") or ""),
                raw_metadata={"adapter": "worker", "backend": "pass_through", "reason": "text_submission"},
            )
        else:
            vision_result = vision_adapter.extract(submission=submission, job_payload=job.payload)
    except VisionPermanentError:
        # Avoid logging exception messages to prevent PII in logs.
        LOG.warning(
            "Vision permanent error for submission %s job %s",
            job.submission_id,
            job.id,
        )
        _handle_vision_error(
            conn=conn,
            job=job,
            submission_id=job.submission_id,
            now=now,
            message="vision_failed",
            transient=False,
        )
        return
    except VisionTransientError:
        LOG.info(
            "Vision transient error for submission %s job %s",
            job.submission_id,
            job.id,
        )
        _handle_vision_error(
            conn=conn,
            job=job,
            submission_id=job.submission_id,
            now=now,
            message="vision_retrying",
            transient=True,
        )
        return

    try:
        # Pass task context (instruction/hints) to adapters that support it; keep compatibility otherwise.
        analyze_kwargs = {
            "text_md": vision_result.text_md,
            "criteria": job.payload.get("criteria", []),
        }
        if isinstance(job.payload, dict):
            instr = job.payload.get("instruction_md")
            hints = job.payload.get("hints_md")
            sig = None
            try:
                sig = inspect.signature(feedback_adapter.analyze)  # type: ignore[attr-defined]
            except Exception:
                sig = None
            if sig and "instruction_md" in sig.parameters and "hints_md" in sig.parameters:
                analyze_kwargs["instruction_md"] = instr
                analyze_kwargs["hints_md"] = hints
        feedback_result = feedback_adapter.analyze(**analyze_kwargs)  # type: ignore[arg-type]
    except FeedbackPermanentError:
        LOG.warning(
            "Feedback permanent error for submission %s job %s",
            job.submission_id,
            job.id,
        )
        _handle_feedback_error(
            conn=conn,
            job=job,
            submission_id=job.submission_id,
            now=now,
            message="feedback_failed",
            transient=False,
        )
        return
    except FeedbackTransientError:
        LOG.info(
            "Feedback transient error for submission %s job %s",
            job.submission_id,
            job.id,
        )
        _handle_feedback_error(
            conn=conn,
            job=job,
            submission_id=job.submission_id,
            now=now,
            message="feedback_retrying",
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
            "Vision retry scheduled for submission=%s job=%s retry=%s next_visible_at=%s",
            submission_id,
            job.id,
            job.retry_count + 1,
            next_visible.isoformat(),
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
            "Feedback retry scheduled for submission=%s job=%s retry=%s next_visible_at=%s",
            submission_id,
            job.id,
            job.retry_count + 1,
            next_visible.isoformat(),
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


def _dsn_username(dsn: str) -> str:
    try:
        from urllib.parse import urlparse

        parsed = urlparse(dsn)
        if parsed.username:
            return parsed.username
    except Exception:
        pass
    match = re.match(r"^[a-z]+://(?P<user>[^:@/]+)", dsn or "")
    return match.group("user") if match else ""


def _resolve_worker_dsn() -> str:
    """
    Resolve the Postgres DSN for the learning worker with least-privilege guards.

    Behavior:
        - Favors explicit overrides (LEARNING_DATABASE_URL/LEARNING_DB_URL/DATABASE_URL).
        - Falls back to the app login role derived from APP_DB_USER/APP_DB_PASSWORD.
        - Rejects service-role/superuser accounts (postgres, service_role) unless
          ALLOW_SERVICE_DSN_FOR_TESTING=true (opt-in for local debugging).
    """

    def _truthy(env_name: str) -> bool:
        return (os.getenv(env_name, "") or "").strip().lower() in {"1", "true", "yes", "on"}

    candidates = [
        os.getenv("LEARNING_DATABASE_URL"),
        os.getenv("LEARNING_DB_URL"),
        os.getenv("DATABASE_URL"),
    ]
    for candidate in candidates:
        if candidate:
            dsn = candidate
            break
    else:
        host = os.getenv("TEST_DB_HOST", "127.0.0.1")
        port = os.getenv("TEST_DB_PORT", "54322")
        user = os.getenv("APP_DB_USER", "gustav_app")
        password = os.getenv("APP_DB_PASSWORD", "CHANGE_ME_DEV")
        dsn = f"postgresql://{user}:{password}@{host}:{port}/postgres"

    allow_service = _truthy("ALLOW_SERVICE_DSN_FOR_TESTING") or _truthy("RUN_E2E") or _truthy("RUN_SUPABASE_E2E")
    user = _dsn_username(dsn)
    if user in {"postgres", "service_role", "supabase_admin"} and not allow_service:
        raise RuntimeError(
            "Learning worker requires the gustav_app (or gustav_worker) login role. "
            "Override LEARNING_DATABASE_URL with a limited account or set "
            "ALLOW_SERVICE_DSN_FOR_TESTING=true for temporary local debugging."
        )
    return dsn


_TRUTHY = {"1", "true", "yes", "on"}


def _truthy_env(name: str, *, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in _TRUTHY


def _json_adapter_enabled() -> bool:
    """Feature toggle for JSONAdapter (default on; set env to 'false' to disable)."""
    return _truthy_env("LEARNING_DSPY_JSON_ADAPTER", default=True)


def _ensure_ollama_host_env() -> str | None:
    """
    Align DSPy/LiteLLM host resolution with the worker configuration.

    DSPy (via LiteLLM) expects `api_base` or `OLLAMA_API_BASE`, whereas our
    env files only expose `OLLAMA_BASE_URL`. We propagate the value to the
    expected knobs and return it so callers can pass `api_base` explicitly.
    """
    base_url = (os.getenv("OLLAMA_BASE_URL") or "").strip()
    if not base_url:
        return None

    if not (os.getenv("OLLAMA_HOST") or "").strip():
        os.environ["OLLAMA_HOST"] = base_url
    if not (os.getenv("OLLAMA_API_BASE") or "").strip():
        os.environ["OLLAMA_API_BASE"] = base_url
    return base_url


def main() -> None:
    """CLI entrypoint for the worker."""
    level_name = os.getenv("LOG_LEVEL", "INFO")
    normalized_level = level_name.strip().upper() or "INFO"
    logging.basicConfig(level=normalized_level)
    dsn = _resolve_worker_dsn()

    # Centralised config load (keeps behaviour identical to the previous env logic).
    from backend.learning.config import load_ai_config

    cfg = load_ai_config()
    vision_path = cfg.vision_adapter_path
    feedback_path = cfg.feedback_adapter_path
    LOG.info(
        "learning.adapters.selected backend=%s vision=%s feedback=%s",
        cfg.backend,
        vision_path,
        feedback_path,
    )

    # Configure DSPy globally when available so structured outputs are preferred.
    try:  # pragma: no cover - behavior validated via higher-level tests
        import dspy  # type: ignore

        model_name = (os.getenv("AI_FEEDBACK_MODEL") or "").strip()
        if model_name and hasattr(dspy, "LM"):
            api_base = _ensure_ollama_host_env()
            lm_kwargs = {"api_base": api_base} if api_base else {}
            lm = dspy.LM(f"ollama/{model_name}", **lm_kwargs)  # type: ignore[attr-defined]
            use_json_adapter = _json_adapter_enabled()
            adapter_cls = getattr(dspy, "JSONAdapter", None) if use_json_adapter else None
            if adapter_cls is not None:
                dspy.configure(lm=lm, adapter=adapter_cls())  # type: ignore[misc]
                adapter_label = "JSONAdapter"
            else:
                # Explicit opt-out path: allow local debugging without JSONAdapter.
                dspy.configure(lm=lm)
                adapter_label = "default"
            LOG.info("learning.feedback.dspy_configured model=%s adapter=%s", model_name, adapter_label)
    except Exception as _cfg_exc:  # pragma: no cover
        LOG.debug("DSPy not configured: %s", type(_cfg_exc).__name__)

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
