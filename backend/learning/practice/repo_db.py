"""PostgreSQL repository for learner practice sessions.

Why:
    Session creation and transitions require row locks, RLS context and an
    immutable task snapshot. Keeping that transaction logic in one adapter
    makes the use-case layer deterministic and keeps HTTP handlers small.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import random
import secrets
from uuid import UUID, uuid4

import psycopg
from psycopg.types.json import Jsonb

from backend.learning.repo_db import _dsn as learning_dsn
from backend.learning.practice.service import ActivePracticeSessionError
from backend.learning.practice.scheduler import (
    PreviousPracticeState,
    classify_h5p,
    schedule,
    scheduler_classification,
)


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
                select item.id::text, item.course_id::text, item.practice_module_id::text,
                       item.task_id::text, item.position, item.status, item.presentation_number,
                       item.task_kind, item.instruction_md, item.criteria, item.h5p_content_id,
                       latest_attempt.id::text
                  from public.learning_practice_session_items item
                  left join lateral (
                    select attempt.id
                      from public.learning_practice_attempts attempt
                     where attempt.session_item_id = item.id
                     order by attempt.created_at desc, attempt.id desc
                     limit 1
                  ) latest_attempt on true
                 where item.session_id=%s::uuid
                   and item.status in ('active', 'awaiting_analysis', 'feedback')
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
                    "latest_attempt_id": str(item[11]) if item[11] is not None else None,
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

    def create_native_attempt(
        self,
        *,
        student_sub: str,
        session_id: str,
        item_id: str,
        answer_text: str,
        idempotency_key: str,
    ) -> dict:
        """Accept one native answer and enqueue its analysis atomically.

        The raw idempotency key is never persisted. Its SHA-256 digest binds a
        retry to the learner and the existing attempt while the answer remains
        in the established submission store.
        """

        session_uuid, item_uuid = _uuid(session_id), _uuid(item_id)
        key_hash = hashlib.sha256(idempotency_key.encode("utf-8")).digest()
        key_hex = key_hash.hex()
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                self._set_student(cur, student_sub)
                # Lock ownership and item state before interpreting the key. A
                # concurrent duplicate then observes the first committed row.
                cur.execute(
                    """
                    select session.mode, session.status, item.course_id::text,
                           item.practice_module_id::text, item.task_id::text,
                           item.task_kind, item.status, item.presentation_number,
                           item.criteria, item.instruction_md
                      from public.learning_practice_sessions session
                      join public.learning_practice_session_items item on item.session_id=session.id
                     where session.id=%s::uuid and session.student_sub=%s
                       and item.id=%s::uuid
                     for update of session, item
                    """,
                    (session_uuid, student_sub, item_uuid),
                )
                row = cur.fetchone()
                if not row:
                    raise LookupError("practice_session_not_found")

                # The row lock serializes duplicates for the same item. The
                # advisory lock also covers accidental reuse across two items.
                cur.execute(
                    "select pg_advisory_xact_lock(hashtextextended(%s, 0))",
                    (f"{student_sub}:{key_hex}",),
                )
                cur.execute(
                    """
                    select attempt.id::text, attempt.status, attempt.session_id::text,
                           attempt.session_item_id::text
                      from public.learning_practice_attempts attempt
                     where attempt.student_sub=%s and attempt.idempotency_key_hash=%s
                    """,
                    (student_sub, key_hash),
                )
                existing = cur.fetchone()
                if existing:
                    if str(existing[2]) != session_uuid or str(existing[3]) != item_uuid:
                        raise ValueError("practice_idempotency_conflict")
                    return {"attempt_id": str(existing[0]), "status": str(existing[1])}

                mode, session_status, course_id, module_id, task_id = map(str, row[:5])
                task_kind, item_status = str(row[5]), str(row[6])
                presentation_number = int(row[7])
                criteria, instruction_md = list(row[8] or []), str(row[9])
                if session_status != "active" or item_status != "active" or task_kind != "native":
                    raise ValueError("practice_item_state_conflict")
                if not self._stack_is_open(
                    cur,
                    student_sub=student_sub,
                    course_id=course_id,
                    module_id=module_id,
                ):
                    raise LookupError("practice_session_not_found")
                cur.execute(
                    "select section_id::text from public.unit_tasks where id=%s::uuid",
                    (task_id,),
                )
                task_row = cur.fetchone()
                if not task_row:
                    raise LookupError("practice_session_not_found")
                section_id = str(task_row[0])

                submission_id, attempt_id = str(uuid4()), str(uuid4())
                cur.execute(
                    "select public.next_attempt_nr(%s::uuid, %s::uuid, %s)",
                    (course_id, task_id, student_sub),
                )
                attempt_nr = int(cur.fetchone()[0])
                cur.execute(
                    """
                    insert into public.learning_submissions (
                      id, course_id, task_id, section_id, student_sub, intent,
                      kind, text_body, attempt_nr, analysis_status,
                      idempotency_key, internal_metadata
                    ) values (
                      %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s, 'feedback',
                      'text', %s, %s, 'pending', %s,
                      jsonb_build_object('analysis_mode', 'text_direct', 'practice_attempt_id', %s::text)
                    )
                    """,
                    (
                        submission_id, course_id, task_id, section_id, student_sub,
                        answer_text, attempt_nr, key_hex, attempt_id,
                    ),
                )
                cur.execute(
                    """
                    insert into public.learning_practice_attempts (
                      id, session_id, session_item_id, course_id, student_sub,
                      task_id, submission_id, mode, presentation_number,
                      input_method, idempotency_key_hash, solution_seen
                    ) values (
                      %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s,
                      %s::uuid, %s::uuid, %s, %s, 'typed', %s,
                      exists(select 1 from public.learning_practice_session_items where id=%s::uuid and solution_viewed_at is not null)
                    )
                    """,
                    (
                        attempt_id, session_uuid, item_uuid, course_id, student_sub,
                        task_id, submission_id, mode, presentation_number, key_hash, item_uuid,
                    ),
                )
                job_payload = {
                    "submission_id": submission_id,
                    "course_id": course_id,
                    "task_id": task_id,
                    "task_kind": "native",
                    "student_sub": student_sub,
                    "intent": "feedback",
                    "kind": "text",
                    "attempt_nr": attempt_nr,
                    "criteria": criteria,
                    "instruction_md": instruction_md,
                    "analysis_mode": "text_direct",
                    "practice_attempt_id": attempt_id,
                }
                cur.execute(
                    "insert into public.learning_submission_jobs (submission_id, payload) values (%s::uuid, %s)",
                    (submission_id, Jsonb(job_payload)),
                )
                cur.execute(
                    "update public.learning_practice_session_items set status='awaiting_analysis' where id=%s::uuid",
                    (item_uuid,),
                )
                conn.commit()
        return {"attempt_id": attempt_id, "status": "pending"}

    def get_attempt(self, *, student_sub: str, attempt_id: str) -> dict | None:
        attempt_uuid = _uuid(attempt_id)
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                self._set_student(cur, student_sub)
                cur.execute(
                    """
                    select id::text, status, classification, fulfillment,
                           feedback_md, resulting_due_at
                      from public.learning_practice_attempts
                     where id=%s::uuid and student_sub=%s
                    """,
                    (attempt_uuid, student_sub),
                )
                row = cur.fetchone()
        if not row:
            return None
        return {
            "id": str(row[0]),
            "status": str(row[1]),
            "classification": str(row[2]) if row[2] is not None else None,
            "fulfillment": float(row[3]) if row[3] is not None else None,
            "feedback_md": str(row[4]) if row[4] is not None else None,
            "due_at": row[5].isoformat() if row[5] is not None else None,
        }

    def issue_h5p_context(
        self, *, student_sub: str, session_id: str, item_id: str
    ) -> dict | None:
        """Issue one fresh presentation token and persist only its digest."""

        session_uuid, item_uuid = _uuid(session_id), _uuid(item_id)
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode("utf-8")).digest()
        context_id = f"practice-{item_uuid}-{secrets.token_urlsafe(12)}"
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                self._set_student(cur, student_sub)
                cur.execute(
                    """
                    select item.course_id::text, item.practice_module_id::text,
                           item.task_kind, item.status
                      from public.learning_practice_sessions session
                      join public.learning_practice_session_items item on item.session_id=session.id
                     where session.id=%s::uuid and session.student_sub=%s
                       and session.status='active' and item.id=%s::uuid
                     for update of session, item
                    """,
                    (session_uuid, student_sub, item_uuid),
                )
                row = cur.fetchone()
                if not row:
                    return None
                if str(row[2]) != "h5p" or str(row[3]) != "active":
                    raise ValueError("practice_item_state_conflict")
                if not self._stack_is_open(
                    cur,
                    student_sub=student_sub,
                    course_id=str(row[0]),
                    module_id=str(row[1]),
                ):
                    return None
                cur.execute(
                    "update public.learning_practice_session_items set completion_token_hash=%s where id=%s::uuid",
                    (token_hash, item_uuid),
                )
                conn.commit()
        return {"practice_completion_token": token, "context_id": context_id}

    def complete_h5p_attempt(
        self,
        *,
        student_sub: str,
        session_id: str,
        item_id: str,
        score_raw: int,
        score_max: int,
        completion_token: str,
    ) -> dict:
        """Persist one token-bound H5P completion and scheduler transition."""

        session_uuid, item_uuid = _uuid(session_id), _uuid(item_id)
        token_hash = hashlib.sha256(completion_token.encode("utf-8")).digest()
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                self._set_student(cur, student_sub)
                cur.execute(
                    "select id::text, status from public.learning_practice_attempts where completion_token_hash=%s and student_sub=%s",
                    (token_hash, student_sub),
                )
                existing = cur.fetchone()
                if existing:
                    return {"attempt_id": str(existing[0]), "status": str(existing[1])}
                cur.execute(
                    """
                    select session.mode, item.course_id::text, item.practice_module_id::text,
                           item.task_id::text, item.status, item.presentation_number,
                           item.completion_token_hash
                      from public.learning_practice_sessions session
                      join public.learning_practice_session_items item on item.session_id=session.id
                     where session.id=%s::uuid and session.student_sub=%s
                       and session.status='active' and item.id=%s::uuid and item.task_kind='h5p'
                     for update of session, item
                    """,
                    (session_uuid, student_sub, item_uuid),
                )
                row = cur.fetchone()
                if not row:
                    raise LookupError("practice_session_not_found")
                cur.execute(
                    "select id::text, status from public.learning_practice_attempts where completion_token_hash=%s and student_sub=%s",
                    (token_hash, student_sub),
                )
                existing = cur.fetchone()
                if existing:
                    return {"attempt_id": str(existing[0]), "status": str(existing[1])}
                if str(row[4]) != "active" or bytes(row[6] or b"") != token_hash:
                    raise ValueError("practice_completion_token_invalid")
                mode, course_id, module_id, task_id = map(str, row[:4])
                presentation_number = int(row[5])
                if not self._stack_is_open(
                    cur, student_sub=student_sub, course_id=course_id, module_id=module_id
                ):
                    raise LookupError("practice_session_not_found")
                cur.execute(
                    """
                    select stability_days, interval_seconds, due_at, last_attempt_at,
                           review_count, scheduler_version, support_pending
                      from public.learning_practice_states
                     where course_id=%s::uuid and student_sub=%s and task_id=%s::uuid
                     for update
                    """,
                    (course_id, student_sub, task_id),
                )
                state_row = cur.fetchone()
                previous = None
                if state_row:
                    previous = PreviousPracticeState(
                        stability_days=float(state_row[0]),
                        interval_seconds=int(state_row[1]),
                        due_at=state_row[2],
                        last_attempt_at=state_row[3],
                        review_count=int(state_row[4]),
                        scheduler_version=str(state_row[5]),
                    )
                supported = presentation_number == 2 or bool(state_row and state_row[6])
                fulfillment = score_raw / score_max
                classification = classify_h5p(fulfillment, supported=supported)
                completed_at = datetime.now(timezone.utc)
                result = schedule(
                    previous=previous,
                    completed_at=completed_at,
                    fulfillment=fulfillment,
                    classification=scheduler_classification(classification),
                    supported_recall=supported,
                )
                self._set_course(cur, course_id)
                cur.execute("select section_id::text from public.unit_tasks where id=%s::uuid", (task_id,))
                task = cur.fetchone()
                if not task:
                    raise LookupError("practice_session_not_found")
                submission_id, attempt_id = str(uuid4()), str(uuid4())
                cur.execute("select public.next_attempt_nr(%s::uuid, %s::uuid, %s)", (course_id, task_id, student_sub))
                attempt_nr = int(cur.fetchone()[0])
                cur.execute(
                    """
                    insert into public.learning_submissions (
                      id, course_id, task_id, section_id, student_sub, intent, kind,
                      score_raw, score_max, attempt_nr, analysis_status,
                      idempotency_key, completed_at
                    ) values (%s::uuid, %s::uuid, %s::uuid, %s::uuid, %s,
                      'feedback', 'h5p', %s, %s, %s, 'completed', %s, %s)
                    """,
                    (submission_id, course_id, task_id, str(task[0]), student_sub,
                     score_raw, score_max, attempt_nr, token_hash.hex(), completed_at),
                )
                feedback = {
                    "secure": "Sicher gelöst.",
                    "partial": "Teilweise gelöst.",
                    "insufficient": "Noch nicht ausreichend gelöst.",
                }[classification]
                cur.execute(
                    """
                    insert into public.learning_practice_attempts (
                      id, session_id, session_item_id, course_id, student_sub, task_id,
                      submission_id, mode, presentation_number, input_method,
                      completion_token_hash, supported_recall, original_due_at,
                      original_stability_days, original_interval_seconds, fulfillment,
                      classification, resulting_stability_days, resulting_interval_seconds,
                      resulting_due_at, feedback_md, status, scheduler_applied_at, completed_at
                    ) values (
                      %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s, %s::uuid,
                      %s::uuid, %s, %s, 'h5p', %s, %s, %s, %s, %s, %s, %s,
                      %s, %s, %s, %s, 'completed', %s, %s
                    )
                    """,
                    (
                        attempt_id, session_uuid, item_uuid, course_id, student_sub, task_id,
                        submission_id, mode, presentation_number, token_hash, supported,
                        previous.due_at if previous else None,
                        previous.stability_days if previous else None,
                        previous.interval_seconds if previous else None,
                        fulfillment, classification, result.stability_days,
                        result.interval_seconds, result.due_at, feedback, completed_at, completed_at,
                    ),
                )
                cur.execute(
                    """
                    insert into public.learning_practice_states (
                      course_id, student_sub, task_id, stability_days, interval_seconds,
                      due_at, last_attempt_at, last_fulfillment, last_classification,
                      review_count, scheduler_version, support_pending
                    ) values (%s::uuid, %s, %s::uuid, %s, %s, %s, %s, %s, %s, 1, %s, false)
                    on conflict (course_id, student_sub, task_id) do update set
                      stability_days=excluded.stability_days,
                      interval_seconds=excluded.interval_seconds,
                      due_at=excluded.due_at,
                      last_attempt_at=excluded.last_attempt_at,
                      last_fulfillment=excluded.last_fulfillment,
                      last_classification=excluded.last_classification,
                      review_count=public.learning_practice_states.review_count + 1,
                      scheduler_version=excluded.scheduler_version,
                      support_pending=case when %s then false else public.learning_practice_states.support_pending end
                    """,
                    (course_id, student_sub, task_id, result.stability_days,
                     result.interval_seconds, result.due_at, completed_at, fulfillment,
                     classification, result.scheduler_version, supported),
                )
                cur.execute("update public.learning_practice_session_items set status='feedback' where id=%s::uuid", (item_uuid,))
                conn.commit()
        return {"attempt_id": attempt_id, "status": "completed"}

    def reveal_solution(
        self, *, student_sub: str, session_id: str, item_id: str
    ) -> dict | None:
        """Persist solution access and future support before returning content."""

        session_uuid, item_uuid = _uuid(session_id), _uuid(item_id)
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                self._set_student(cur, student_sub)
                cur.execute(
                    """
                    select item.course_id::text, item.task_id::text, item.status
                      from public.learning_practice_sessions session
                      join public.learning_practice_session_items item on item.session_id=session.id
                     where session.id=%s::uuid and session.student_sub=%s and item.id=%s::uuid
                     for update of item
                    """,
                    (session_uuid, student_sub, item_uuid),
                )
                row = cur.fetchone()
                if not row:
                    return None
                if str(row[2]) != "feedback":
                    raise ValueError("practice_item_state_conflict")
                self._set_course(cur, str(row[0]))
                cur.execute(
                    """
                    select exists(
                      select 1 from public.learning_practice_attempts
                       where session_item_id=%s::uuid and student_sub=%s and status='completed'
                    )
                    """,
                    (item_uuid, student_sub),
                )
                if not bool(cur.fetchone()[0]):
                    raise PermissionError("practice_solution_forbidden")
                cur.execute(
                    "update public.learning_practice_session_items set solution_viewed_at=coalesce(solution_viewed_at, now()) where id=%s::uuid",
                    (item_uuid,),
                )
                cur.execute(
                    """
                    update public.learning_practice_states
                       set support_pending=true
                     where course_id=%s::uuid and student_sub=%s and task_id=%s::uuid
                    """,
                    (str(row[0]), student_sub, str(row[1])),
                )
                cur.execute(
                    "select model_solution_md from public.unit_tasks where id=%s::uuid",
                    (str(row[1]),),
                )
                solution_row = cur.fetchone()
                if not solution_row:
                    raise LookupError("practice_session_not_found")
                conn.commit()
                solution = str(solution_row[0] or "")
        return {"model_solution_md": solution}

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
             where session_id=%s::uuid and status in ('queued', 'retry_queued')
             order by case when status='queued' then 0 else 1 end, position
             limit 1 for update
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
                    """
                    select item.id, item.presentation_number,
                           attempt.classification
                      from public.learning_practice_session_items item
                      join lateral (
                        select classification
                          from public.learning_practice_attempts
                         where session_item_id=item.id and status='completed'
                         order by completed_at desc limit 1
                      ) attempt on true
                     where item.session_id=%s::uuid and item.status='feedback'
                     for update of item
                    """,
                    (session_uuid,),
                )
                current = cur.fetchone()
                if not current:
                    raise ValueError("practice_feedback_pending")
                needs_retry = int(current[1]) == 1 and str(current[2]) != "secure"
                if needs_retry:
                    cur.execute(
                        "update public.learning_practice_session_items set status='retry_queued', presentation_number=2 where id=%s",
                        (current[0],),
                    )
                else:
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
