"""Framework-independent use cases for AI dialog tasks.

Why:
    Keep dialog state rules, input limits and model-output validation outside
    FastAPI and DSPy. The repository owns transactions/RLS; the generator owns
    provider calls. This layer deliberately never logs conversation content.
"""

from __future__ import annotations

from copy import deepcopy
import json
from typing import Any, Protocol, Sequence


MAX_MESSAGE_CHARS = 2_000
MAX_STARTER_CHARS = 240
MAX_STARTERS = 3
MAX_MODEL_CONTEXT_CHARS = 24_000


class DialogServiceUnavailable(RuntimeError):
    """A retryable model failure with a stable, content-free public code."""


class DialogRepoProtocol(Protocol):
    def start_or_resume(self, **kwargs: Any) -> dict[str, Any]: ...
    def claim_initial_starters(self, **kwargs: Any) -> bool: ...
    def set_initial_starters(self, **kwargs: Any) -> dict[str, Any]: ...
    def fail_initial_starters(self, **kwargs: Any) -> None: ...
    def get_session(self, **kwargs: Any) -> dict[str, Any]: ...
    def begin_turn(self, **kwargs: Any) -> dict[str, Any]: ...
    def begin_retry(self, **kwargs: Any) -> dict[str, Any]: ...
    def generation_context(self, **kwargs: Any) -> dict[str, Any]: ...
    def complete_turn(self, **kwargs: Any) -> dict[str, Any]: ...
    def fail_turn(self, **kwargs: Any) -> None: ...
    def complete_session(self, **kwargs: Any) -> dict[str, Any]: ...
    def abandon_session(self, **kwargs: Any) -> dict[str, Any]: ...


class DialogGeneratorProtocol(Protocol):
    def initial_starters(self, **kwargs: Any) -> Sequence[str]: ...
    def partner_reply(self, **kwargs: Any) -> dict[str, Any]: ...


def _message(value: object) -> str:
    text = value.strip() if isinstance(value, str) else ""
    if not text or len(text) > MAX_MESSAGE_CHARS:
        raise ValueError("invalid_dialog_message")
    return text


def _starters(value: object) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, (list, tuple)) or len(value) > MAX_STARTERS:
        raise ValueError("invalid_dialog_generation")
    result: list[str] = []
    for item in value:
        text = item.strip() if isinstance(item, str) else ""
        if not text or len(text) > MAX_STARTER_CHARS:
            raise ValueError("invalid_dialog_generation")
        result.append(text)
    return result


def _starter_provenance(starter_text: object, starter_source: object) -> tuple[str | None, str | None]:
    if starter_text is None and starter_source is None:
        return None, None
    text = starter_text.strip() if isinstance(starter_text, str) else ""
    source = starter_source.strip() if isinstance(starter_source, str) else ""
    if not text or len(text) > MAX_STARTER_CHARS or not source or len(source) > 80:
        raise ValueError("invalid_dialog_starter")
    return text, source


def _bounded_context(context: dict[str, Any]) -> dict[str, Any]:
    """Keep the newest complete turns while enforcing a provider context cap."""

    bounded = deepcopy(context)
    turns = list(bounded.get("turns") or [])
    bounded["turns"] = []
    for turn in reversed(turns):
        candidate = [turn, *bounded["turns"]]
        bounded["turns"] = candidate
        if len(json.dumps(bounded, ensure_ascii=False, default=str)) > MAX_MODEL_CONTEXT_CHARS:
            bounded["turns"] = candidate[1:]
            break
    if len(json.dumps(bounded, ensure_ascii=False, default=str)) > MAX_MODEL_CONTEXT_CHARS:
        raise ValueError("dialog_context_too_large")
    return bounded


class DialogUseCases:
    """Coordinate dialog state changes with a stateless AI generator.

    Permissions:
        Every repository call is scoped by course, task, session and student.
        The persistence adapter must enforce membership, release visibility and
        row ownership with RLS-aware queries.
    """

    def __init__(self, repo: DialogRepoProtocol, generator: DialogGeneratorProtocol) -> None:
        self._repo = repo
        self._generator = generator

    def _record_usage(
        self,
        *,
        stage: str,
        course_id: str,
        task_id: str,
        session_id: str,
        student_sub: str,
        error_code: str | None = None,
    ) -> None:
        pop = getattr(self._generator, "pop_usage_events", None)
        record = getattr(self._repo, "record_usage_events", None)
        if not callable(pop) or not callable(record):
            return
        try:
            events = list(pop() or [])
            if events:
                if error_code is not None:
                    for event in events:
                        event.error_code = error_code
                record(
                    stage=stage,
                    course_id=course_id,
                    task_id=task_id,
                    session_id=session_id,
                    student_sub=student_sub,
                    events=events,
                )
        except Exception:
            # Usage accounting must never duplicate or lose the pedagogical turn.
            return

    def start(self, *, course_id: str, task_id: str, student_sub: str) -> dict[str, Any]:
        session = self._repo.start_or_resume(course_id=course_id, task_id=task_id, student_sub=student_sub)
        if (
            session.get("status") == "active"
            and session.get("response_mode") == "hybrid"
            and session.get("initial_generation_status") in {"pending", "failed"}
            and int(session.get("initial_generation_attempts") or 0) < 3
        ):
            claimed = self._repo.claim_initial_starters(
                course_id=course_id,
                task_id=task_id,
                session_id=session["id"],
                student_sub=student_sub,
            )
            if not claimed:
                return self.get(
                    course_id=course_id, task_id=task_id,
                    session_id=session["id"], student_sub=student_sub,
                )
            try:
                context = _bounded_context(
                    self._repo.generation_context(
                        course_id=course_id,
                        task_id=task_id,
                        session_id=session["id"],
                        student_sub=student_sub,
                    )
                )
                starters = _starters(self._generator.initial_starters(context=context))
                session = self._repo.set_initial_starters(
                    course_id=course_id,
                    task_id=task_id,
                    session_id=session["id"],
                    student_sub=student_sub,
                    starters=starters,
                )
                self._record_usage(
                    stage="initial_starters", course_id=course_id, task_id=task_id,
                    session_id=session["id"], student_sub=student_sub,
                )
            except Exception as exc:
                self._record_usage(
                    stage="initial_starters", course_id=course_id, task_id=task_id,
                    session_id=session["id"], student_sub=student_sub,
                    error_code="dialog_ai_unavailable",
                )
                self._repo.fail_initial_starters(
                    course_id=course_id,
                    task_id=task_id,
                    session_id=session["id"],
                    student_sub=student_sub,
                    error_code="dialog_ai_unavailable",
                )
                raise DialogServiceUnavailable("dialog_ai_unavailable") from exc
        return session

    def get(self, *, course_id: str, task_id: str, session_id: str, student_sub: str) -> dict[str, Any]:
        return self._repo.get_session(
            course_id=course_id, task_id=task_id, session_id=session_id, student_sub=student_sub
        )

    def send_turn(
        self,
        *,
        course_id: str,
        task_id: str,
        session_id: str,
        student_sub: str,
        student_message: object,
        idempotency_key: str,
        starter_text: object = None,
        starter_source: object = None,
    ) -> dict[str, Any]:
        message = _message(student_message)
        used_starter, source = _starter_provenance(starter_text, starter_source)
        turn = self._repo.begin_turn(
            course_id=course_id,
            task_id=task_id,
            session_id=session_id,
            student_sub=student_sub,
            student_message=message,
            starter_text=used_starter,
            starter_source=source,
            idempotency_key=idempotency_key,
        )
        if turn.get("status") == "completed":
            return self.get(
                course_id=course_id, task_id=task_id, session_id=session_id, student_sub=student_sub
            )
        return self._generate_turn(
            course_id=course_id,
            task_id=task_id,
            session_id=session_id,
            student_sub=student_sub,
            turn=turn,
        )

    def retry_turn(
        self,
        *,
        course_id: str,
        task_id: str,
        session_id: str,
        turn_id: str,
        student_sub: str,
    ) -> dict[str, Any]:
        turn = self._repo.begin_retry(
            course_id=course_id,
            task_id=task_id,
            session_id=session_id,
            turn_id=turn_id,
            student_sub=student_sub,
        )
        return self._generate_turn(
            course_id=course_id,
            task_id=task_id,
            session_id=session_id,
            student_sub=student_sub,
            turn=turn,
        )

    def _generate_turn(
        self,
        *,
        course_id: str,
        task_id: str,
        session_id: str,
        student_sub: str,
        turn: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            context = _bounded_context(
                self._repo.generation_context(
                    course_id=course_id,
                    task_id=task_id,
                    session_id=session_id,
                    student_sub=student_sub,
                )
            )
            generated = self._generator.partner_reply(context=context, turn=dict(turn))
            if not isinstance(generated, dict):
                raise ValueError("invalid_dialog_generation")
            ai_message = _message(generated.get("message"))
            starters = _starters(generated.get("starters"))
            if context.get("response_mode") != "hybrid" or int(turn["round_nr"]) >= int(context["max_rounds"]):
                starters = []
            completed = self._repo.complete_turn(
                course_id=course_id,
                task_id=task_id,
                session_id=session_id,
                turn_id=turn["id"],
                student_sub=student_sub,
                ai_message=ai_message,
                next_starters=starters,
            )
            self._record_usage(
                stage="reply", course_id=course_id, task_id=task_id,
                session_id=session_id, student_sub=student_sub,
            )
            return completed
        except Exception as exc:
            self._record_usage(
                stage="reply", course_id=course_id, task_id=task_id,
                session_id=session_id, student_sub=student_sub,
                error_code="dialog_ai_unavailable",
            )
            self._repo.fail_turn(
                course_id=course_id,
                task_id=task_id,
                session_id=session_id,
                turn_id=turn["id"],
                student_sub=student_sub,
                error_code="dialog_ai_unavailable",
            )
            raise DialogServiceUnavailable("dialog_ai_unavailable") from exc

    def complete(
        self,
        *,
        course_id: str,
        task_id: str,
        session_id: str,
        student_sub: str,
        closing_answer_md: object,
        idempotency_key: str,
    ) -> dict[str, Any]:
        session = self.get(
            course_id=course_id, task_id=task_id, session_id=session_id, student_sub=student_sub
        )
        if int(session.get("round_count") or 0) < 1:
            raise ValueError("dialog_requires_completed_turn")
        closing: str | None = None
        if session.get("closing_prompt_md"):
            if not isinstance(closing_answer_md, str) or not closing_answer_md.strip():
                raise ValueError("closing_answer_required")
            closing = _message(closing_answer_md)
        elif isinstance(closing_answer_md, str) and closing_answer_md.strip():
            closing = _message(closing_answer_md)
        return self._repo.complete_session(
            course_id=course_id,
            task_id=task_id,
            session_id=session_id,
            student_sub=student_sub,
            closing_answer_md=closing,
            idempotency_key=idempotency_key,
        )

    def abandon(self, *, course_id: str, task_id: str, session_id: str, student_sub: str) -> dict[str, Any]:
        return self._repo.abandon_session(
            course_id=course_id, task_id=task_id, session_id=session_id, student_sub=student_sub
        )
