"""Teaching unit task routes.

Why:
    Task endpoints delegate to a dedicated TasksService, so their HTTP adapter
    can live outside the large `teaching.py` module without duplicating domain
    logic.
"""

from __future__ import annotations

from typing import Dict

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from backend.teaching.errors import TeachingRepositoryUnavailable
from backend.web.routes import teaching_authoring, teaching_guards
from backend.web.routes.teaching import _get_repo
from backend.web.routes.teaching_payloads import TaskCreatePayload, TaskReorderPayload, TaskUpdatePayload
from backend.web.routes.teaching_serialization import _serialize_task
from backend.web.routes.teaching_shared import (
    _current_sub,
    _is_uuid_like,
    _json_private,
    _private_error,
    _require_teacher,
)
from backend.web.routes.teaching_task_services import _get_tasks_service
from backend.learning.usecases.dialogs import _message as _dialog_message, _starters as _dialog_starters
from backend.web.routes.learning_dialogs import _public_payload as _public_dialog_payload


teaching_unit_tasks_router = APIRouter(tags=["Teaching"])

_TASK_VALIDATION_DETAILS = {
    "invalid_instruction_md",
    "invalid_criteria",
    "invalid_due_at",
    "invalid_max_attempts",
    "invalid_teacher_context_md",
    "invalid_model_solution_md",
    "invalid_h5p_config",
    "invalid_visual_config",
    "invalid_scratch_config",
    "invalid_calliope_config",
    "invalid_filius_config",
    "invalid_dialog_config",
    "invalid_task_kind_config",
    "practice_fields_required",
    "practice_schedule_fields_forbidden",
    "practice_task_kind_not_supported",
}


def _dialog_generator():
    from backend.learning.adapters.local_dialog import build

    return build()


def _record_preview_usage(
    generator,
    *,
    unit_id: str,
    task_id: str,
    author_sub: str,
    error_code: str | None = None,
) -> None:
    """Persist content-free preview telemetry without changing the preview result."""

    pop_usage = getattr(generator, "pop_usage_events", None)
    if not callable(pop_usage):
        return
    try:
        events = list(pop_usage() or [])
        if error_code is not None:
            for event in events:
                event.error_code = error_code
        _get_repo().record_dialog_preview_usage(
            unit_id=unit_id,
            task_id=task_id,
            author_id=author_sub,
            events=events,
        )
    except TeachingRepositoryUnavailable:
        raise
    except Exception:
        # Telemetry contains no pedagogical state and must not hide a valid preview.
        return


def _task_bad_request(exc: ValueError):
    detail = str(exc) or "invalid_input"
    if detail not in _TASK_VALIDATION_DETAILS:
        detail = "invalid_input"
    return _private_error({"error": "bad_request", "detail": detail}, status_code=400)


@teaching_unit_tasks_router.get("/api/teaching/units/{unit_id}/sections/{section_id}/tasks")
async def list_section_tasks(request: Request, unit_id: str, section_id: str):
    """List tasks for a section owned by the authoring teacher."""

    user, error = _require_teacher(request)
    if error:
        return error
    if not _is_uuid_like(unit_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    if not _is_uuid_like(section_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_section_id"}, status_code=400)
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    try:
        items = _get_tasks_service().list_tasks(unit_id, section_id, sub)
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404)
    return _json_private([_serialize_task(task) for task in items], status_code=200)


@teaching_unit_tasks_router.post("/api/teaching/units/{unit_id}/sections/{section_id}/tasks")
async def create_section_task(
    request: Request,
    unit_id: str,
    section_id: str,
    payload: TaskCreatePayload,
):
    """Create a task in a section owned by the authoring teacher."""

    user, error = _require_teacher(request)
    if error:
        return error
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    if not _is_uuid_like(unit_id):
        return _private_error({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    if not _is_uuid_like(section_id):
        return _private_error({"error": "bad_request", "detail": "invalid_section_id"}, status_code=400)
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    try:
        task = _get_tasks_service().create_task(
            unit_id,
            section_id,
            sub,
            instruction_md=payload.instruction_md,
            criteria=payload.criteria,
            teacher_context_md=payload.teacher_context_md,
            model_solution_md=payload.model_solution_md,
            due_at=payload.due_at,
            max_attempts=payload.max_attempts,
            h5p=payload.h5p,
            visual=payload.visual,
            scratch=payload.scratch,
            calliope=payload.calliope,
            filius=payload.filius,
            dialog=payload.dialog,
        )
    except LookupError:
        return _private_error({"error": "not_found"}, status_code=404)
    except ValueError as exc:
        return _task_bad_request(exc)
    except PermissionError:
        return _private_error({"error": "forbidden"}, status_code=403)
    return _json_private(_serialize_task(task), status_code=201)


@teaching_unit_tasks_router.patch("/api/teaching/units/{unit_id}/sections/{section_id}/tasks/{task_id}")
async def update_section_task(
    request: Request,
    unit_id: str,
    section_id: str,
    task_id: str,
    payload: TaskUpdatePayload,
):
    """Update a task in a section owned by the authoring teacher."""

    user, error = _require_teacher(request)
    if error:
        return error
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    if not _is_uuid_like(unit_id):
        return _private_error({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    if not _is_uuid_like(section_id):
        return _private_error({"error": "bad_request", "detail": "invalid_section_id"}, status_code=400)
    if not _is_uuid_like(task_id):
        return _private_error({"error": "bad_request", "detail": "invalid_task_id"}, status_code=400)
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    raw_updates = payload.model_dump(mode="python", exclude_unset=True)
    if not raw_updates:
        return _private_error({"error": "bad_request", "detail": "empty_payload"}, status_code=400)
    kwargs: Dict[str, object] = {}
    for key in (
        "instruction_md",
        "criteria",
        "teacher_context_md",
        "model_solution_md",
        "due_at",
        "max_attempts",
        "h5p",
        "visual",
        "scratch",
        "calliope",
        "filius",
        "dialog",
    ):
        if key in raw_updates:
            kwargs[key] = raw_updates[key]
    try:
        updated = _get_tasks_service().update_task(unit_id, section_id, task_id, sub, **kwargs)
    except ValueError as exc:
        return _task_bad_request(exc)
    except LookupError:
        return _private_error({"error": "not_found"}, status_code=404)
    except PermissionError:
        return _private_error({"error": "forbidden"}, status_code=403)
    return _json_private(_serialize_task(updated), status_code=200)


@teaching_unit_tasks_router.post("/api/teaching/units/{unit_id}/tasks/{task_id}/dialog-preview")
async def preview_dialog_task(request: Request, unit_id: str, task_id: str, payload: dict):
    """Generate one stateless response from the latest saved configuration."""

    user, error = _require_teacher(request)
    if error:
        return error
    if (csrf := teaching_guards._csrf_guard(request)) is not None:
        return csrf
    if not _is_uuid_like(unit_id) or not _is_uuid_like(task_id):
        return _private_error({"error": "bad_request", "detail": "invalid_uuid"}, status_code=400)
    author_sub = _current_sub(user)
    task = _get_repo().get_dialog_task_for_author(unit_id, task_id, author_sub)
    if not task:
        return _private_error({"error": "not_found"}, status_code=404)
    operation = payload.get("operation")
    messages = payload.get("messages")
    if operation not in {"initial_starters", "reply"} or not isinstance(messages, list) or len(messages) > 24:
        return _private_error({"error": "bad_request", "detail": "invalid_dialog_preview"}, status_code=400)
    completed_turns: list[dict] = []
    pending_student: str | None = None
    current_student: str | None = None
    try:
        for item in messages:
            if not isinstance(item, dict) or item.get("role") not in {"student", "assistant"}:
                raise ValueError("invalid_dialog_preview")
            content = _dialog_message(item.get("body_md"))
            if item["role"] == "student":
                pending_student = content
            elif pending_student is not None:
                completed_turns.append({"student_message": pending_student, "ai_message": content})
                pending_student = None
        task["turns"] = completed_turns
        if operation == "reply":
            current_student = _dialog_message(payload.get("student_message_md") or pending_student)
    except ValueError as exc:
        return _private_error({"error": "bad_request", "detail": str(exc)}, status_code=400)

    generator = _dialog_generator()
    try:
        if operation == "initial_starters":
            starters = _dialog_starters(generator.initial_starters(context=task))
            result = {"reply_md": None, "sentence_starters": starters}
        else:
            generated = generator.partner_reply(
                context=task,
                turn={"student_message": current_student},
            )
            result = {
                "reply_md": _dialog_message(generated.get("message")),
                "sentence_starters": _dialog_starters(generated.get("starters")),
            }
        _record_preview_usage(
            generator, unit_id=unit_id, task_id=task_id, author_sub=author_sub
        )
    except Exception:
        _record_preview_usage(
            generator,
            unit_id=unit_id,
            task_id=task_id,
            author_sub=author_sub,
            error_code="dialog_ai_unavailable",
        )
        return _private_error(
            {"error": "service_unavailable", "detail": "dialog_ai_unavailable"}, status_code=503
        )
    return _json_private(result, status_code=200)


@teaching_unit_tasks_router.get(
    "/api/teaching/courses/{course_id}/units/{unit_id}/tasks/{task_id}/students/{student_sub:path}/submissions/{submission_id}/dialog"
)
async def get_dialog_submission_transcript(
    request: Request,
    course_id: str,
    unit_id: str,
    task_id: str,
    student_sub: str,
    submission_id: str,
):
    """Return a completed transcript without frozen internal instructions."""

    user, error = _require_teacher(request)
    if error:
        return error
    if not all(_is_uuid_like(value) for value in (course_id, unit_id, task_id, submission_id)):
        return _private_error({"error": "bad_request", "detail": "invalid_uuid"}, status_code=400)
    transcript = _get_repo().get_dialog_submission_for_owner(
        course_id=course_id,
        unit_id=unit_id,
        task_id=task_id,
        student_sub=student_sub,
        submission_id=submission_id,
        author_id=_current_sub(user),
    )
    if transcript is None:
        return _private_error({"error": "not_found"}, status_code=404)
    return _json_private(_public_dialog_payload(transcript), status_code=200)


@teaching_unit_tasks_router.delete("/api/teaching/units/{unit_id}/sections/{section_id}/tasks/{task_id}")
async def delete_section_task(request: Request, unit_id: str, section_id: str, task_id: str):
    """Delete a task in a section and resequence positions."""

    user, error = _require_teacher(request)
    if error:
        return error
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    if not _is_uuid_like(unit_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    if not _is_uuid_like(section_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_section_id"}, status_code=400)
    if not _is_uuid_like(task_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_task_id"}, status_code=400)
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    try:
        _get_tasks_service().delete_task(unit_id, section_id, task_id, sub)
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404)
    except PermissionError:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    return Response(status_code=204, headers={"Cache-Control": "private, no-store"})


@teaching_unit_tasks_router.post("/api/teaching/units/{unit_id}/sections/{section_id}/tasks/reorder")
async def reorder_section_tasks(
    request: Request,
    unit_id: str,
    section_id: str,
    payload: TaskReorderPayload,
):
    """Reorder tasks in a section owned by the authoring teacher."""

    user, error = _require_teacher(request)
    if error:
        return error
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    if not _is_uuid_like(unit_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    if not _is_uuid_like(section_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_section_id"}, status_code=400)
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    ids = payload.task_ids
    if not isinstance(ids, list):
        return JSONResponse({"error": "bad_request", "detail": "task_ids_must_be_array"}, status_code=400)
    if len(ids) == 0:
        return JSONResponse({"error": "bad_request", "detail": "empty_task_ids"}, status_code=400)
    if len(ids) != len(set(ids)):
        return JSONResponse({"error": "bad_request", "detail": "duplicate_task_ids"}, status_code=400)
    if any(not _is_uuid_like(task_id) for task_id in ids):
        return JSONResponse({"error": "bad_request", "detail": "invalid_task_ids"}, status_code=400)
    try:
        _get_tasks_service().list_tasks(unit_id, section_id, sub)
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404)
    try:
        ordered = _get_tasks_service().reorder_tasks(unit_id, section_id, sub, ids)
    except ValueError as exc:
        detail = str(exc) or "task_mismatch"
        return JSONResponse({"error": "bad_request", "detail": detail}, status_code=400)
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404)
    except PermissionError:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    return JSONResponse(content=[_serialize_task(task) for task in ordered], status_code=200)


@teaching_unit_tasks_router.get("/api/teaching/units/{unit_id}/modules/{module_id}/tasks")
async def list_module_tasks(request: Request, unit_id: str, module_id: str):
    """List teacher-visible tasks through the public module abstraction."""

    section_id, error = teaching_authoring._resolve_module_section_for_authoring_read(
        request,
        unit_id=unit_id,
        module_id=module_id,
        repo_provider=_get_repo,
    )
    if error:
        return error
    return await list_section_tasks(request, unit_id, str(section_id))


@teaching_unit_tasks_router.post("/api/teaching/units/{unit_id}/modules/{module_id}/tasks")
async def create_module_task(
    request: Request,
    unit_id: str,
    module_id: str,
    payload: TaskCreatePayload,
):
    """Create a task in a module-backed section with write scope only."""

    section_id, error = teaching_authoring._resolve_module_section_for_authoring_mutation(
        request,
        unit_id=unit_id,
        module_id=module_id,
        repo_provider=_get_repo,
    )
    if error:
        return error
    return await create_section_task(request, unit_id, str(section_id), payload)


@teaching_unit_tasks_router.patch("/api/teaching/units/{unit_id}/modules/{module_id}/tasks/{task_id}")
async def update_module_task(
    request: Request,
    unit_id: str,
    module_id: str,
    task_id: str,
    payload: TaskUpdatePayload,
):
    """Update a task in a module-backed section with write scope only."""

    section_id, error = teaching_authoring._resolve_module_section_for_authoring_mutation(
        request,
        unit_id=unit_id,
        module_id=module_id,
        repo_provider=_get_repo,
    )
    if error:
        return error
    return await update_section_task(request, unit_id, str(section_id), task_id, payload)


@teaching_unit_tasks_router.delete("/api/teaching/units/{unit_id}/modules/{module_id}/tasks/{task_id}")
async def delete_module_task(request: Request, unit_id: str, module_id: str, task_id: str):
    """Delete a task in a module-backed section with delete scope only."""

    section_id, error = teaching_authoring._resolve_module_section_for_authoring_mutation(
        request,
        unit_id=unit_id,
        module_id=module_id,
        repo_provider=_get_repo,
    )
    if error:
        return error
    return await delete_section_task(request, unit_id, str(section_id), task_id)


@teaching_unit_tasks_router.post("/api/teaching/units/{unit_id}/modules/{module_id}/tasks/reorder")
async def reorder_module_tasks(
    request: Request,
    unit_id: str,
    module_id: str,
    payload: TaskReorderPayload,
):
    """Reorder tasks in a module-backed section with write scope only."""

    section_id, error = teaching_authoring._resolve_module_section_for_authoring_mutation(
        request,
        unit_id=unit_id,
        module_id=module_id,
        repo_provider=_get_repo,
    )
    if error:
        return error
    return await reorder_section_tasks(request, unit_id, str(section_id), payload)
