"""Learner HTTP adapter for AI dialog sessions."""

from __future__ import annotations

import re
import sys
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.learning.usecases.dialogs import DialogServiceUnavailable, DialogUseCases


learning_dialog_router = APIRouter(tags=["Learning"])
_USECASES: Any | None = None


def _learning_facade():  # type: ignore[no-untyped-def]
    module = sys.modules.get("backend.web.routes.learning")
    if module is None:
        import backend.web.routes.learning as module  # type: ignore
    return module


def set_dialog_dependencies(*, usecases: Any | None = None) -> None:
    """Override dialog use cases in focused adapter tests."""

    global _USECASES
    _USECASES = usecases


def _usecases() -> Any:
    if _USECASES is not None:
        return _USECASES
    from backend.learning.adapters.local_dialog import build

    return DialogUseCases(_learning_facade()._get_repo(), build())


def _ids(*values: str) -> bool:
    try:
        for value in values:
            UUID(value)
        return True
    except (TypeError, ValueError):
        return False


def _key(request: Request) -> str:
    value = str(request.headers.get("Idempotency-Key") or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", value):
        raise ValueError("invalid_idempotency_key")
    return value


def _student(request: Request):  # type: ignore[no-untyped-def]
    facade = _learning_facade()
    user, error = facade._require_student(request)
    if error:
        return None, error
    return str(user.get("sub") or ""), None


def _mutation_guard(request: Request):  # type: ignore[no-untyped-def]
    facade = _learning_facade()
    if not facade._require_strict_same_origin(request):
        return JSONResponse(
            {"error": "forbidden", "detail": "csrf_violation"},
            status_code=403,
            headers=facade._cache_headers_error(),
        )
    return None


def _result(call, *, success_status: int = 200):  # type: ignore[no-untyped-def]
    facade = _learning_facade()
    try:
        return JSONResponse(_public_payload(call()), status_code=success_status, headers=facade._cache_headers_success())
    except DialogServiceUnavailable as exc:
        return JSONResponse(
            {"error": "service_unavailable", "detail": str(exc) or "dialog_ai_unavailable"},
            status_code=503,
            headers=facade._cache_headers_error(),
        )
    except PermissionError:
        return JSONResponse({"error": "forbidden"}, status_code=403, headers=facade._cache_headers_error())
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404, headers=facade._cache_headers_error())
    except ValueError as exc:
        detail = str(exc) or "invalid_input"
        state_errors = {
            "dialog_generation_pending",
            "dialog_previous_turn_incomplete",
            "dialog_round_limit_reached",
            "dialog_retry_not_allowed",
            "invalid_dialog_session_state",
            "invalid_dialog_turn_state",
            "dialog_abandon_not_allowed",
            "max_attempts_exceeded",
        }
        status = 409 if detail in state_errors else 400
        return JSONResponse(
            {"error": "conflict" if status == 409 else "bad_request", "detail": detail},
            status_code=status,
            headers=facade._cache_headers_error(),
        )


def _public_payload(value: Any) -> Any:
    """Translate internal repository names to the strict OpenAPI projection."""

    if isinstance(value, dict) and "session" in value:
        return {**value, "session": _public_payload(value["session"])}
    if not isinstance(value, dict) or "turns" not in value or "round_count" not in value:
        return value
    dialog = {
        "partner_name": value.get("partner_name"),
        "partner_description_md": value.get("partner_description_md"),
        "opening_message_md": value.get("opening_message_md"),
        "response_mode": value.get("response_mode"),
        "max_rounds": value.get("max_rounds"),
        "closing_prompt_md": value.get("closing_prompt_md"),
    }
    turns = [
        {
            "id": turn.get("id"),
            "round_nr": turn.get("round_nr"),
            "student_message_md": turn.get("student_message"),
            "used_sentence_starter_md": turn.get("starter_text"),
            "used_sentence_starter_source": turn.get("starter_source"),
            "status": turn.get("status"),
            "assistant_reply_md": turn.get("ai_message"),
            "sentence_starters": turn.get("next_starters") or [],
            "generation_attempts": turn.get("generation_attempts"),
            "error_code": turn.get("error_code"),
            "created_at": turn.get("created_at"),
            "completed_at": turn.get("completed_at"),
        }
        for turn in value.get("turns") or []
    ]
    return {
        "id": value.get("id"),
        "course_id": value.get("course_id"),
        "task_id": value.get("task_id"),
        "status": value.get("status"),
        "round_count": value.get("round_count"),
        "dialog": dialog,
        "initial_sentence_starters": value.get("initial_starters") or [],
        "initial_starters_status": value.get("initial_generation_status"),
        "initial_starters_error_code": value.get("initial_generation_error_code"),
        "initial_generation_attempts": value.get("initial_generation_attempts", 0),
        "turns": turns,
        "closing_answer_md": value.get("closing_answer_md"),
        "created_at": value.get("created_at"),
        "updated_at": value.get("updated_at"),
        "completed_at": value.get("completed_at"),
    }


@learning_dialog_router.post("/api/learning/courses/{course_id}/tasks/{task_id}/dialog-sessions")
async def start_dialog_session(request: Request, course_id: str, task_id: str):
    if (error := _mutation_guard(request)) is not None:
        return error
    student_sub, error = _student(request)
    if error:
        return error
    if not _ids(course_id, task_id):
        return _result(lambda: (_ for _ in ()).throw(ValueError("invalid_uuid")))
    return _result(
        lambda: _usecases().start(course_id=course_id, task_id=task_id, student_sub=student_sub),
        success_status=201,
    )


@learning_dialog_router.get("/api/learning/courses/{course_id}/tasks/{task_id}/dialog-sessions/{session_id}")
async def get_dialog_session(request: Request, course_id: str, task_id: str, session_id: str):
    student_sub, error = _student(request)
    if error:
        return error
    if not _ids(course_id, task_id, session_id):
        return _result(lambda: (_ for _ in ()).throw(ValueError("invalid_uuid")))
    return _result(
        lambda: _usecases().get(
            course_id=course_id, task_id=task_id, session_id=session_id, student_sub=student_sub
        )
    )


@learning_dialog_router.post("/api/learning/courses/{course_id}/tasks/{task_id}/dialog-sessions/{session_id}/turns")
async def send_dialog_turn(request: Request, course_id: str, task_id: str, session_id: str, payload: dict[str, Any]):
    if (error := _mutation_guard(request)) is not None:
        return error
    student_sub, error = _student(request)
    if error:
        return error
    return _result(
        lambda: _usecases().send_turn(
            course_id=course_id,
            task_id=task_id,
            session_id=session_id,
            student_sub=student_sub,
            student_message=payload.get("student_message_md"),
            starter_text=payload.get("used_sentence_starter_md"),
            starter_source=payload.get("used_sentence_starter_source"),
            idempotency_key=_key(request),
        )
        if _ids(course_id, task_id, session_id)
        else (_ for _ in ()).throw(ValueError("invalid_uuid"))
    )


@learning_dialog_router.post("/api/learning/courses/{course_id}/tasks/{task_id}/dialog-sessions/{session_id}/turns/{turn_id}/retry")
async def retry_dialog_turn(request: Request, course_id: str, task_id: str, session_id: str, turn_id: str):
    if (error := _mutation_guard(request)) is not None:
        return error
    student_sub, error = _student(request)
    if error:
        return error
    return _result(
        lambda: _usecases().retry_turn(
            course_id=course_id,
            task_id=task_id,
            session_id=session_id,
            turn_id=turn_id,
            student_sub=student_sub,
        )
        if _ids(course_id, task_id, session_id, turn_id)
        else (_ for _ in ()).throw(ValueError("invalid_uuid"))
    )


@learning_dialog_router.post("/api/learning/courses/{course_id}/tasks/{task_id}/dialog-sessions/{session_id}/complete")
async def complete_dialog_session(request: Request, course_id: str, task_id: str, session_id: str, payload: dict[str, Any]):
    if (error := _mutation_guard(request)) is not None:
        return error
    student_sub, error = _student(request)
    if error:
        return error
    return _result(
        lambda: _usecases().complete(
            course_id=course_id,
            task_id=task_id,
            session_id=session_id,
            student_sub=student_sub,
            closing_answer_md=payload.get("closing_answer_md"),
            idempotency_key=_key(request),
        )
        if _ids(course_id, task_id, session_id)
        else (_ for _ in ()).throw(ValueError("invalid_uuid"))
    )


@learning_dialog_router.post("/api/learning/courses/{course_id}/tasks/{task_id}/dialog-sessions/{session_id}/abandon")
async def abandon_dialog_session(request: Request, course_id: str, task_id: str, session_id: str):
    if (error := _mutation_guard(request)) is not None:
        return error
    student_sub, error = _student(request)
    if error:
        return error
    return _result(
        lambda: _usecases().abandon(
            course_id=course_id, task_id=task_id, session_id=session_id, student_sub=student_sub
        )
        if _ids(course_id, task_id, session_id)
        else (_ for _ in ()).throw(ValueError("invalid_uuid"))
    )
