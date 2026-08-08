"""Submission command queries for the Learning repository.

Why:
    Creating and finalizing submissions is the largest write surface in the
    Learning repository. Keeping the SQL-heavy command flow here lets
    DBLearningRepo stay a small facade while preserving the existing public
    persistence contract and RLS behavior.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid5

from backend.learning.submission_kind_policy import validate_task_submission_kind

if TYPE_CHECKING:
    from backend.learning.repo_db import SubmissionInput


def find_matching_inflight_feedback_submission(
    cur: Any,
    *,
    course_uuid: str,
    task_uuid: str,
    student_sub: str,
    data: SubmissionInput,
) -> Any | None:
    """Return the newest matching in-flight feedback submission, if any.

    Why:
        The learner UI already disables the feedback button locally, but
        accidental double-clicks or parallel retries can still reach the
        backend with different idempotency keys. Reusing the active
        feedback submission prevents duplicate worker runs without blocking
        a deliberate re-run after completion.
    """
    if data.intent != "feedback" or data.kind == "h5p":
        return None

    base_query = """
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
         where course_id = %s::uuid
           and task_id = %s::uuid
           and student_sub = %s
           and intent = 'feedback'
           and (
                analysis_status in ('pending', 'extracted')
                or error_code in ('vision_retrying', 'feedback_retrying')
           )
    """

    if data.kind == "text":
        text_body = str(data.text_body or "").strip()
        if not text_body:
            return None
        cur.execute(
            base_query
            + """
               and kind = 'text'
               and btrim(coalesce(text_body, '')) = %s
             order by created_at desc, attempt_nr desc
             limit 1
            """,
            (course_uuid, task_uuid, student_sub, text_body),
        )
        return cur.fetchone()

    if data.kind not in {"image", "file"}:
        return None

    mime_type = str(data.mime_type or "").strip().lower()
    sha256 = str(data.sha256 or "").strip().lower()
    if not mime_type or not sha256 or data.size_bytes is None:
        return None

    cur.execute(
        base_query
        + """
           and kind = %s
           and coalesce(mime_type, '') = %s
           and coalesce(sha256, '') = %s
           and coalesce(size_bytes, -1) = %s
         order by created_at desc, attempt_nr desc
         limit 1
        """,
        (course_uuid, task_uuid, student_sub, data.kind, mime_type, sha256, int(data.size_bytes)),
    )
    return cur.fetchone()

# ------------------------------------------------------------------
def create_submission(repo, data: SubmissionInput, *, psycopg_module, sql_module, json_adapter, json_dumps, running_under_pytest, pytest_test_run_id) -> dict:
    """Persist a student submission after enforcing membership and attempts.

    Why:
        Centralizes membership checks, release visibility, rubric retrieval
        and attempt counting within the persistence adapter so the use case
        stays framework-agnostic.

    Parameters:
        data: SubmissionInput containing course/task identifiers, caller
              `student_sub`, payload kind and optional storage metadata.

    Behavior:
        - Verifies membership via course_memberships (RLS-aware).
        - Reuses existing row when an Idempotency-Key is supplied.
        - Fetches release metadata (max_attempts + rubric criteria) via
          `get_task_metadata_for_student`, which already scopes rows to
          the caller and visible sections.
        - Persists the submission and returns the stored record with stub
          analysis/feedback fields.

    Permissions:
        Caller must be the enrolled student and the section must be
        released. Database helper functions enforce this through RLS.
    """
    course_uuid = str(UUID(data.course_id))
    task_uuid = str(UUID(data.task_id))

    with psycopg_module.connect(repo._dsn) as conn:
        with conn.cursor() as cur:
            repo._set_current_sub(cur, data.student_sub)
            # Course-scoped RLS context: required for modular units where
            # section/task visibility depends on the current course.
            repo._set_current_course_id(cur, course_uuid)
            cur.execute(
                "select exists(select 1 from public.course_memberships where course_id=%s and student_id=%s)",
                (course_uuid, data.student_sub),
            )
            if not bool(cur.fetchone()[0]):
                raise PermissionError("not_course_member")

            # Normalize Idempotency-Key (guard against hidden whitespace/case quirks)
            norm_key = None
            if data.idempotency_key and isinstance(data.idempotency_key, str):
                nk = data.idempotency_key.strip()
                norm_key = nk if nk else None

            if norm_key:
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
                     where course_id = %s::uuid
                       and task_id = %s::uuid
                       and student_sub = %s
                       and idempotency_key = %s
                    """,
                    (course_uuid, task_uuid, data.student_sub, norm_key),
                )
                existing = cur.fetchone()
                if existing:
                    return repo._row_to_submission(existing)

            cur.execute(
                """
                select task_id::text,
                       section_id::text,
                       unit_id::text,
                       kind,
                       h5p_content_id,
                       max_attempts,
                       coalesce(criteria, array[]::text[])
                  from public.get_task_metadata_for_student(%s, %s, %s)
                """,
                (data.student_sub, course_uuid, task_uuid),
            )
            meta = cur.fetchone()
            if not meta:
                raise LookupError("task_not_visible")
            section_uuid = str(UUID(meta[1]))
            unit_uuid = str(UUID(meta[2]))
            cur.execute(
                "select module_kind from public.unit_modules where section_id=%s::uuid",
                (section_uuid,),
            )
            module_row = cur.fetchone()
            if module_row and str(module_row[0]) == "practice":
                raise ValueError("practice_requires_session")
            if not repo._is_modular_section_open_or_done(
                cur=cur,
                course_uuid=course_uuid,
                student_sub=data.student_sub,
                unit_uuid=unit_uuid,
                section_uuid=section_uuid,
            ):
                raise LookupError("task_not_visible")
            task_kind = str(meta[3] or "native")
            max_attempts = meta[5]
            # Rubric criteria come from the helper (already filtered by RLS).
            raw_criteria = list(meta[6] or [])
            criteria = [str(entry).strip() for entry in raw_criteria if str(entry).strip()]

            # Guard against mixing task types and submission types.
            # This prevents students from spoofing a different submission kind.
            validate_task_submission_kind(
                task_kind=task_kind,
                submission_kind=data.kind,
                mime_type=data.mime_type,
            )
            if task_kind == "h5p" and (data.score_raw is None or data.score_max is None):
                raise ValueError("invalid_h5p_payload")

            cur.execute(
                "select public.next_attempt_nr(%s, %s, %s)",
                (course_uuid, task_uuid, data.student_sub),
            )
            attempt_nr = int(cur.fetchone()[0])
            existing_feedback = find_matching_inflight_feedback_submission(
                cur,
                course_uuid=course_uuid,
                task_uuid=task_uuid,
                student_sub=data.student_sub,
                data=data,
            )
            if existing_feedback:
                return repo._row_to_submission(existing_feedback)
            # H5P attempts are not limited at the GUSTAV DB layer (H5P can enforce its own limits).
            # Native feedback runs are stored as submissions, but only final submissions
            # consume the teacher-defined attempt limit.
            if task_kind != "h5p" and max_attempts is not None and data.intent == "submit":
                cur.execute(
                    """
                    select count(*)
                      from public.learning_submissions
                     where course_id = %s::uuid
                       and task_id = %s::uuid
                       and student_sub = %s
                       and intent = 'submit'
                    """,
                    (course_uuid, task_uuid, data.student_sub),
                )
                final_attempt_count = int(cur.fetchone()[0] or 0)
                if final_attempt_count >= int(max_attempts):
                    raise ValueError("max_attempts_exceeded")

            try:
                analysis_mode = "text_direct"
                if data.kind in ("image", "file"):
                    analysis_mode = "visual_direct" if task_kind in {"native", "visual"} else "ocr_text"

                # Async path: record pending status and enqueue job. Idempotency is enforced
                # via ON CONFLICT on (course_id, task_id, student_sub, idempotency_key).
                # For stronger guarantees independent of index inference, when an
                # Idempotency-Key is provided we derive a deterministic UUIDv5 for
                # the primary key from (course_id, task_id, student_sub, key). This
                # ensures duplicate retries inevitably collide on the primary key.
                deterministic_id = None
                if norm_key:
                    # UUID namespace chosen arbitrarily but constant.
                    deterministic_id = str(
                        uuid5(UUID("00000000-0000-0000-0000-000000000001"),
                              f"{course_uuid}:{task_uuid}:{data.student_sub}:{norm_key}")
                    )

                if data.kind == "h5p":
                    cur.execute(
                        """
                        insert into public.learning_submissions (
                            id,
                            course_id,
                            task_id,
                            section_id,
                            student_sub,
                            intent,
                            kind,
                            score_raw,
                            score_max,
                            attempt_nr,
                            analysis_status,
                            analysis_json,
                            feedback_md,
                            error_code,
                            idempotency_key,
                            completed_at
                        )
                        values (
                                coalesce(%s::uuid, gen_random_uuid()),
                                %s::uuid,
                                %s::uuid,
                                %s::uuid,
                                %s,
                                %s,
                                %s,
                                %s,
                                %s,
                                %s,
                                'completed',
                                null,
                                null,
                                null,
                                %s,
                                now()
                        )
                        on conflict (course_id, task_id, student_sub, idempotency_key)
                        do nothing
                        returning id::text,
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
                        """,
                        (
                            deterministic_id,
                            course_uuid,
                            task_uuid,
                            section_uuid,
                            data.student_sub,
                            data.intent,
                            data.kind,
                            int(data.score_raw),
                            int(data.score_max),
                            attempt_nr,
                            norm_key,
                        ),
                    )
                else:
                    cur.execute(
                        """
                        insert into public.learning_submissions (
                            id,
                            course_id,
                            task_id,
                            section_id,
                            student_sub,
                            intent,
                            kind,
                            text_body,
                            storage_key,
                            mime_type,
                            size_bytes,
                            sha256,
                            attempt_nr,
                            analysis_status,
                            analysis_json,
                            feedback_md,
                            error_code,
                            idempotency_key,
                            internal_metadata
                        )
                        values (
                                coalesce(%s::uuid, gen_random_uuid()),
                                %s::uuid,
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
                                %s,
                                'pending',
                                null,
                                null,
                                null,
                                %s,
                                jsonb_build_object('analysis_mode', %s::text)
                        )
                        on conflict (course_id, task_id, student_sub, idempotency_key)
                        do nothing
                        returning id::text,
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
                        """,
                        (
                            deterministic_id,
                            course_uuid,
                            task_uuid,
                            section_uuid,
                            data.student_sub,
                            data.intent,
                            data.kind,
                            data.text_body,
                            data.storage_key,
                            data.mime_type,
                            data.size_bytes,
                            data.sha256,
                            attempt_nr,
                            norm_key,
                            analysis_mode,
                        ),
                    )
                row = cur.fetchone()
                if row is None and norm_key:
                    # Conflict occurred; fetch existing row by idempotency key
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
                         where course_id = %s::uuid and task_id = %s::uuid and student_sub = %s and idempotency_key = %s
                        """,
                        (course_uuid, task_uuid, data.student_sub, norm_key),
                    )
                    row = cur.fetchone()
                if data.kind == "h5p":
                    conn.commit()
                    return repo._row_to_submission(row)
                submission_id = row[0]
                # Enrich job payload with the visible task instruction.
                #
                # Why:
                #   Visual-native uploads skip OCR and go straight into the
                #   feedback model. The queue payload must therefore carry
                #   the student-visible task instruction even for modular
                #   units. `get_released_tasks_for_student(...)` is section-
                #   shaped and can miss the concrete task here, so we read
                #   the already-authorized task row directly.
                instruction_md: str | None = None
                try:
                    cur.execute(
                        """
                        select instruction_md
                          from public.unit_tasks
                         where id = %s::uuid
                        """,
                        (task_uuid,),
                    )
                    row_ctx = cur.fetchone()
                    if row_ctx:
                        instruction_md = row_ctx[0]
                except Exception:
                    # Be tolerant: missing context must not block submissions.
                    instruction_md = None

                job_payload = {
                    "submission_id": submission_id,
                    "course_id": course_uuid,
                    "task_id": task_uuid,
                    "task_kind": task_kind,
                    "student_sub": data.student_sub,
                    "intent": data.intent,
                    "kind": data.kind,
                    "attempt_nr": attempt_nr,
                    "criteria": criteria,
                    "instruction_md": instruction_md,
                    "analysis_mode": analysis_mode,
                }
                if running_under_pytest():
                    # Tag jobs created by in-process tests so a local docker worker
                    # can be configured to ignore them (avoid race conditions).
                    job_payload["_gustav_source"] = "pytest"
                    test_run_id = pytest_test_run_id()
                    if test_run_id:
                        job_payload["_gustav_test_run_id"] = test_run_id
                queue_table = repo._resolve_queue_table(cur)
                insert_sql = sql_module.SQL(
                    "insert into public.{} (submission_id, payload) values (%s::uuid, %s)"
                ).format(sql_module.Identifier(queue_table))
                cur.execute(
                    insert_sql,
                    (
                        submission_id,
                        json_adapter(job_payload) if json_adapter is not None else json_dumps(job_payload),
                    ),
                )
                conn.commit()
            except Exception as exc:
                # If another in-flight request inserted with the same Idempotency-Key, reuse it
                from psycopg import errors as _pg_errors  # type: ignore

                if isinstance(exc, _pg_errors.UniqueViolation):
                    conn.rollback()
                    with conn.cursor() as cur2:
                        # Rollback clears transaction-scoped GUCs; restore RLS context before querying.
                        repo._set_current_sub(cur2, data.student_sub)
                        cur2.execute(
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
                             where course_id = %s::uuid and task_id = %s::uuid and student_sub = %s and idempotency_key = %s
                            """,
                            (course_uuid, task_uuid, data.student_sub, norm_key),
                        )
                        existing = cur2.fetchone()
                    if existing:
                        row = existing
                    else:  # defensive: re-raise if we cannot recover
                        raise
                else:
                    raise
    return repo._row_to_submission(row)

def finalize_latest_feedback_submission(
    repo,
    *,
    psycopg_module,
    json_adapter,
    json_dumps,
    student_sub: str,
    course_id: str,
    task_id: str,
    idempotency_key: str | None,
) -> dict:
    """Persist a final submission by copying the newest completed draft.

    Why:
        The student-facing UX distinguishes between a feedback draft and a
        formal submission. Finalizing must therefore reuse the most recent
        completed draft instead of enqueueing a second analysis run.
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

            norm_key = None
            if idempotency_key and isinstance(idempotency_key, str):
                candidate = idempotency_key.strip()
                norm_key = candidate if candidate else None

            if norm_key:
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
                     where course_id = %s::uuid
                       and task_id = %s::uuid
                       and student_sub = %s
                       and intent = 'submit'
                       and idempotency_key = %s
                    """,
                    (course_uuid, task_uuid, student_sub, norm_key),
                )
                existing = cur.fetchone()
                if existing:
                    return repo._row_to_submission(existing)

            cur.execute(
                """
                select task_id::text,
                       section_id::text,
                       unit_id::text,
                       kind,
                       h5p_content_id,
                       max_attempts
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

            task_kind = str(meta[3] or "native")
            max_attempts = meta[5]
            if task_kind == "h5p":
                raise ValueError("invalid_input")

            if max_attempts is not None:
                cur.execute(
                    """
                    select count(*)
                      from public.learning_submissions
                     where course_id = %s::uuid
                       and task_id = %s::uuid
                       and student_sub = %s
                       and intent = 'submit'
                    """,
                    (course_uuid, task_uuid, student_sub),
                )
                if int(cur.fetchone()[0] or 0) >= int(max_attempts):
                    raise ValueError("max_attempts_exceeded")

            cur.execute(
                """
                select kind,
                       score_raw,
                       score_max,
                       text_body,
                       mime_type,
                       size_bytes,
                       storage_key,
                       sha256,
                       analysis_json,
                       feedback_md,
                       coalesce(vision_attempts, 0),
                       vision_last_error,
                       feedback_last_attempt_at,
                       feedback_last_error,
                       analysis_status
                  from public.learning_submissions
                 where course_id = %s::uuid
                   and task_id = %s::uuid
                   and student_sub = %s
                   and intent = 'feedback'
                 order by created_at desc, attempt_nr desc
                 limit 1
                """,
                (course_uuid, task_uuid, student_sub),
            )
            latest_draft = cur.fetchone()
            if not latest_draft:
                raise LookupError("draft_missing")
            if str(latest_draft[14] or "") != "completed":
                raise RuntimeError("draft_not_ready")

            cur.execute(
                "select public.next_attempt_nr(%s, %s, %s)",
                (course_uuid, task_uuid, student_sub),
            )
            attempt_nr = int(cur.fetchone()[0])

            deterministic_id = None
            if norm_key:
                deterministic_id = str(
                    uuid5(
                        UUID("00000000-0000-0000-0000-000000000002"),
                        f"{course_uuid}:{task_uuid}:{student_sub}:{norm_key}",
                    )
                )

            cur.execute(
                """
                insert into public.learning_submissions (
                    id,
                    course_id,
                    task_id,
                    section_id,
                    student_sub,
                    intent,
                    kind,
                    score_raw,
                    score_max,
                    text_body,
                    storage_key,
                    mime_type,
                    size_bytes,
                    sha256,
                    attempt_nr,
                    analysis_status,
                    analysis_json,
                    feedback_md,
                    error_code,
                    vision_attempts,
                    vision_last_error,
                    feedback_last_attempt_at,
                    feedback_last_error,
                    idempotency_key,
                    completed_at
                )
                values (
                    coalesce(%s::uuid, gen_random_uuid()),
                    %s::uuid,
                    %s::uuid,
                    %s::uuid,
                    %s,
                    'submit',
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    'completed',
                    %s::jsonb,
                    %s,
                    null,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    now()
                )
                on conflict (course_id, task_id, student_sub, idempotency_key)
                do nothing
                returning id::text,
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
                """,
                (
                    deterministic_id,
                    course_uuid,
                    task_uuid,
                    section_uuid,
                    student_sub,
                    latest_draft[0],
                    latest_draft[1],
                    latest_draft[2],
                    latest_draft[3],
                    latest_draft[6],
                    latest_draft[4],
                    latest_draft[5],
                    latest_draft[7],
                    attempt_nr,
                    json_adapter(latest_draft[8]) if json_adapter is not None else json_dumps(latest_draft[8]),
                    latest_draft[9],
                    latest_draft[10],
                    latest_draft[11],
                    latest_draft[12],
                    latest_draft[13],
                    norm_key,
                ),
            )
            row = cur.fetchone()
            if row is None and norm_key:
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
                     where course_id = %s::uuid
                       and task_id = %s::uuid
                       and student_sub = %s
                       and intent = 'submit'
                       and idempotency_key = %s
                    """,
                    (course_uuid, task_uuid, student_sub, norm_key),
                )
                row = cur.fetchone()
            conn.commit()

    return repo._row_to_submission(row)
