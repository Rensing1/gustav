"""Database reads and result writes for submission jobs.

The caller supplies an open worker-role connection and owns all commits,
rollbacks and RLS context lifetimes. These operations never invoke AI adapters.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Optional, Sequence

from backend.learning.adapters.ports import TokenUsageEvent, VisionResult

if TYPE_CHECKING:
    from psycopg import Connection

LOG = logging.getLogger("backend.learning.workers.process_learning_submission_jobs")


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


def _delete_job(conn: Connection, *, job_id: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "delete from public.learning_submission_jobs where id = %s::uuid",
            (job_id,),
        )
        LOG.debug("Deleted job %s rowcount=%s", job_id, cur.rowcount)
