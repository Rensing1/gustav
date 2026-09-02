"""Task SQL queries for the Teaching repository.

Why:
    DBTeachingRepo remains the public facade, but task authoring and
    course-scoped task read models form a distinct DB surface. The functions here
    receive the DSN and psycopg module from the facade.
"""

from __future__ import annotations

import json
from typing import Any, List, Optional, Sequence

from backend.teaching.repo_row_mappers import (
    compute_average_score_from_analysis as _compute_average_score_from_analysis,
    TASK_COLUMNS_SQL as _TASK_COLUMNS_SQL,
    task_row_to_dict as _task_row_to_dict,
)

_UNSET = object()


def _is_unset(value: object) -> bool:
    """Accept unset sentinels from DBTeachingRepo and this module."""
    if value is _UNSET:
        return True
    return value.__class__ is object


def _dialog_config_row_to_dict(row: Sequence[object]) -> dict[str, Any]:
    """Map a dialog config row without exposing persistence metadata."""

    return {
        "partner_name": row[1],
        "partner_description_md": row[2],
        "role_md": row[3],
        "learning_goal_md": row[4],
        "opening_message_md": row[5],
        "response_mode": row[6],
        "max_rounds": int(row[7]),
        "closing_prompt_md": row[8],
    }


def _load_dialog_configs(cur, task_ids: Sequence[str]) -> dict[str, dict[str, Any]]:
    """Load all dialog configs for a task list in one query (avoids N+1)."""

    if not task_ids:
        return {}
    cur.execute(
        """
        select task_id::text, partner_name, partner_description_md, role_md,
               learning_goal_md, opening_message_md, response_mode,
               max_rounds, closing_prompt_md
        from public.unit_task_dialog_configs
        where task_id = any(%s::uuid[])
        """,
        (list(task_ids),),
    )
    return {str(row[0]): _dialog_config_row_to_dict(row) for row in (cur.fetchall() or [])}


def _store_dialog_config(cur, task_id: str, config: dict[str, Any]) -> None:
    """Persist the validated 1:1 dialog configuration in the current transaction."""

    cur.execute(
        """
        insert into public.unit_task_dialog_configs (
          task_id, partner_name, partner_description_md, role_md,
          learning_goal_md, opening_message_md, response_mode,
          max_rounds, closing_prompt_md
        ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        on conflict (task_id) do update set
          partner_name = excluded.partner_name,
          partner_description_md = excluded.partner_description_md,
          role_md = excluded.role_md,
          learning_goal_md = excluded.learning_goal_md,
          opening_message_md = excluded.opening_message_md,
          response_mode = excluded.response_mode,
          max_rounds = excluded.max_rounds,
          closing_prompt_md = excluded.closing_prompt_md,
          updated_at = now()
        """,
        (
            task_id,
            config["partner_name"],
            config["partner_description_md"],
            config["role_md"],
            config["learning_goal_md"],
            config["opening_message_md"],
            config["response_mode"],
            config["max_rounds"],
            config.get("closing_prompt_md"),
        ),
    )


def get_dialog_task_for_author(*, dsn: str, psycopg_module, unit_id: str, task_id: str, author_id: str) -> dict[str, Any] | None:
    """Return the latest saved dialog config for a stateless author preview."""

    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
            cur.execute(
                """
                select d.task_id::text, d.partner_name, d.partner_description_md,
                       d.role_md, d.learning_goal_md, d.opening_message_md,
                       d.response_mode, d.max_rounds, d.closing_prompt_md,
                       t.instruction_md, t.teacher_context_md
                  from public.unit_task_dialog_configs d
                  join public.unit_tasks t on t.id=d.task_id
                 where d.task_id=%s::uuid and t.unit_id=%s::uuid and t.kind='dialog'
                """,
                (task_id, unit_id),
            )
            row = cur.fetchone()
    if not row:
        return None
    config = _dialog_config_row_to_dict(row[:9])
    config.update({"instruction_md": row[9], "teacher_context_md": row[10], "turns": []})
    return config


def get_dialog_submission_for_owner(*, dsn: str, psycopg_module, course_id: str, unit_id: str, task_id: str, student_sub: str, submission_id: str, author_id: str) -> dict[str, Any] | None:
    """Return a safe completed transcript; the DB function performs owner checks."""

    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
            cur.execute(
                "select public.teaching_get_dialog_submission(%s::uuid,%s::uuid,%s::uuid,%s,%s::uuid)",
                (course_id, unit_id, task_id, student_sub, submission_id),
            )
            row = cur.fetchone()
    if not row or row[0] is None:
        return None
    parsed = json.loads(row[0]) if isinstance(row[0], str) else row[0]
    return dict(parsed) if isinstance(parsed, dict) else None


def record_dialog_preview_usage(*, dsn: str, psycopg_module, unit_id: str, task_id: str, author_id: str, events: Sequence[Any]) -> None:
    """Store content-free preview usage for an authored dialog task."""

    if not events:
        return
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
            for event in events:
                cur.execute(
                    """
                    insert into public.dialog_ai_usage_events (
                      event_key, unit_id, task_id, actor_sub, actor_role, stage,
                      model, usage_known, input_tokens, output_tokens,
                      total_tokens, unknown_reason, error_code
                    ) values (%s::uuid,%s::uuid,%s::uuid,%s,'teacher','preview',%s,%s,%s,%s,%s,%s,%s)
                    on conflict (event_key) do nothing
                    """,
                    (
                        event.event_key, unit_id, task_id, author_id, event.model,
                        event.usage_known, event.input_tokens, event.output_tokens,
                        event.total_tokens, event.unknown_reason,
                        getattr(event, "error_code", None),
                    ),
                )
            conn.commit()


def list_tasks_for_section_owned(*, dsn: str, psycopg_module, unit_id: str, section_id: str, author_id: str) -> List[dict]:
    """Return ordered tasks for a section authored by the caller."""
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
            cur.execute(
                f"""
                select {_TASK_COLUMNS_SQL}
                from public.unit_tasks
                where unit_id = %s
                  and section_id = %s
                order by position asc, id
                """,
                (unit_id, section_id),
            )
            rows = cur.fetchall() or []
            tasks = [_task_row_to_dict(row) for row in rows]
            configs = _load_dialog_configs(cur, [task["id"] for task in tasks if task["kind"] == "dialog"])
            for task in tasks:
                task["dialog"] = configs.get(task["id"])
    return tasks

def create_task(
    *,
    dsn: str,
    psycopg_module,
    json_adapter,
    unit_id: str,
    section_id: str,
    author_id: str,
    instruction_md: str,
    criteria: List[str],
    teacher_context_md: str | None,
    model_solution_md: str | None = None,
    due_at,
    max_attempts: int | None,
    kind: str,
    h5p_content_id: str | None,
    h5p_display_options: dict[str, Any],
    dialog_config: dict[str, Any] | None = None,
) -> dict:
    """Create a task at the next position within the section."""
    if not instruction_md or not isinstance(instruction_md, str):
        raise ValueError("invalid_instruction_md")
    instruction = instruction_md.strip()
    if not instruction:
        raise ValueError("invalid_instruction_md")
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
            cur.execute(
                "select id from public.unit_sections where id = %s and unit_id = %s for update",
                (section_id, unit_id),
            )
            sec_row = cur.fetchone()
            if not sec_row:
                raise LookupError("section_not_found")
            cur.execute(
                "select id from public.unit_tasks where section_id = %s for update",
                (section_id,),
            )
            cur.execute(
                "select coalesce(max(position), 0) + 1 from public.unit_tasks where section_id = %s",
                (section_id,),
            )
            next_pos = int(cur.fetchone()[0])
            cur.execute(
                f"""
                insert into public.unit_tasks (
                  unit_id,
                  section_id,
                  instruction_md,
                  criteria,
                  teacher_context_md,
                  model_solution_md,
                  due_at,
                  max_attempts,
                  position,
                  kind,
                  h5p_content_id,
                  h5p_display_options
                )
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                returning {_TASK_COLUMNS_SQL}
                """,
                (
                    unit_id,
                    section_id,
                    instruction,
                    criteria,
                    teacher_context_md,
                    model_solution_md,
                    due_at,
                    max_attempts,
                    next_pos,
                    kind,
                    h5p_content_id,
                    json_adapter(h5p_display_options) if json_adapter is not None else json.dumps(h5p_display_options),
                ),
            )
            row = cur.fetchone()
            if not row:
                raise RuntimeError("unit_tasks insert returned no row")
            task = _task_row_to_dict(row)
            if kind == "dialog":
                if dialog_config is None:
                    raise ValueError("invalid_dialog_config")
                _store_dialog_config(cur, task["id"], dialog_config)
                task["dialog"] = dict(dialog_config)
            conn.commit()
    return task

def update_task(
    *,
    dsn: str,
    psycopg_module,
    json_adapter,
    unit_id: str,
    section_id: str,
    task_id: str,
    author_id: str,
    instruction_md=_UNSET,
    criteria=_UNSET,
    teacher_context_md=_UNSET,
    model_solution_md=_UNSET,
    due_at=_UNSET,
    max_attempts=_UNSET,
    kind=_UNSET,
    h5p_content_id=_UNSET,
    h5p_display_options=_UNSET,
    dialog_config=_UNSET,
) -> Optional[dict]:
    """Update mutable task fields when owned by the caller."""
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
            cur.execute(
                f"""
                select {_TASK_COLUMNS_SQL}
                from public.unit_tasks
                where id = %s
                  and unit_id = %s
                  and section_id = %s
                for update
                """,
                (task_id, unit_id, section_id),
            )
            existing = cur.fetchone()
            if not existing:
                return None
            updates = []
            params: List[object] = []
            if not _is_unset(instruction_md):
                updates.append("instruction_md")
                params.append(instruction_md)
            if not _is_unset(criteria):
                updates.append("criteria")
                params.append(criteria)
            if not _is_unset(teacher_context_md):
                updates.append("teacher_context_md")
                params.append(teacher_context_md)
            if not _is_unset(model_solution_md):
                updates.append("model_solution_md")
                params.append(model_solution_md)
            if not _is_unset(due_at):
                updates.append("due_at")
                params.append(due_at)
            if not _is_unset(max_attempts):
                updates.append("max_attempts")
                params.append(max_attempts)
            if not _is_unset(kind):
                updates.append("kind")
                params.append(kind)
            if not _is_unset(h5p_content_id):
                updates.append("h5p_content_id")
                params.append(h5p_content_id)
            if not _is_unset(h5p_display_options):
                updates.append("h5p_display_options")
                params.append(
                    json_adapter(h5p_display_options) if json_adapter is not None else json.dumps(h5p_display_options)
                )
            row = existing
            if updates:
                try:
                    _sql = psycopg_module.sql

                    assignments = [_sql.SQL("{} = %s").format(_sql.Identifier(col)) for col in updates]
                    params.extend([task_id, unit_id, section_id])
                    stmt = _sql.SQL(
                        f"""
                        update public.unit_tasks
                        set {{assign}}
                        where id = %s
                          and unit_id = %s
                          and section_id = %s
                        returning {_TASK_COLUMNS_SQL}
                        """
                    ).format(assign=_sql.SQL(", ").join(assignments))
                    cur.execute(stmt, params)
                except Exception:
                    params = list(params[:-3]) + [task_id, unit_id, section_id]
                    cols = ", ".join([f"{col} = %s" for col in updates])
                    cur.execute(
                        f"""
                        update public.unit_tasks
                        set {cols}
                        where id = %s
                          and unit_id = %s
                          and section_id = %s
                        returning {_TASK_COLUMNS_SQL}
                        """,
                        params,
                    )
                row = cur.fetchone()
                if not row:
                    conn.rollback()
                    return None
            task = _task_row_to_dict(row)
            if not _is_unset(dialog_config):
                if dialog_config is None:
                    cur.execute("delete from public.unit_task_dialog_configs where task_id = %s", (task_id,))
                else:
                    _store_dialog_config(cur, task_id, dialog_config)
            elif not _is_unset(kind) and kind != "dialog":
                cur.execute("delete from public.unit_task_dialog_configs where task_id = %s", (task_id,))
            if task["kind"] == "dialog":
                task["dialog"] = _load_dialog_configs(cur, [task_id]).get(task_id)
            conn.commit()
    return task

def delete_task(*, dsn: str, psycopg_module, unit_id: str, section_id: str, task_id: str, author_id: str) -> bool:
    """Delete a task and resequence remaining positions."""
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
            cur.execute(
                """
                select id
                from public.unit_tasks
                where id = %s
                  and unit_id = %s
                  and section_id = %s
                for update
                """,
                (task_id, unit_id, section_id),
            )
            row = cur.fetchone()
            if not row:
                return False
            cur.execute(
                "delete from public.unit_tasks where id = %s and unit_id = %s and section_id = %s",
                (task_id, unit_id, section_id),
            )
            cur.execute(
                """
                with ordered as (
                  select id, row_number() over (order by position asc, id) as rn
                  from public.unit_tasks
                  where section_id = %s
                )
                update public.unit_tasks t
                set position = o.rn
                from ordered o
                where t.id = o.id
                """,
                (section_id,),
            )
            conn.commit()
            return True

def reorder_section_tasks(
    *,
    dsn: str,
    psycopg_module,
    unit_id: str,
    section_id: str,
    author_id: str,
    task_ids: List[str],
) -> List[dict]:
    """Atomically reorder tasks owned by the caller."""
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
            cur.execute(
                """
                select id::text
                from public.unit_tasks
                where unit_id = %s
                  and section_id = %s
                order by position asc, id
                """,
                (unit_id, section_id),
            )
            existing = [row[0] for row in (cur.fetchall() or [])]
            if not existing:
                raise ValueError("task_mismatch")
            if set(existing) != set(task_ids) or len(existing) != len(task_ids):
                raise ValueError("task_mismatch")
            cur.execute("set constraints unit_tasks_section_id_position_key deferred")
            orderings = list(range(1, len(task_ids) + 1))
            cur.execute(
                """
                with new_order as (
                  select tid, ord from unnest(%s::uuid[], %s::int[]) as t(tid, ord)
                )
                update public.unit_tasks ut
                set position = n.ord
                from new_order n
                where ut.id = n.tid
                  and ut.section_id = %s
                  and ut.unit_id = %s
                """,
                (task_ids, orderings, section_id, unit_id),
            )
            cur.execute(
                f"""
                select {_TASK_COLUMNS_SQL}
                from public.unit_tasks
                where unit_id = %s
                  and section_id = %s
                order by position asc, id
                """,
                (unit_id, section_id),
            )
            rows = cur.fetchall() or []
            conn.commit()
    return [_task_row_to_dict(r) for r in rows]

def list_latest_submission_aggregates_for_owner(
    *,
    dsn: str,
    psycopg_module,
    course_id: str,
    owner_sub: str,
    student_sub: str,
    unit_ids: Sequence[str],
) -> List[dict]:
    """Return latest submission aggregates for one student across selected units.

    Why:
        The teaching student overview needs only compact task-level status
        information. We first derive the allowed task ids as the course owner
        and then read the student's own submissions under their RLS context.
    """
    normalized_unit_ids = [str(unit_id) for unit_id in unit_ids if str(unit_id or "").strip()]
    if not normalized_unit_ids:
        return []

    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (owner_sub,))
            cur.execute(
                """
                select m.unit_id::text,
                       t.id::text,
                       t.kind::text
                  from public.course_modules m
                  join public.courses c
                    on c.id = m.course_id
                  join public.unit_sections s
                    on s.unit_id = m.unit_id
                  join public.unit_tasks t
                    on t.unit_id = s.unit_id
                   and t.section_id = s.id
                 where m.course_id = %s
                   and m.unit_id = any(%s::uuid[])
                   and c.teacher_id = coalesce(current_setting('app.current_sub', true), '')
                 order by m.position asc, s.position asc, t.position asc, t.id
                """,
                (course_id, normalized_unit_ids),
            )
            task_rows = cur.fetchall() or []
            if not task_rows:
                return []

            unit_ids_by_task: dict[str, str] = {}
            h5p_task_ids: list[str] = []
            for raw_unit_id, raw_task_id, raw_kind in task_rows:
                task_id = str(raw_task_id or "")
                unit_ids_by_task[task_id] = str(raw_unit_id or "")
                if str(raw_kind or "") == "h5p":
                    h5p_task_ids.append(task_id)

            task_ids = list(unit_ids_by_task.keys())
            cur.execute("select set_config('app.current_sub', %s, true)", (student_sub,))
            cur.execute(
                """
                select distinct on (ls.task_id)
                       ls.id::text,
                       ls.task_id::text,
                       ls.analysis_status::text,
                       ls.analysis_json,
                       ls.score_raw,
                       ls.score_max
                  from public.learning_submissions ls
                where ls.course_id = %s
                  and ls.student_sub = %s
                  and ls.task_id = any(%s::uuid[])
                 order by ls.task_id, ls.created_at desc, ls.attempt_nr desc, ls.id desc
                """,
                (course_id, student_sub, task_ids),
            )
            latest_rows = cur.fetchall() or []

            h5p_completed_by_task: dict[str, bool] = {}
            if h5p_task_ids:
                cur.execute(
                    """
                    select ls.task_id::text,
                           bool_or(ls.score_raw = ls.score_max)
                      from public.learning_submissions ls
                     where ls.course_id = %s
                       and ls.student_sub = %s
                       and ls.task_id = any(%s::uuid[])
                       and ls.kind = 'h5p'
                     group by ls.task_id
                    """,
                    (course_id, student_sub, h5p_task_ids),
                )
                h5p_rows = cur.fetchall() or []
                h5p_completed_by_task = {str(task_id): bool(completed) for task_id, completed in h5p_rows}

            cur.execute("select set_config('app.current_sub', %s, true)", (owner_sub,))

    aggregates: list[dict] = []
    for _submission_id, task_id, analysis_status, analysis_json, score_raw, score_max in latest_rows:
        avg_score = None
        if str(analysis_status or "") == "completed":
            avg_score = _compute_average_score_from_analysis(analysis_json)
        aggregates.append(
            {
                "unit_id": unit_ids_by_task.get(str(task_id), ""),
                "task_id": str(task_id),
                "has_submission": True,
                "average_score": avg_score,
                "h5p_completed": h5p_completed_by_task.get(str(task_id)),
                "score_raw": score_raw,
                "score_max": score_max,
            }
        )
    return aggregates

def list_tasks_for_course_unit_owner(*, dsn: str, psycopg_module, course_id: str, unit_id: str, owner_sub: str) -> List[dict]:
    """Return course-attached tasks for one unit in deterministic display order.

    Why:
        The student overview is course-scoped, not author-scoped. We therefore
        validate the `course x unit` relation via `course_modules` and project
        tasks in section/task order without relying on author-only methods.
    """
    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (owner_sub,))
            cur.execute(
                """
                select t.id::text,
                       t.instruction_md,
                       row_number() over (order by s.position asc, t.position asc, t.id) as position,
                       t.kind::text
                  from public.course_modules m
                  join public.courses c
                    on c.id = m.course_id
                  join public.unit_sections s
                    on s.unit_id = m.unit_id
                  join public.unit_tasks t
                    on t.unit_id = s.unit_id
                   and t.section_id = s.id
                 where m.course_id = %s
                   and m.unit_id = %s::uuid
                   and c.teacher_id = coalesce(current_setting('app.current_sub', true), '')
                 order by s.position asc, t.position asc, t.id
                """,
                (course_id, unit_id),
            )
            rows = cur.fetchall() or []
    return [
        {
            "id": r[0],
            "instruction_md": r[1] or "",
            "position": int(r[2]) if r[2] is not None else 0,
            "kind": str(r[3] or "native"),
        }
        for r in rows
    ]

def list_tasks_for_course_units_owner(
    *,
    dsn: str,
    psycopg_module,
    course_id: str,
    unit_ids: Sequence[str],
    owner_sub: str,
) -> List[dict]:
    """Return tasks for several attached units with one owner-scoped query.

    Why:
        The student overview renders a course-level snapshot across multiple
        units. Batching the task lookup avoids one SQL round-trip per unit
        while keeping ordering identical to the single-unit variant.
    """
    normalized_unit_ids = [str(unit_id) for unit_id in unit_ids if str(unit_id or "").strip()]
    if not normalized_unit_ids:
        return []

    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (owner_sub,))
            cur.execute(
                """
                select m.unit_id::text,
                       t.id::text,
                       t.instruction_md,
                       row_number() over (
                           partition by m.unit_id
                           order by s.position asc, t.position asc, t.id
                       ) as position,
                       t.kind::text
                  from public.course_modules m
                  join public.courses c
                    on c.id = m.course_id
                  join public.unit_sections s
                    on s.unit_id = m.unit_id
                  join public.unit_tasks t
                    on t.unit_id = s.unit_id
                   and t.section_id = s.id
                 where m.course_id = %s
                   and m.unit_id = any(%s::uuid[])
                   and c.teacher_id = coalesce(current_setting('app.current_sub', true), '')
                 order by m.position asc, s.position asc, t.position asc, t.id
                """,
                (course_id, normalized_unit_ids),
            )
            rows = cur.fetchall() or []
    return [
        {
            "unit_id": r[0],
            "id": r[1],
            "instruction_md": r[2] or "",
            "position": int(r[3]) if r[3] is not None else 0,
            "kind": str(r[4] or "native"),
        }
        for r in rows
    ]
