"""Live-dashboard SQL queries for the Teaching repository.

Why:
    DBTeachingRepo remains the public facade, but live dashboard read models are
    large enough to deserve their own module. The functions here are deliberately
    DB-shaped and receive the DSN and psycopg module from the facade.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List, Sequence

from backend.teaching.errors import TeachingRepositoryUnavailable
from backend.teaching.repo_row_mappers import compute_average_score_from_analysis as _compute_average_score_from_analysis


def _safe_int(value: object) -> int | None:
    try:
        return int(value)
    except Exception:
        return None


def list_unit_latest_submission_aggregates_for_owner(
    *,
    dsn: str,
    psycopg_module,
    course_id: str,
    unit_id: str,
    owner_sub: str,
    student_subs: Sequence[str],
) -> List[dict]:
    """Return latest submission aggregates for one unit and an explicit learner page.

    Why:
        The live unit summary paginates by learners. Fetching aggregates for
        the exact learner page avoids truncating later learners when the unit
        contains many tasks.
    """
    normalized_student_subs = [str(student_sub) for student_sub in student_subs if str(student_sub or "").strip()]
    if not normalized_student_subs:
        return []

    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (owner_sub,))
            cur.execute(
                """
                select student_sub::text,
                       task_id::text,
                       submission_id::text,
                       analysis_status::text,
                       analysis_json,
                       score_raw,
                       score_max,
                       created_at_iso,
                       completed_at_iso,
                       h5p_completed
                  from public.get_unit_latest_submission_aggregates_for_owner(
                       %s, %s, %s, %s
                  )
                """,
                (owner_sub, course_id, unit_id, normalized_student_subs),
            )
            rows = cur.fetchall() or []

    aggregates: List[dict] = []
    for row in rows:
        analysis_status = str(row[3] or "")
        analysis_json = row[4]
        average_score = None
        if analysis_status == "completed":
            average_score = _compute_average_score_from_analysis(analysis_json)
        aggregates.append(
            {
                "student_sub": str(row[0] or ""),
                "task_id": str(row[1] or ""),
                "submission_id": str(row[2] or "") if row[2] else None,
                "has_submission": bool(row[2]),
                "average_score": average_score,
                "score_raw": int(row[5]) if row[5] is not None else None,
                "score_max": int(row[6]) if row[6] is not None else None,
                "created_at_iso": str(row[7] or "") if row[7] else None,
                "completed_at_iso": str(row[8] or "") if row[8] else None,
                "h5p_completed": bool(row[9]) if row[9] is not None else None,
            }
        )
    return aggregates

def list_unit_live_helper_rows(
    *,
    dsn: str,
    psycopg_module,
    owner_sub: str,
    course_id: str,
    unit_id: str,
    updated_since_dt: datetime | None,
    limit: int,
    offset: int,
) -> list[dict[str, Any]]:
    """Load live helper rows for a unit with compatibility fallback.

    Why:
        The dashboard endpoint uses a SECURITY DEFINER helper that may
        expose `score_raw/score_max` only in newer DB migrations.
        This method probes both shapes and returns normalized rows.
    """
    current_sql = """
        select student_sub::text,
               task_id::text,
               submission_id::text,
               score_raw,
               score_max,
               created_at_iso,
               completed_at_iso,
               h5p_completed
          from public.get_unit_latest_submissions_for_owner(%s, %s, %s, %s, %s, %s)
    """
    legacy_sql = """
        select student_sub::text,
               task_id::text,
               submission_id::text,
               null::integer as score_raw,
               null::integer as score_max,
               created_at_iso,
               completed_at_iso,
               h5p_completed
          from public.get_unit_latest_submissions_for_owner(%s, %s, %s, %s, %s, %s)
    """

    params = (owner_sub, course_id, unit_id, updated_since_dt, int(limit), int(offset))

    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (owner_sub,))
            last_exc: Exception | None = None

            cur.execute("savepoint live_helper_compat")
            for idx, sql in enumerate((current_sql, legacy_sql)):
                if idx > 0:
                    cur.execute("rollback to savepoint live_helper_compat")
                try:
                    cur.execute(sql, params)
                    rows = cur.fetchall() or []
                    cur.execute("release savepoint live_helper_compat")
                    return [
                        {
                            "student_sub": str(raw_student),
                            "task_id": str(raw_task_id),
                            "submission_id": str(raw_submission_id) if raw_submission_id else None,
                            "score_raw": _safe_int(raw_score_raw),
                            "score_max": _safe_int(raw_score_max),
                            "created_at_iso": str(raw_created_at_iso) if raw_created_at_iso else None,
                            "completed_at_iso": str(raw_completed_at_iso) if raw_completed_at_iso else None,
                            "h5p_completed": bool(raw_h5p_completed) if raw_h5p_completed is not None else None,
                        }
                        for (
                            raw_student,
                            raw_task_id,
                            raw_submission_id,
                            raw_score_raw,
                            raw_score_max,
                            raw_created_at_iso,
                            raw_completed_at_iso,
                            raw_h5p_completed,
                        ) in rows
                    ]
                except Exception as exc:
                    last_exc = exc

            try:
                cur.execute("rollback to savepoint live_helper_compat")
            except Exception:
                pass
            try:
                cur.execute("release savepoint live_helper_compat")
            except Exception:
                pass

            if last_exc is not None:
                raise last_exc
            raise RuntimeError("live helper compatibility probe failed")

def list_unit_live_submission_state_by_task(
    *,
    dsn: str,
    psycopg_module,
    owner_sub: str,
    course_id: str,
    task_ids_by_student: dict[str, list[str]],
) -> dict[tuple[str, str], dict[str, Any]]:
    """Load latest submission state for each `(student_sub, task_id)` pair."""
    if not task_ids_by_student:
        return {}

    out: dict[tuple[str, str], dict[str, Any]] = {}
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            try:
                for student_sub, task_ids in task_ids_by_student.items():
                    if not task_ids:
                        continue
                    cur.execute("select set_config('app.current_sub', %s, true)", (student_sub,))
                    cur.execute(
                        """
                        select distinct on (task_id)
                               task_id::text,
                               id::text,
                               score_raw,
                               score_max,
                               greatest(created_at, coalesce(completed_at, created_at))
                          from public.learning_submissions
                         where course_id = %s
                           and task_id = any(%s)
                         order by task_id, created_at desc, attempt_nr desc, id desc
                        """,
                        (course_id, task_ids),
                    )
                    for raw_task_id, raw_submission_id, raw_score_raw, raw_score_max, raw_changed_at in (cur.fetchall() or []):
                        out[(student_sub, str(raw_task_id))] = {
                            "submission_id": str(raw_submission_id) if raw_submission_id else None,
                            "score_raw": _safe_int(raw_score_raw),
                            "score_max": _safe_int(raw_score_max),
                            "changed_at": raw_changed_at,
                        }
            finally:
                cur.execute("select set_config('app.current_sub', %s, true)", (owner_sub,))

    return out

def list_unit_live_average_scores_by_submission_id(
    *,
    dsn: str,
    psycopg_module,
    owner_sub: str,
    submission_ids_by_student: dict[str, list[str]],
) -> dict[str, float | None]:
    """Load average scores for completed analyses keyed by submission id."""
    if not submission_ids_by_student:
        return {}

    out: dict[str, float | None] = {}
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            try:
                for student_sub, submission_ids in submission_ids_by_student.items():
                    if not submission_ids:
                        continue
                    cur.execute("select set_config('app.current_sub', %s, true)", (student_sub,))
                    cur.execute(
                        """
                        select id::text, analysis_status::text, analysis_json
                          from public.learning_submissions
                         where id = any(%s)
                        """,
                        (submission_ids,),
                    )
                    for raw_submission_id, raw_analysis_status, raw_analysis_json in cur.fetchall() or []:
                        if str(raw_analysis_status or "") != "completed":
                            out[str(raw_submission_id)] = None
                        else:
                            out[str(raw_submission_id)] = _compute_average_score_from_analysis(raw_analysis_json)
            finally:
                cur.execute("select set_config('app.current_sub', %s, true)", (owner_sub,))

    return out

def list_unit_live_summary_fallback_rows(
    *,
    dsn: str,
    psycopg_module,
    owner_sub: str,
    course_id: str,
    task_ids: list[str],
    member_subs: list[str],
) -> list[tuple[str, str, str]]:
    """Fallback summary rows: latest submission time per learner-task pair."""
    if not task_ids or not member_subs:
        return []

    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (owner_sub,))
            cur.execute(
                """
                select distinct on (student_sub, task_id)
                       student_sub::text,
                       task_id::text,
                       to_char(
                           greatest(created_at, coalesce(completed_at, created_at)) at time zone 'utc',
                           'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'
                       )
                  from public.learning_submissions
                 where course_id = %s
                   and task_id = any(%s)
                   and student_sub = any(%s)
                 order by student_sub, task_id, created_at desc, attempt_nr desc, id desc
                """,
                (course_id, task_ids, member_subs),
            )
            return [
                (str(raw_student), str(raw_task_id), str(raw_created_at_iso or ""))
                for raw_student, raw_task_id, raw_created_at_iso in (cur.fetchall() or [])
            ]

def list_unit_live_task_ids_for_student(
    *,
    dsn: str,
    psycopg_module,
    owner_sub: str,
    course_id: str,
    student_sub: str,
    task_ids: list[str],
) -> list[tuple[str, str]]:
    """Fallback summary rows for one learner: latest per-task timestamp."""
    if not task_ids:
        return []

    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (student_sub,))
            cur.execute(
                """
                select distinct on (task_id)
                       task_id::text,
                       to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
                  from public.learning_submissions
                 where course_id = %s
                   and student_sub = %s
                   and task_id = any(%s)
                 order by task_id, created_at desc, attempt_nr desc, id desc
                """,
                (course_id, student_sub, task_ids),
            )
            return [
                (str(raw_task_id), str(raw_created_at_iso or ""))
                for raw_task_id, raw_created_at_iso in (cur.fetchall() or [])
            ]

def list_unit_live_latest_changed_at_by_pairs(
    *,
    dsn: str,
    psycopg_module,
    owner_sub: str,
    course_id: str,
    task_ids_by_student: dict[str, list[str]],
) -> dict[tuple[str, str], Any]:
    """Latest changed timestamp for requested learner-task pairs."""
    if not task_ids_by_student:
        return {}

    students: list[str] = []
    task_ids: list[str] = []
    for student_sub, raw_task_ids in task_ids_by_student.items():
        if not student_sub:
            continue
        students.append(str(student_sub))
        task_ids.extend([str(task_id) for task_id in raw_task_ids if str(task_id)])

    if not students or not task_ids:
        return {}

    out: dict[tuple[str, str], Any] = {}
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (owner_sub,))
            cur.execute(
                """
                select student_sub::text,
                       task_id::text,
                       max(greatest(created_at, coalesce(completed_at, created_at)))
                  from public.learning_submissions
                 where course_id = %s
                   and student_sub = any(%s)
                   and task_id = any(%s)
                 group by student_sub, task_id
                """,
                (course_id, students, task_ids),
            )
            for raw_student_sub, raw_task_id, raw_changed_at in cur.fetchall() or []:
                out[(str(raw_student_sub), str(raw_task_id))] = raw_changed_at
    return out

def list_unit_live_delta_fallback_rows(
    *,
    dsn: str,
    psycopg_module,
    owner_sub: str,
    course_id: str,
    changed_since: datetime,
    limit: int,
    offset: int,
) -> list[tuple[str, str, Any]]:
    """Fallback changed cells when live helper projection cannot run."""
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (owner_sub,))
            cur.execute(
                """
                select distinct student_sub::text,
                               task_id::text,
                               greatest(created_at, coalesce(completed_at, created_at)) as changed_ts
                  from public.learning_submissions
                 where course_id = %s
                   and greatest(created_at, coalesce(completed_at, created_at)) > %s
                 order by changed_ts desc
                 limit %s offset %s
                """,
                (course_id, changed_since, int(limit), int(offset)),
            )
            return [
                (str(raw_student_sub), str(raw_task_id), raw_changed_ts)
                for raw_student_sub, raw_task_id, raw_changed_ts in (cur.fetchall() or [])
            ]

def get_statement_timestamp(*, dsn: str, psycopg_module, owner_sub: str) -> str | None:
    """Read DB timestamp for live-dashboard cursor seeding."""
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (owner_sub,))
            cur.execute("select statement_timestamp()")
            row = cur.fetchone()
    if row and row[0] is not None:
        return row[0].astimezone(timezone.utc).isoformat(timespec="microseconds")
    return None


def get_latest_submission_for_owner(
    *,
    dsn: str,
    psycopg_module,
    owner_sub: str,
    course_id: str,
    unit_id: str,
    task_id: str,
    student_sub: str,
) -> dict[str, Any] | None:
    """Return the owner-scoped task and latest submission read projection.

    Why:
        The Teaching web adapter must not open database cursors itself. Keeping
        this query at the repository boundary ensures PostgreSQL connection
        failures are translated into ``TeachingRepositoryUnavailable`` by the
        public ``DBTeachingRepo`` facade.

    Permissions:
        ``owner_sub`` must own ``course_id``. The task must belong to ``unit_id``
        and the unit must be attached to the course. The required SECURITY
        DEFINER helper repeats those checks and verifies current membership.

    Behavior:
        A missing helper means that the required production migration is not
        available. It is reported as ``TeachingRepositoryUnavailable`` instead
        of bypassing the helper with a direct table query.
    """

    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (owner_sub,))
            cur.execute(
                """
                select t.kind::text,
                       t.instruction_md,
                       t.h5p_content_id::text
                  from public.unit_tasks t
                  join public.unit_sections s on s.id = t.section_id
                  join public.course_modules m on m.unit_id = s.unit_id
                 where m.course_id = %s
                   and s.unit_id = %s::uuid
                   and t.id = %s::uuid
                 limit 1
                """,
                (course_id, unit_id, task_id),
            )
            task_row = cur.fetchone()
            if task_row is None:
                return None

            params = (owner_sub, course_id, unit_id, task_id, student_sub)
            helper_sql = """
                select id::text,
                       task_id::text,
                       student_sub::text,
                       created_at,
                       completed_at,
                       kind,
                       score_raw,
                       score_max,
                       text_body,
                       mime_type,
                       size_bytes,
                       storage_key,
                       feedback_md,
                       analysis_json
                  from public.get_latest_submission_for_owner(%s, %s, %s, %s, %s)
            """
            try:
                cur.execute(helper_sql, params)
            except psycopg_module.errors.UndefinedFunction as exc:
                # The helper is part of the production schema contract. Falling
                # back to the table would change authorization semantics under
                # different database roles.
                raise TeachingRepositoryUnavailable() from exc
            submission_row = cur.fetchone()

    task_kind, instruction_md, h5p_content_id = task_row
    return {
        "task_kind": task_kind,
        "instruction_md": instruction_md,
        "h5p_content_id": h5p_content_id,
        "submission": submission_row,
    }


def get_latest_submission_file_for_owner(
    *,
    dsn: str,
    psycopg_module,
    owner_sub: str,
    course_id: str,
    unit_id: str,
    task_id: str,
    student_sub: str,
) -> tuple[Any, Any, Any] | None:
    """Return owner-visible file metadata for the latest submission.

    Permissions:
        The caller must own the course. The SECURITY DEFINER helper validates
        the course, unit, task and learner relation before returning metadata.

    Behavior:
        A missing helper is an unavailable required migration, matching the
        detail projection's ``TeachingRepositoryUnavailable`` contract.
    """

    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (owner_sub,))
            cur.execute(
                """
                select exists(
                         select 1
                           from public.course_modules
                          where course_id = %s
                            and unit_id = %s::uuid
                     )
                """,
                (course_id, unit_id),
            )
            if not bool((cur.fetchone() or [False])[0]):
                return None
            try:
                cur.execute(
                    """
                    select s.mime_type,
                           s.size_bytes,
                           s.storage_key
                      from public.get_latest_submission_for_owner(%s, %s, %s, %s, %s) s
                     where s.id::text is not null
                     limit 1
                    """,
                    (owner_sub, course_id, unit_id, task_id, student_sub),
                )
            except psycopg_module.errors.UndefinedFunction as exc:
                raise TeachingRepositoryUnavailable() from exc
            return cur.fetchone()
