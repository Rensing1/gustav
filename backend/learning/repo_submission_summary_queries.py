"""Task submission summary queries for the Learning repository."""

from __future__ import annotations

from typing import Any, Callable, Sequence
from uuid import UUID


def task_submission_summary_map(
    conn,
    *,
    student_sub: str,
    course_id: str,
    task_ids: Sequence[str],
    set_current_sub: Callable[[Any, str], None],
    set_current_course_id: Callable[[Any, str], None],
) -> dict[str, dict[str, Any]]:
    """Return lightweight latest-submission metadata per task for learner UI."""

    if not task_ids:
        return {}

    uuid_ids = [UUID(task_id) for task_id in task_ids]
    with conn.cursor() as cur:
        set_current_sub(cur, student_sub)
        set_current_course_id(cur, course_id)
        cur.execute(
            """
            with latest as (
                select distinct on (task_id)
                       task_id::text,
                       intent,
                       analysis_status,
                       to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"') as created_at_iso
                  from public.learning_submissions
                 where course_id = %s::uuid
                   and student_sub = %s
                   and task_id = any(%s::uuid[])
                 order by task_id, created_at desc, attempt_nr desc
            ),
            finals as (
                select task_id::text,
                       to_char(max(created_at) at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"') as final_created_at_iso
                  from public.learning_submissions
                 where course_id = %s::uuid
                   and student_sub = %s
                   and intent = 'submit'
                   and task_id = any(%s::uuid[])
                 group by task_id
            )
            select latest.task_id,
                   latest.intent,
                   latest.analysis_status,
                   latest.created_at_iso,
                   finals.final_created_at_iso
              from latest
         left join finals on finals.task_id = latest.task_id
            """,
            (course_id, student_sub, uuid_ids, course_id, student_sub, uuid_ids),
        )
        rows = cur.fetchall() or []

    summary: dict[str, dict[str, Any]] = {}
    for row in rows:
        summary[str(row[0])] = {
            "has_submission": True,
            "latest_submission_intent": row[1],
            "latest_submission_analysis_status": row[2],
            "latest_submission_created_at": row[3],
            "latest_final_submission_at": row[4],
        }
    return summary
