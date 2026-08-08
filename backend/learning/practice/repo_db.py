"""PostgreSQL repository for learner practice sessions.

Why:
    Session creation and transitions require row locks, RLS context and an
    immutable task snapshot. Keeping that transaction logic in one adapter
    makes the use-case layer deterministic and keeps HTTP handlers small.
"""

from __future__ import annotations

from datetime import datetime, timezone
import random
from uuid import UUID

import psycopg

from backend.learning.repo_db import _dsn as learning_dsn
from backend.learning.practice.service import ActivePracticeSessionError


def _uuid(value: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid_uuid") from exc


class DBPracticeRepo:
    """Persist practice stacks and learner-owned session state."""

    def __init__(self, dsn: str | None = None) -> None:
        self._dsn = dsn or learning_dsn()

    @staticmethod
    def _set_student(cur, student_sub: str) -> None:  # noqa: ANN001
        cur.execute("select set_config('app.current_sub', %s, true)", (student_sub,))

    @staticmethod
    def _set_course(cur, course_id: str) -> None:  # noqa: ANN001
        cur.execute("select set_config('app.current_course_id', %s, true)", (course_id,))

    def _course_ids(self, cur, student_sub: str) -> list[tuple[str, str]]:  # noqa: ANN001
        cur.execute(
            """
            select membership.course_id::text, course.title
              from public.course_memberships membership
              join public.courses course on course.id = membership.course_id
             where membership.student_id = %s
             order by course.title asc, membership.course_id asc
            """,
            (student_sub,),
        )
        return [(str(row[0]), str(row[1])) for row in (cur.fetchall() or [])]

    def _stacks_for_course(
        self, cur, *, student_sub: str, course_id: str, course_title: str
    ) -> list[dict]:  # noqa: ANN001
        self._set_course(cur, course_id)
        cur.execute(
            """
            select unit.id::text,
                   unit.title,
                   module.id::text,
                   section.title,
                   state.tasks_total,
                   state.due_tasks_count
              from public.course_modules course_module
              join public.units unit on unit.id = course_module.unit_id
              join public.unit_modules module on module.unit_id = unit.id
              join public.unit_sections section on section.id = module.section_id
              join lateral public.get_modular_unit_module_states_for_student(
                %s, %s::uuid, unit.id, true
              ) state on state.module_id = module.id
             where course_module.course_id = %s::uuid
               and unit.unit_type = 'modular'
               and state.module_kind = 'practice'
               and state.status = 'open'
               and state.tasks_total > 0
             order by course_module.position, unit.title, module.position_in_phase, module.id
            """,
            (student_sub, course_id, course_id),
        )
        return [
            {
                "course_id": course_id,
                "course_title": course_title,
                "unit_id": str(row[0]),
                "unit_title": str(row[1]),
                "practice_module_id": str(row[2]),
                "module_title": str(row[3]),
                "task_count": int(row[4] or 0),
                "due_tasks_count": int(row[5] or 0),
            }
            for row in (cur.fetchall() or [])
        ]

    def list_stacks(self, *, student_sub: str) -> list[dict]:
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                self._set_student(cur, student_sub)
                stacks: list[dict] = []
                for course_id, title in self._course_ids(cur, student_sub):
                    stacks.extend(
                        self._stacks_for_course(
                            cur,
                            student_sub=student_sub,
                            course_id=course_id,
                            course_title=title,
                        )
                    )
        return stacks

    def _load_selected_stack(
        self,
        cur,
        *,
        student_sub: str,
        course_id: str,
        module_id: str,
        mode: str,
    ) -> list[dict]:  # noqa: ANN001
        self._set_course(cur, course_id)
        cur.execute(
            """
            select module.section_id::text
              from public.unit_modules module
              join public.course_modules course_module on course_module.unit_id = module.unit_id
              join lateral public.get_modular_unit_module_states_for_student(
                %s, %s::uuid, module.unit_id, true
              ) state on state.module_id = module.id
             where course_module.course_id = %s::uuid
               and module.id = %s::uuid
               and state.module_kind = 'practice'
               and state.status = 'open'
               and state.tasks_total > 0
             limit 1
            """,
            (student_sub, course_id, course_id, module_id),
        )
        row = cur.fetchone()
        if not row:
            raise LookupError("practice_stack_not_found")
        section_id = str(row[0])
        cur.execute(
            """
            select task.id::text,
                   task.kind,
                   task.instruction_md,
                   task.criteria,
                   task.h5p_content_id
              from public.unit_tasks task
              left join public.learning_practice_states state
                on state.course_id = %s::uuid
               and state.student_sub = %s
               and state.task_id = task.id
             where task.section_id = %s::uuid
               and (%s = 'exam' or state.task_id is null or state.due_at <= now())
             order by task.position, task.id
            """,
            (course_id, student_sub, section_id, mode),
        )
        return [
            {
                "course_id": course_id,
                "practice_module_id": module_id,
                "task_id": str(task[0]),
                "task_kind": str(task[1]),
                "instruction_md": str(task[2]),
                "criteria": list(task[3] or []),
                "h5p_content_id": str(task[4]) if task[4] is not None else None,
            }
            for task in (cur.fetchall() or [])
        ]

    def create_session(
        self,
        *,
        student_sub: str,
        mode: str,
        stacks: list[dict[str, str]],
        rng: random.Random,
        max_items: int,
    ) -> dict:
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                self._set_student(cur, student_sub)
                cur.execute(
                    "select id::text from public.learning_practice_sessions where student_sub=%s and status='active'",
                    (student_sub,),
                )
                active = cur.fetchone()
                if active:
                    raise ActivePracticeSessionError(str(active[0]))

                items: list[dict] = []
                normalized_stacks: list[tuple[str, str]] = []
                for stack in stacks:
                    course_id = _uuid(stack["course_id"])
                    module_id = _uuid(stack["practice_module_id"])
                    normalized_stacks.append((course_id, module_id))
                    items.extend(
                        self._load_selected_stack(
                            cur,
                            student_sub=student_sub,
                            course_id=course_id,
                            module_id=module_id,
                            mode=mode,
                        )
                    )
                    if len(items) > max_items:
                        raise ValueError("session_item_limit_exceeded")

                rng.shuffle(items)
                status = "active" if items else "ended"
                ended_at = None if items else datetime.now(timezone.utc)
                try:
                    cur.execute(
                        """
                        insert into public.learning_practice_sessions (student_sub, mode, status, ended_at)
                        values (%s, %s, %s, %s)
                        returning id::text
                        """,
                        (student_sub, mode, status, ended_at),
                    )
                except psycopg.errors.UniqueViolation as exc:
                    raise ActivePracticeSessionError("") from exc
                session_id = str(cur.fetchone()[0])
                cur.executemany(
                    """
                    insert into public.learning_practice_session_stacks
                      (session_id, course_id, practice_module_id)
                    values (%s::uuid, %s::uuid, %s::uuid)
                    """,
                    [(session_id, course_id, module_id) for course_id, module_id in normalized_stacks],
                )
                cur.executemany(
                    """
                    insert into public.learning_practice_session_items (
                      session_id, course_id, practice_module_id, task_id,
                      task_kind, instruction_md, criteria, h5p_content_id,
                      position, status
                    ) values (%s::uuid, %s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s)
                    """,
                    [
                        (
                            session_id,
                            item["course_id"],
                            item["practice_module_id"],
                            item["task_id"],
                            item["task_kind"],
                            item["instruction_md"],
                            item["criteria"],
                            item["h5p_content_id"],
                            position,
                            "active" if position == 1 else "queued",
                        )
                        for position, item in enumerate(items, start=1)
                    ],
                )
                conn.commit()
        result = self.get_session(student_sub=student_sub, session_id=session_id)
        if result is None:  # pragma: no cover - defensive RLS guard
            raise RuntimeError("practice_session_insert_not_visible")
        return result

    def _session_payload(self, cur, *, student_sub: str, session_id: str) -> dict | None:  # noqa: ANN001
        cur.execute(
            """
            select id::text, mode, status, started_at, ended_at
              from public.learning_practice_sessions
             where id=%s::uuid and student_sub=%s
            """,
            (session_id, student_sub),
        )
        row = cur.fetchone()
        if not row:
            return None
        cur.execute(
            """
            select count(*)::int,
                   count(*) filter (where status in ('completed', 'skipped'))::int
              from public.learning_practice_session_items
             where session_id=%s::uuid
            """,
            (session_id,),
        )
        total, completed = cur.fetchone()
        current_item = None
        if str(row[2]) == "active":
            cur.execute(
                """
                select id::text, course_id::text, practice_module_id::text,
                       task_id::text, position, status, presentation_number,
                       task_kind, instruction_md, criteria, h5p_content_id
                  from public.learning_practice_session_items
                 where session_id=%s::uuid
                   and status in ('active', 'awaiting_analysis', 'feedback')
                 limit 1
                """,
                (session_id,),
            )
            item = cur.fetchone()
            if item:
                current_item = {
                    "id": str(item[0]),
                    "course_id": str(item[1]),
                    "practice_module_id": str(item[2]),
                    "task_id": str(item[3]),
                    "position": int(item[4]),
                    "status": str(item[5]),
                    "presentation_number": int(item[6]),
                    "kind": str(item[7]),
                    "instruction_md": str(item[8]),
                    "criteria": list(item[9] or []),
                    "h5p_content_id": str(item[10]) if item[10] is not None else None,
                }
        return {
            "id": str(row[0]),
            "mode": str(row[1]),
            "status": str(row[2]),
            "started_at": row[3].isoformat(),
            "ended_at": row[4].isoformat() if row[4] else None,
            "total_items": int(total or 0),
            "completed_items": int(completed or 0),
            "current_item": current_item,
        }

    def get_active_session(self, *, student_sub: str) -> dict | None:
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                self._set_student(cur, student_sub)
                cur.execute(
                    "select id::text from public.learning_practice_sessions where student_sub=%s and status='active'",
                    (student_sub,),
                )
                row = cur.fetchone()
                return self._session_payload(cur, student_sub=student_sub, session_id=str(row[0])) if row else None

    def get_session(self, *, student_sub: str, session_id: str) -> dict | None:
        session_uuid = _uuid(session_id)
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                self._set_student(cur, student_sub)
                return self._session_payload(cur, student_sub=student_sub, session_id=session_uuid)

    def _stack_is_open(self, cur, *, student_sub: str, course_id: str, module_id: str) -> bool:  # noqa: ANN001
        self._set_course(cur, course_id)
        cur.execute(
            """
            select exists(
              select 1
                from public.unit_modules module
                join public.course_modules course_module on course_module.unit_id=module.unit_id
                join lateral public.get_modular_unit_module_states_for_student(
                  %s, %s::uuid, module.unit_id, true
                ) state on state.module_id=module.id
               where course_module.course_id=%s::uuid
                 and module.id=%s::uuid
                 and state.module_kind='practice'
                 and state.status='open'
            )
            """,
            (student_sub, course_id, course_id, module_id),
        )
        return bool(cur.fetchone()[0])

    def _prune_inaccessible_queued(self, cur, *, student_sub: str, session_id: str) -> None:  # noqa: ANN001
        cur.execute(
            """
            select distinct course_id::text, practice_module_id::text
              from public.learning_practice_session_items
             where session_id=%s::uuid and status in ('queued', 'retry_queued')
            """,
            (session_id,),
        )
        for course_id, module_id in cur.fetchall() or []:
            if self._stack_is_open(
                cur, student_sub=student_sub, course_id=str(course_id), module_id=str(module_id)
            ):
                continue
            cur.execute(
                """
                update public.learning_practice_session_items
                   set status='skipped', access_skip_reason='access_lost'
                 where session_id=%s::uuid and course_id=%s::uuid
                   and practice_module_id=%s::uuid and status in ('queued', 'retry_queued')
                """,
                (session_id, course_id, module_id),
            )

    @staticmethod
    def _activate_next_or_end(cur, session_id: str) -> None:  # noqa: ANN001
        cur.execute(
            """
            select id from public.learning_practice_session_items
             where session_id=%s::uuid and status='queued'
             order by position limit 1 for update
            """,
            (session_id,),
        )
        next_item = cur.fetchone()
        if next_item:
            cur.execute(
                "update public.learning_practice_session_items set status='active' where id=%s",
                (next_item[0],),
            )
            return
        cur.execute(
            "update public.learning_practice_sessions set status='ended', ended_at=now() where id=%s::uuid and status='active'",
            (session_id,),
        )

    def continue_session(self, *, student_sub: str, session_id: str) -> dict | None:
        session_uuid = _uuid(session_id)
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                self._set_student(cur, student_sub)
                cur.execute(
                    "select status from public.learning_practice_sessions where id=%s::uuid and student_sub=%s for update",
                    (session_uuid, student_sub),
                )
                session = cur.fetchone()
                if not session:
                    return None
                if str(session[0]) == "ended":
                    return self._session_payload(cur, student_sub=student_sub, session_id=session_uuid)
                cur.execute(
                    "select id from public.learning_practice_session_items where session_id=%s::uuid and status='feedback' for update",
                    (session_uuid,),
                )
                current = cur.fetchone()
                if not current:
                    raise ValueError("practice_feedback_pending")
                cur.execute(
                    "update public.learning_practice_session_items set status='completed' where id=%s",
                    (current[0],),
                )
                self._prune_inaccessible_queued(cur, student_sub=student_sub, session_id=session_uuid)
                self._activate_next_or_end(cur, session_uuid)
                conn.commit()
        return self.get_session(student_sub=student_sub, session_id=session_uuid)

    def skip_item(self, *, student_sub: str, session_id: str, item_id: str) -> dict | None:
        session_uuid, item_uuid = _uuid(session_id), _uuid(item_id)
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                self._set_student(cur, student_sub)
                cur.execute(
                    "select status from public.learning_practice_sessions where id=%s::uuid and student_sub=%s for update",
                    (session_uuid, student_sub),
                )
                session = cur.fetchone()
                if not session:
                    return None
                if str(session[0]) == "ended":
                    return self._session_payload(cur, student_sub=student_sub, session_id=session_uuid)
                cur.execute(
                    "select status from public.learning_practice_session_items where id=%s::uuid and session_id=%s::uuid for update",
                    (item_uuid, session_uuid),
                )
                item = cur.fetchone()
                if not item:
                    raise LookupError("practice_item_not_found")
                if str(item[0]) == "skipped":
                    return self._session_payload(cur, student_sub=student_sub, session_id=session_uuid)
                if str(item[0]) != "active":
                    raise ValueError("practice_item_state_conflict")
                cur.execute(
                    "update public.learning_practice_session_items set status='skipped' where id=%s::uuid",
                    (item_uuid,),
                )
                self._prune_inaccessible_queued(cur, student_sub=student_sub, session_id=session_uuid)
                self._activate_next_or_end(cur, session_uuid)
                conn.commit()
        return self.get_session(student_sub=student_sub, session_id=session_uuid)

    def end_session(self, *, student_sub: str, session_id: str) -> dict | None:
        session_uuid = _uuid(session_id)
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                self._set_student(cur, student_sub)
                cur.execute(
                    "select status from public.learning_practice_sessions where id=%s::uuid and student_sub=%s for update",
                    (session_uuid, student_sub),
                )
                row = cur.fetchone()
                if not row:
                    return None
                if str(row[0]) == "active":
                    cur.execute(
                        """
                        update public.learning_practice_session_items
                           set status='skipped'
                         where session_id=%s::uuid and status in ('queued', 'active', 'retry_queued')
                        """,
                        (session_uuid,),
                    )
                    cur.execute(
                        "update public.learning_practice_sessions set status='ended', ended_at=now() where id=%s::uuid",
                        (session_uuid,),
                    )
                    conn.commit()
        return self.get_session(student_sub=student_sub, session_id=session_uuid)
