"""AI usage SQL queries for the Teaching repository.

Why:
    DBTeachingRepo remains the public facade, but owner-scoped AI usage events
    are an analytics read model with separate filtering concerns.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


def list_ai_usage_events_for_owner(
    *,
    dsn: str,
    psycopg_module,
    course_id: str,
    owner_sub: str,
    from_at: datetime | None = None,
    to_at: datetime | None = None,
    unit_id: str | None = None,
    task_id: str | None = None,
    student_sub: str | None = None,
) -> list[dict[str, Any]]:
    """Return owner-scoped, database-aggregated AI usage rows.

    Why:
        The API read-model needs flexible grouping, but no SECURITY DEFINER
        aggregate helper. This method sets `app.current_sub` and reads the
        RLS-protected event table directly.

    Security:
        Caller must be the course owner. SQL repeats the owner guard and
        RLS enforces the same boundary on `ai_usage_events`.
    """
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (owner_sub,))
            cur.execute(
                """
                with unified_usage as (
                    select e.student_sub,
                           e.model,
                           e.stage,
                           e.modality,
                           e.call_kind,
                           e.usage_known,
                           e.input_tokens,
                           e.output_tokens,
                           e.total_tokens
                      from public.ai_usage_events e
                      join public.courses c on c.id = e.course_id
                     where e.course_id = %s::uuid
                       and c.teacher_id = coalesce(current_setting('app.current_sub', true), '')
                       and (%s::timestamptz is null or e.occurred_at >= %s::timestamptz)
                       and (%s::timestamptz is null or e.occurred_at < %s::timestamptz)
                       and (%s::text is null or e.unit_id::text = %s::text)
                       and (%s::text is null or e.task_id::text = %s::text)
                       and (%s::text is null or e.student_sub = %s::text)

                    union all

                    select e.actor_sub as student_sub,
                           e.model,
                           e.stage,
                           'text'::text as modality,
                           'dialog_generation'::text as call_kind,
                           e.usage_known,
                           e.input_tokens,
                           e.output_tokens,
                           e.total_tokens
                      from public.dialog_ai_usage_events e
                      join public.courses c on c.id = e.course_id
                     where e.course_id = %s::uuid
                       and e.actor_role = 'student'
                       and c.teacher_id = coalesce(current_setting('app.current_sub', true), '')
                       and (%s::timestamptz is null or e.occurred_at >= %s::timestamptz)
                       and (%s::timestamptz is null or e.occurred_at < %s::timestamptz)
                       and (%s::text is null or e.unit_id::text = %s::text)
                       and (%s::text is null or e.task_id::text = %s::text)
                       and (%s::text is null or e.actor_sub = %s::text)
                )
                select student_sub,
                       model,
                       stage,
                       modality,
                       call_kind,
                       coalesce(sum(input_tokens), 0)::bigint as input_tokens,
                       coalesce(sum(output_tokens), 0)::bigint as output_tokens,
                       coalesce(sum(total_tokens), 0)::bigint as total_tokens,
                       count(*) filter (where usage_known)::bigint as known_events,
                       count(*) filter (where not usage_known)::bigint as unknown_events
                  from unified_usage
                 group by student_sub, model, stage, modality, call_kind
                 order by student_sub, model, stage, modality, call_kind
                """,
                (
                    course_id,
                    from_at,
                    from_at,
                    to_at,
                    to_at,
                    unit_id,
                    unit_id,
                    task_id,
                    task_id,
                    student_sub,
                    student_sub,
                    course_id,
                    from_at,
                    from_at,
                    to_at,
                    to_at,
                    unit_id,
                    unit_id,
                    task_id,
                    task_id,
                    student_sub,
                    student_sub,
                ),
            )
            rows = cur.fetchall() or []
    return [
        {
            "student_sub": r[0],
            "model": r[1],
            "stage": r[2],
            "modality": r[3],
            "call_kind": r[4],
            "input_tokens": r[5],
            "output_tokens": r[6],
            "total_tokens": r[7],
            "known_events": int(r[8]),
            "unknown_events": int(r[9]),
        }
        for r in rows
    ]
