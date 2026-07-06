"""Submission history and worker helper queries for the Learning repository.

Why:
    History reads and worker-adjacent state transitions are a separate surface
    from submission creation. Keeping them here leaves DBLearningRepo as a small
    facade and makes the remaining RLS-sensitive helper queries easier to audit.
"""

from __future__ import annotations

from uuid import UUID


def list_submissions(
    repo,
    *,
    psycopg_module,
    student_sub: str,
    course_id: str,
    task_id: str,
    limit: int,
    offset: int,
) -> list[dict]:
    """Fetch the caller's submission history for a task.

    Intent:
        Encapsulate membership/visibility guards and stable ordering inside
        the persistence layer while keeping use cases framework-agnostic.

    Parameters:
        student_sub: Authenticated student's subject identifier.
        course_id: Course scope for the task, UUID string.
        task_id: Target task UUID.
        limit/offset: Pagination parameters (already clamped by use case).

    Permissions:
        Caller must be enrolled in the course and the section must be
        released; enforced via membership check and
        `get_task_metadata_for_student`.
    """
    course_uuid = str(UUID(course_id))
    task_uuid = str(UUID(task_id))

    with psycopg_module.connect(repo._dsn) as conn:
        with conn.cursor() as cur:
            repo._set_current_sub(cur, student_sub)
            repo._set_current_course_id(cur, course_uuid)
            cur.execute(
                "select exists(select 1 from public.course_memberships where course_id=%s and student_id=%s)",
                (course_uuid, student_sub),
            )
            if not bool(cur.fetchone()[0]):
                raise PermissionError("not_course_member")

            cur.execute(
                """
                select task_id::text,
                       section_id::text,
                       unit_id::text
                  from public.get_task_metadata_for_student(%s, %s, %s)
                """,
                (student_sub, course_uuid, task_uuid),
            )
            meta = cur.fetchone()
            if not meta:
                raise LookupError("task_not_visible")
            section_uuid = str(UUID(meta[1]))
            unit_uuid = str(UUID(meta[2]))
            if not repo._is_modular_section_open_or_done(
                cur=cur,
                course_uuid=course_uuid,
                student_sub=student_sub,
                unit_uuid=unit_uuid,
                section_uuid=section_uuid,
            ):
                raise LookupError("task_not_visible")

            cur.execute(
                """
                select id::text,
                       attempt_nr,
                       intent,
                       kind,
                       score_raw,
                       score_max,
                       text_body,
                       mime_type,
                       size_bytes,
                       storage_key,
                       sha256,
                       analysis_status,
                       analysis_json,
                       feedback_md,
                       error_code,
                       coalesce(vision_attempts, 0),
                       vision_last_error,
                       to_char(feedback_last_attempt_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                       feedback_last_error,
                       to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                       to_char(completed_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
                  from public.learning_submissions
                 where course_id = %s
                   and task_id = %s
                   and student_sub = %s
                 order by created_at desc, attempt_nr desc
                 limit %s offset %s
                """,
                (course_uuid, task_uuid, student_sub, int(limit), int(offset)),
            )
            rows = cur.fetchall()

    return [repo._row_to_submission(row) for row in rows]

def get_task_kind_for_student(
    repo,
    *,
    psycopg_module,
    student_sub: str,
    course_id: str,
    task_id: str,
) -> str:
    """Return the backend task kind for a student-visible task.

    Intent:
        Provide a minimal, framework-free way for web adapters to make
        task-kind decisions (e.g., upload allowlists) without duplicating
        SQL helpers across layers.

    Security:
        Enforces course membership and released visibility using the same
        DB guards as submissions/listing paths (RLS + helpers).
    """
    course_uuid = str(UUID(course_id))
    task_uuid = str(UUID(task_id))
    with psycopg_module.connect(repo._dsn) as conn:
        with conn.cursor() as cur:
            repo._set_current_sub(cur, student_sub)
            repo._set_current_course_id(cur, course_uuid)
            cur.execute(
                "select exists(select 1 from public.course_memberships where course_id=%s and student_id=%s)",
                (course_uuid, student_sub),
            )
            if not bool(cur.fetchone()[0]):
                raise PermissionError("not_course_member")
            cur.execute(
                """
                select task_id::text,
                       section_id::text,
                       unit_id::text,
                       kind
                  from public.get_task_metadata_for_student(%s, %s, %s)
                """,
                (student_sub, course_uuid, task_uuid),
            )
            meta = cur.fetchone()
            if not meta:
                raise LookupError("task_not_visible")
            section_uuid = str(UUID(meta[1]))
            unit_uuid = str(UUID(meta[2]))
            if not repo._is_modular_section_open_or_done(
                cur=cur,
                course_uuid=course_uuid,
                student_sub=student_sub,
                unit_uuid=unit_uuid,
                section_uuid=section_uuid,
            ):
                raise LookupError("task_not_visible")
            kind = str(meta[3] or "native").strip() or "native"
    return kind

def resolve_queue_table(cur) -> str:
    """
    Ensure the canonical worker queue exists before inserting jobs.

    Parameters:
        cur: Open psycopg cursor operating under `gustav_limited`. The caller
             already set `app.current_sub`, so we only assert schema state here.

    Behavior:
        - Checks `to_regclass('public.learning_submission_jobs')`.
        - Returns the canonical table name when present, otherwise aborts with a
          descriptive runtime error so API callers see a 500 instead of silently
          failing to enqueue submissions.

    Permissions:
        Requires SELECT on `pg_catalog.pg_class`, included in the default privileges
        of the application role.
    """
    cur.execute("select to_regclass('public.learning_submission_jobs')")
    reg = cur.fetchone()
    if reg and reg[0]:
        return "learning_submission_jobs"
    raise RuntimeError("Queue table public.learning_submission_jobs missing; run migrations.")

# ------------------------------------------------------------------
def mark_extracted(repo, *, psycopg_module, json_adapter, submission_id: str, page_keys: list[str]) -> None:
    """Set analysis_status to 'extracted' and persist page key metadata internally.

    Why:
        After rendering a PDF to page images, we record their storage keys
        to enable downstream OCR/vision steps. The artifacts remain private
        (`internal_metadata`) so the public API stays schema-compliant.

    Behavior:
        - Updates only the targeted submission id.
        - Sets `analysis_status = 'extracted'`.
        - Stores `page_keys` inside `internal_metadata` while keeping
          `analysis_json` null until feedback is generated.

    Permissions:
        The repo executes with the limited application role under RLS. The
        caller must only pass submission ids that belong to the current
        student/flow per surrounding use case.
    """
    if not submission_id:
        raise ValueError("submission_id is required")
    with psycopg_module.connect(repo._dsn) as conn:
        with conn.cursor() as cur:
            # We do not change completed_at here; 'extracted' is intermediate
            cur.execute(
                """
                update public.learning_submissions
                   set analysis_status = 'extracted',
                       analysis_json = null,
                       internal_metadata = coalesce(internal_metadata, '{}'::jsonb)
                                          || jsonb_build_object('page_keys', %s::jsonb)
             where id = %s::uuid
                returning id
                """,
                (json_adapter(list(page_keys)), str(UUID(submission_id))),
            )
            updated = cur.fetchone()
            if not updated:
                raise LookupError("submission_not_found")
        conn.commit()
