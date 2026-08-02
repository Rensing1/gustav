"""RLS-aware Postgres queries for resumable AI dialog sessions.

Conversation text is persisted but never logged. Every learner operation sets
both student and course context before reading or mutating rows.
"""

from __future__ import annotations

import json
from typing import Any, Sequence
from uuid import UUID, uuid5


_SUBMISSION_NAMESPACE = UUID("00000000-0000-0000-0000-000000000002")


def _json_object(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        parsed = json.loads(value)
        if isinstance(parsed, dict):
            return parsed
    raise RuntimeError("invalid_dialog_snapshot")


def _turn(row: Sequence[object]) -> dict[str, Any]:
    return {
        "id": row[0],
        "round_nr": int(row[1]),
        "student_message": row[2],
        "starter_text": row[3],
        "starter_source": row[4],
        "status": row[5],
        "ai_message": row[6],
        "next_starters": list(row[7] or []),
        "generation_attempts": int(row[8] or 0),
        "error_code": row[9],
        "created_at": row[10],
        "completed_at": row[11],
    }


def _read_context(cur, *, course_id: str, task_id: str, session_id: str) -> dict[str, Any]:
    cur.execute(
        "select * from public.learning_get_dialog_context(%s::uuid, %s::uuid, %s::uuid)",
        (course_id, task_id, session_id),
    )
    row = cur.fetchone()
    if not row:
        raise LookupError("dialog_session_not_found")
    return {
        "instruction_md": row[0],
        "criteria": list(row[1] or []),
        "teacher_context_md": row[2],
        "max_attempts": int(row[3]) if row[3] is not None else None,
        "dialog_config": _json_object(row[4]),
    }


def _read_session(cur, *, course_id: str, task_id: str, session_id: str, for_update: bool = False) -> dict[str, Any]:
    suffix = " for update" if for_update else ""
    cur.execute(
        f"""
        select id::text, status, round_count, initial_sentence_starters,
               initial_starters_status, initial_starters_error_code,
               initial_generation_attempts, closing_answer_md,
               to_char(created_at at time zone 'utc', 'YYYY-MM-DD\"T\"HH24:MI:SS\"+00:00\"'),
               to_char(updated_at at time zone 'utc', 'YYYY-MM-DD\"T\"HH24:MI:SS\"+00:00\"'),
               to_char(completed_at at time zone 'utc', 'YYYY-MM-DD\"T\"HH24:MI:SS\"+00:00\"')
          from public.learning_dialog_sessions
         where id = %s::uuid and course_id = %s::uuid and task_id = %s::uuid
         {suffix}
        """,
        (session_id, course_id, task_id),
    )
    row = cur.fetchone()
    if not row:
        raise LookupError("dialog_session_not_found")
    context = _read_context(cur, course_id=course_id, task_id=task_id, session_id=session_id)
    config = context["dialog_config"]
    cur.execute(
        """
        select id::text, round_nr, student_message_md, used_sentence_starter_md,
               used_sentence_starter_source, status, assistant_reply_md,
               sentence_starters, generation_attempts, error_code,
               to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
               to_char(completed_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
          from public.learning_dialog_turns
         where session_id = %s::uuid
         order by round_nr
        """,
        (session_id,),
    )
    return {
        "id": row[0],
        "course_id": course_id,
        "task_id": task_id,
        "status": row[1],
        "round_count": int(row[2]),
        "partner_name": config["partner_name"],
        "partner_description_md": config["partner_description_md"],
        "opening_message_md": config["opening_message_md"],
        "response_mode": config["response_mode"],
        "max_rounds": int(config["max_rounds"]),
        "closing_prompt_md": config.get("closing_prompt_md"),
        "initial_starters": list(row[3] or []),
        "initial_generation_status": row[4],
        "initial_generation_error_code": row[5],
        "initial_generation_attempts": int(row[6] or 0),
        "closing_answer_md": row[7],
        "created_at": row[8],
        "updated_at": row[9],
        "completed_at": row[10],
        "turns": [_turn(turn_row) for turn_row in (cur.fetchall() or [])],
    }


def _connect(repo, *, student_sub: str, course_id: str):
    conn = repo._psycopg.connect(repo._dsn)
    cur = conn.cursor()
    repo._set_current_sub(cur, student_sub)
    repo._set_current_course_id(cur, course_id)
    return conn, cur


def start_or_resume(repo, *, course_id: str, task_id: str, student_sub: str) -> dict[str, Any]:
    course_id, task_id = str(UUID(course_id)), str(UUID(task_id))
    conn, cur = _connect(repo, student_sub=student_sub, course_id=course_id)
    try:
        cur.execute("select public.learning_start_dialog_session(%s::uuid, %s::uuid)::text", (course_id, task_id))
        session_id = str(cur.fetchone()[0])
        session = _read_session(cur, course_id=course_id, task_id=task_id, session_id=session_id)
        conn.commit()
        return session
    finally:
        cur.close()
        conn.close()


def get_session(repo, *, course_id: str, task_id: str, session_id: str, student_sub: str) -> dict[str, Any]:
    course_id, task_id, session_id = str(UUID(course_id)), str(UUID(task_id)), str(UUID(session_id))
    conn, cur = _connect(repo, student_sub=student_sub, course_id=course_id)
    try:
        return _read_session(cur, course_id=course_id, task_id=task_id, session_id=session_id)
    finally:
        cur.close()
        conn.close()


def set_initial_starters(repo, *, course_id: str, task_id: str, session_id: str, student_sub: str, starters: list[str]) -> dict[str, Any]:
    conn, cur = _connect(repo, student_sub=student_sub, course_id=course_id)
    try:
        cur.execute(
            """
            update public.learning_dialog_sessions
               set initial_sentence_starters = %s,
                   initial_starters_status = 'completed',
                   initial_starters_error_code = null,
                   initial_generation_attempts = initial_generation_attempts + 1
             where id = %s::uuid and course_id = %s::uuid and task_id = %s::uuid
               and status = 'active' and initial_starters_status in ('generating', 'failed')
               and initial_generation_attempts < 3
            """,
            (starters, session_id, course_id, task_id),
        )
        if cur.rowcount != 1:
            raise ValueError("invalid_dialog_session_state")
        session = _read_session(cur, course_id=course_id, task_id=task_id, session_id=session_id)
        conn.commit()
        return session
    finally:
        cur.close()
        conn.close()


def claim_initial_starters(repo, *, course_id: str, task_id: str, session_id: str, student_sub: str) -> bool:
    """Atomically claim one hybrid-start generation across concurrent tabs."""

    conn, cur = _connect(repo, student_sub=student_sub, course_id=course_id)
    try:
        cur.execute(
            """
            update public.learning_dialog_sessions
               set initial_starters_status='generating'
             where id=%s::uuid and course_id=%s::uuid and task_id=%s::uuid
               and status='active' and initial_starters_status in ('pending','failed')
               and initial_generation_attempts < 3
            """,
            (session_id, course_id, task_id),
        )
        claimed = cur.rowcount == 1
        conn.commit()
        return claimed
    finally:
        cur.close()
        conn.close()


def fail_initial_starters(repo, *, course_id: str, task_id: str, session_id: str, student_sub: str, error_code: str) -> None:
    conn, cur = _connect(repo, student_sub=student_sub, course_id=course_id)
    try:
        cur.execute(
            """
            update public.learning_dialog_sessions
               set initial_starters_status = 'failed', initial_starters_error_code = %s,
                   initial_generation_attempts = least(initial_generation_attempts + 1, 3)
             where id = %s::uuid and course_id = %s::uuid and task_id = %s::uuid and status = 'active'
            """,
            (error_code, session_id, course_id, task_id),
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()


def generation_context(repo, *, course_id: str, task_id: str, session_id: str, student_sub: str) -> dict[str, Any]:
    conn, cur = _connect(repo, student_sub=student_sub, course_id=course_id)
    try:
        context = _read_context(cur, course_id=course_id, task_id=task_id, session_id=session_id)
        config = context.pop("dialog_config")
        cur.execute(
            """
            select round_nr, student_message_md, used_sentence_starter_md,
                   used_sentence_starter_source, assistant_reply_md
              from public.learning_dialog_turns
             where session_id = %s::uuid and status = 'completed'
             order by round_nr
            """,
            (session_id,),
        )
        context.update(config)
        context["turns"] = [
            {
                "round_nr": int(row[0]),
                "student_message": row[1],
                "starter_text": row[2],
                "starter_source": row[3],
                "ai_message": row[4],
            }
            for row in (cur.fetchall() or [])
        ]
        return context
    finally:
        cur.close()
        conn.close()


def begin_turn(repo, *, course_id: str, task_id: str, session_id: str, student_sub: str, student_message: str, starter_text: str | None, starter_source: str | None, idempotency_key: str) -> dict[str, Any]:
    conn, cur = _connect(repo, student_sub=student_sub, course_id=course_id)
    try:
        session = _read_session(cur, course_id=course_id, task_id=task_id, session_id=session_id, for_update=True)
        cur.execute(
            """
            select id::text, round_nr, student_message_md, used_sentence_starter_md,
                   used_sentence_starter_source, status, assistant_reply_md,
                   sentence_starters, generation_attempts, error_code, null, null
              from public.learning_dialog_turns
             where session_id = %s::uuid and idempotency_key = %s
            """,
            (session_id, idempotency_key),
        )
        existing = cur.fetchone()
        if existing:
            conn.commit()
            return _turn(existing)
        if session["status"] != "active" or session["round_count"] >= session["max_rounds"]:
            raise ValueError("dialog_round_limit_reached")
        if session["response_mode"] == "hybrid" and session["initial_generation_status"] != "completed":
            raise ValueError("dialog_generation_pending")
        if session["turns"] and session["turns"][-1]["status"] != "completed":
            raise ValueError("dialog_previous_turn_incomplete")
        round_nr = session["round_count"] + 1
        cur.execute(
            """
            insert into public.learning_dialog_turns (
              session_id, round_nr, student_message_md, used_sentence_starter_md,
              used_sentence_starter_source, idempotency_key
            ) values (%s::uuid, %s, %s, %s, %s, %s)
            returning id::text, round_nr, student_message_md, used_sentence_starter_md,
                      used_sentence_starter_source, status, assistant_reply_md,
                      sentence_starters, generation_attempts, error_code, null, null
            """,
            (session_id, round_nr, student_message, starter_text, starter_source, idempotency_key),
        )
        turn = _turn(cur.fetchone())
        conn.commit()
        return turn
    finally:
        cur.close()
        conn.close()


def begin_retry(repo, *, course_id: str, task_id: str, session_id: str, turn_id: str, student_sub: str) -> dict[str, Any]:
    conn, cur = _connect(repo, student_sub=student_sub, course_id=course_id)
    try:
        cur.execute(
            """
            update public.learning_dialog_turns t
               set status = 'generating', error_code = null,
                   generation_attempts = generation_attempts + 1,
                   generation_started_at = now()
              from public.learning_dialog_sessions s
             where t.id = %s::uuid and t.session_id = %s::uuid
               and s.id = t.session_id and s.course_id = %s::uuid and s.task_id = %s::uuid
               and s.status = 'active' and t.status = 'failed' and t.generation_attempts < 3
            returning t.id::text, t.round_nr, t.student_message_md,
                      t.used_sentence_starter_md, t.used_sentence_starter_source,
                      t.status, t.assistant_reply_md, t.sentence_starters,
                      t.generation_attempts, t.error_code, null, null
            """,
            (turn_id, session_id, course_id, task_id),
        )
        row = cur.fetchone()
        if not row:
            raise ValueError("dialog_retry_not_allowed")
        conn.commit()
        return _turn(row)
    finally:
        cur.close()
        conn.close()


def complete_turn(repo, *, course_id: str, task_id: str, session_id: str, turn_id: str, student_sub: str, ai_message: str, next_starters: list[str]) -> dict[str, Any]:
    conn, cur = _connect(repo, student_sub=student_sub, course_id=course_id)
    try:
        _read_session(cur, course_id=course_id, task_id=task_id, session_id=session_id, for_update=True)
        cur.execute(
            """
            update public.learning_dialog_turns
               set status = 'completed', assistant_reply_md = %s,
                   sentence_starters = %s, error_code = null, completed_at = now()
             where id = %s::uuid and session_id = %s::uuid and status = 'generating'
            """,
            (ai_message, next_starters, turn_id, session_id),
        )
        if cur.rowcount != 1:
            raise ValueError("invalid_dialog_turn_state")
        cur.execute(
            """
            update public.learning_dialog_sessions
               set round_count = round_count + 1
             where id = %s::uuid and status = 'active'
            """,
            (session_id,),
        )
        session = _read_session(cur, course_id=course_id, task_id=task_id, session_id=session_id)
        conn.commit()
        return session
    finally:
        cur.close()
        conn.close()


def fail_turn(repo, *, course_id: str, task_id: str, session_id: str, turn_id: str, student_sub: str, error_code: str) -> None:
    conn, cur = _connect(repo, student_sub=student_sub, course_id=course_id)
    try:
        cur.execute(
            """
            update public.learning_dialog_turns t
               set status = 'failed', error_code = %s
              from public.learning_dialog_sessions s
             where t.id = %s::uuid and t.session_id = %s::uuid and t.status = 'generating'
               and s.id = t.session_id and s.course_id = %s::uuid and s.task_id = %s::uuid
            """,
            (error_code, turn_id, session_id, course_id, task_id),
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()


def _submission_dict(row: Sequence[object]) -> dict[str, Any]:
    return {
        "id": row[0], "attempt_nr": int(row[1]), "intent": "submit", "kind": "dialog",
        "dialog_session_id": row[2], "analysis_status": row[3], "analysis_json": row[4],
        "feedback_md": row[5], "error_code": row[6], "created_at": row[7], "completed_at": row[8],
    }


def complete_session(repo, *, course_id: str, task_id: str, session_id: str, student_sub: str, closing_answer_md: str | None, idempotency_key: str) -> dict[str, Any]:
    conn, cur = _connect(repo, student_sub=student_sub, course_id=course_id)
    try:
        session = _read_session(cur, course_id=course_id, task_id=task_id, session_id=session_id, for_update=True)
        cur.execute(
            """
            select id::text, attempt_nr, dialog_session_id::text, analysis_status,
                   analysis_json, feedback_md, error_code,
                   to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                   to_char(completed_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
              from public.learning_submissions where dialog_session_id = %s::uuid
            """,
            (session_id,),
        )
        existing = cur.fetchone()
        if existing:
            return {"session": session, "submission": _submission_dict(existing)}
        if session["status"] != "active" or session["round_count"] < 1:
            raise ValueError("invalid_dialog_session_state")
        context = _read_context(cur, course_id=course_id, task_id=task_id, session_id=session_id)
        if context["max_attempts"] is not None:
            cur.execute(
                """
                select count(*)
                  from public.learning_submissions
                 where course_id=%s::uuid and task_id=%s::uuid
                   and student_sub=%s and intent='submit' and kind='dialog'
                """,
                (course_id, task_id, student_sub),
            )
            if int(cur.fetchone()[0] or 0) >= context["max_attempts"]:
                raise ValueError("max_attempts_exceeded")
        cur.execute("select section_id::text from public.unit_tasks where id=%s::uuid", (task_id,))
        section_row = cur.fetchone()
        if not section_row:
            raise LookupError("dialog_task_not_found")
        cur.execute("select public.next_attempt_nr(%s::uuid, %s::uuid, %s)", (course_id, task_id, student_sub))
        attempt_nr = int(cur.fetchone()[0])
        submission_id = str(uuid5(_SUBMISSION_NAMESPACE, f"{course_id}:{task_id}:{student_sub}:{idempotency_key}"))
        cur.execute(
            """
            insert into public.learning_submissions (
              id, course_id, task_id, section_id, student_sub, intent, kind,
              attempt_nr, analysis_status, idempotency_key, dialog_session_id,
              internal_metadata
            ) values (%s::uuid, %s::uuid, %s::uuid, %s::uuid, %s, 'submit', 'dialog',
                      %s, 'pending', %s, %s::uuid, jsonb_build_object('analysis_mode', 'dialog'))
            returning id::text, attempt_nr, dialog_session_id::text, analysis_status,
                      analysis_json, feedback_md, error_code,
                      to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                      to_char(completed_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
            """,
            (submission_id, course_id, task_id, section_row[0], student_sub, attempt_nr, idempotency_key, session_id),
        )
        submission = _submission_dict(cur.fetchone())
        cur.execute(
            """
            select student_message_md, used_sentence_starter_md,
                   used_sentence_starter_source, assistant_reply_md
              from public.learning_dialog_turns
             where session_id=%s::uuid and status='completed' order by round_nr
            """,
            (session_id,),
        )
        turns = list(cur.fetchall() or [])
        config = context["dialog_config"]
        payload = {
            "submission_id": submission_id,
            "course_id": course_id,
            "task_id": task_id,
            "task_kind": "dialog",
            "student_sub": student_sub,
            "intent": "submit",
            "kind": "dialog",
            "attempt_nr": attempt_nr,
            "criteria": context["criteria"],
            "instruction_md": context["instruction_md"],
            "analysis_mode": "dialog",
            "student_performance": {
                "messages": [
                    {"text": row[0], "starter_text": row[1], "starter_source": row[2]} for row in turns
                ],
                "closing_answer_md": closing_answer_md,
            },
            "conversation_context": {
                "opening_message_md": config["opening_message_md"],
                "assistant_messages": [row[3] for row in turns],
            },
        }
        queue_table = repo._resolve_queue_table(cur)
        statement = repo._sql.SQL("insert into public.{} (submission_id, payload) values (%s::uuid, %s)").format(
            repo._sql.Identifier(queue_table)
        )
        cur.execute(statement, (submission_id, repo._json_adapter(payload)))
        cur.execute(
            """
            update public.learning_dialog_sessions
               set status='completed', closing_answer_md=%s,
                   completion_idempotency_key=%s, completed_at=now()
             where id=%s::uuid and status='active'
            """,
            (closing_answer_md, idempotency_key, session_id),
        )
        completed = _read_session(cur, course_id=course_id, task_id=task_id, session_id=session_id)
        conn.commit()
        return {"session": completed, "submission": submission}
    finally:
        cur.close()
        conn.close()


def abandon_session(repo, *, course_id: str, task_id: str, session_id: str, student_sub: str) -> dict[str, Any]:
    conn, cur = _connect(repo, student_sub=student_sub, course_id=course_id)
    try:
        session = _read_session(cur, course_id=course_id, task_id=task_id, session_id=session_id, for_update=True)
        turns = session["turns"]
        exhausted_failure = bool(turns and turns[-1]["status"] == "failed" and turns[-1]["generation_attempts"] >= 3)
        if session["status"] != "active" or (turns and not exhausted_failure):
            raise ValueError("dialog_abandon_not_allowed")
        cur.execute(
            "update public.learning_dialog_sessions set status='abandoned', abandoned_at=now() where id=%s::uuid",
            (session_id,),
        )
        abandoned = _read_session(cur, course_id=course_id, task_id=task_id, session_id=session_id)
        conn.commit()
        return abandoned
    finally:
        cur.close()
        conn.close()


def record_usage_events(repo, *, stage: str, course_id: str, task_id: str, session_id: str, student_sub: str, events: Sequence[Any]) -> None:
    """Persist technical counters only; no prompt or response content is accepted."""

    conn, cur = _connect(repo, student_sub=student_sub, course_id=course_id)
    try:
        cur.execute("select unit_id::text from public.unit_tasks where id=%s::uuid", (task_id,))
        row = cur.fetchone()
        if not row:
            raise LookupError("dialog_task_not_found")
        unit_id = row[0]
        for event in events:
            cur.execute(
                """
                insert into public.dialog_ai_usage_events (
                  event_key, session_id, course_id, unit_id, task_id, actor_sub,
                  actor_role, stage, model, usage_known, input_tokens,
                  output_tokens, total_tokens, unknown_reason, error_code
                ) values (%s::uuid,%s::uuid,%s::uuid,%s::uuid,%s::uuid,%s,
                          'student',%s,%s,%s,%s,%s,%s,%s,%s)
                on conflict (event_key) do nothing
                """,
                (
                    event.event_key, session_id, course_id, unit_id, task_id, student_sub,
                    stage, event.model, event.usage_known, event.input_tokens,
                    event.output_tokens, event.total_tokens, event.unknown_reason,
                    getattr(event, "error_code", None),
                ),
            )
        conn.commit()
    finally:
        cur.close()
        conn.close()
