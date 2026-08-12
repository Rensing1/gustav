"""HTTP adapter for learner practice stacks and sessions."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from backend.learning.practice.repo_db import DBPracticeRepo
from backend.learning.practice.service import ActivePracticeSessionError, PracticeService
from backend.web.routes.security import _is_same_origin


practice_router = APIRouter(tags=["Learning"])
_SERVICE: PracticeService | None = None
_NO_STORE = {"Cache-Control": "private, no-store", "Vary": "Origin"}


def _service() -> PracticeService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = PracticeService(DBPracticeRepo())
    return _SERVICE


def set_practice_service(service: PracticeService | None) -> None:
    """Inject a deterministic service in route tests."""

    global _SERVICE
    _SERVICE = service


def _error(status: int, detail: str, **extra: Any) -> JSONResponse:
    body: dict[str, Any] = {
        "error": "not_found" if status == 404 else "conflict" if status == 409 else "bad_request",
        "detail": detail,
        **extra,
    }
    return JSONResponse(body, status_code=status, headers=_NO_STORE)


def _student(request: Request) -> tuple[str | None, Response | None]:
    user = getattr(request.state, "user", None)
    if not isinstance(user, dict):
        return None, JSONResponse({"error": "unauthenticated"}, status_code=401, headers=_NO_STORE)
    roles = {str(role).lower() for role in user.get("roles", []) if role}
    if str(user.get("role") or "").lower() == "student":
        roles.add("student")
    if "student" not in roles:
        return None, JSONResponse({"error": "forbidden"}, status_code=403, headers=_NO_STORE)
    return str(user.get("sub") or ""), None


def _csrf(request: Request) -> Response | None:
    if getattr(request.state, "cli_token_id", None):
        return None
    if not (request.headers.get("origin") or request.headers.get("referer")) or not _is_same_origin(request):
        return _error(403, "csrf_violation")
    return None


def _valid_uuid(value: str) -> bool:
    try:
        UUID(value)
        return True
    except ValueError:
        return False


@practice_router.get("/api/learning/practice/stacks")
async def list_practice_stacks(request: Request):
    student_sub, error = _student(request)
    if error:
        return error
    return JSONResponse({"stacks": _service().list_stacks(student_sub or "")}, headers=_NO_STORE)


@practice_router.get("/api/learning/practice/sessions/active")
async def get_active_practice_session(request: Request):
    student_sub, error = _student(request)
    if error:
        return error
    session = _service().get_active_session(student_sub or "")
    if session is None:
        return Response(status_code=204, headers=_NO_STORE)
    return JSONResponse(session, headers=_NO_STORE)


@practice_router.post("/api/learning/practice/sessions")
async def create_practice_session(request: Request):
    student_sub, error = _student(request)
    if error:
        return error
    csrf_error = _csrf(request)
    if csrf_error:
        return csrf_error
    try:
        payload = await request.json()
        if not isinstance(payload, dict):
            raise ValueError("invalid_practice_payload")
        session = _service().create_session(
            student_sub or "", mode=payload.get("mode"), stacks=payload.get("stacks")
        )
    except ActivePracticeSessionError as exc:
        return _error(409, "practice_session_active", active_session_id=exc.session_id)
    except LookupError:
        return _error(404, "practice_stack_not_found")
    except ValueError as exc:
        detail = str(exc)
        status = 400
        if detail == "session_item_limit_exceeded":
            status = 400
        return _error(status, detail)
    return JSONResponse(session, status_code=201, headers=_NO_STORE)


@practice_router.get("/api/learning/practice/sessions/{session_id}")
async def get_practice_session(request: Request, session_id: str):
    student_sub, error = _student(request)
    if error:
        return error
    if not _valid_uuid(session_id):
        return _error(400, "invalid_uuid")
    try:
        session = _service().get_session(student_sub or "", session_id)
    except LookupError:
        return _error(404, "practice_session_not_found")
    return JSONResponse(session, headers=_NO_STORE)


async def _session_mutation(
    request: Request,
    session_id: str,
    action,
    *args: str,
):
    student_sub, error = _student(request)
    if error:
        return error
    csrf_error = _csrf(request)
    if csrf_error:
        return csrf_error
    if not _valid_uuid(session_id) or any(not _valid_uuid(value) for value in args):
        return _error(400, "invalid_uuid")
    try:
        session = action(student_sub or "", session_id, *args)
    except LookupError:
        return _error(404, "practice_session_not_found")
    except ValueError as exc:
        return _error(409, str(exc))
    return JSONResponse(session, headers=_NO_STORE)


@practice_router.post("/api/learning/practice/sessions/{session_id}/continue")
async def continue_practice_session(request: Request, session_id: str):
    return await _session_mutation(request, session_id, _service().continue_session)


@practice_router.post("/api/learning/practice/sessions/{session_id}/items/{item_id}/skip")
async def skip_practice_item(request: Request, session_id: str, item_id: str):
    return await _session_mutation(request, session_id, _service().skip_item, item_id)


@practice_router.post("/api/learning/practice/sessions/{session_id}/end")
async def end_practice_session(request: Request, session_id: str):
    return await _session_mutation(request, session_id, _service().end_session)


@practice_router.post("/api/learning/practice/sessions/{session_id}/items/{item_id}/attempts")
async def create_practice_attempt(request: Request, session_id: str, item_id: str):
    student_sub, error = _student(request)
    if error:
        return error
    csrf_error = _csrf(request)
    if csrf_error:
        return csrf_error
    if not _valid_uuid(session_id) or not _valid_uuid(item_id):
        return _error(400, "invalid_uuid")
    try:
        payload = await request.json()
        if not isinstance(payload, dict):
            raise ValueError("invalid_practice_payload")
        if "practice_completion_token" in payload:
            attempt = _service().complete_h5p_attempt(
                student_sub or "",
                session_id,
                item_id,
                score_raw=payload.get("score_raw"),
                score_max=payload.get("score_max"),
                completion_token=payload.get("practice_completion_token"),
            )
        else:
            idempotency_key = request.headers.get("Idempotency-Key")
            if not str(idempotency_key or "").strip():
                raise ValueError("missing_idempotency_key")
            attempt = _service().create_native_attempt(
                student_sub or "",
                session_id,
                item_id,
                answer_text=payload.get("answer_text"),
                idempotency_key=idempotency_key,
            )
    except LookupError:
        return _error(404, "practice_session_not_found")
    except ValueError as exc:
        detail = str(exc)
        status = 409 if detail.startswith("practice_item_") else 400
        return _error(status, detail)
    return JSONResponse(attempt, status_code=202, headers=_NO_STORE)


@practice_router.post("/api/learning/practice/sessions/{session_id}/items/{item_id}/h5p-context")
async def issue_practice_h5p_context(request: Request, session_id: str, item_id: str):
    student_sub, error = _student(request)
    if error:
        return error
    csrf_error = _csrf(request)
    if csrf_error:
        return csrf_error
    if not _valid_uuid(session_id) or not _valid_uuid(item_id):
        return _error(400, "invalid_uuid")
    try:
        context = _service().issue_h5p_context(student_sub or "", session_id, item_id)
    except LookupError:
        return _error(404, "practice_session_not_found")
    except ValueError as exc:
        return _error(409, str(exc))
    return JSONResponse(context, status_code=201, headers=_NO_STORE)


@practice_router.get("/api/learning/practice/attempts/{attempt_id}")
async def get_practice_attempt(request: Request, attempt_id: str):
    student_sub, error = _student(request)
    if error:
        return error
    if not _valid_uuid(attempt_id):
        return _error(400, "invalid_uuid")
    try:
        attempt = _service().get_attempt(student_sub or "", attempt_id)
    except LookupError:
        return _error(404, "practice_attempt_not_found")
    return JSONResponse(attempt, headers=_NO_STORE)


@practice_router.post("/api/learning/practice/sessions/{session_id}/items/{item_id}/solution")
async def reveal_practice_solution(request: Request, session_id: str, item_id: str):
    student_sub, error = _student(request)
    if error:
        return error
    csrf_error = _csrf(request)
    if csrf_error:
        return csrf_error
    if not _valid_uuid(session_id) or not _valid_uuid(item_id):
        return _error(400, "invalid_uuid")
    try:
        solution = _service().reveal_solution(student_sub or "", session_id, item_id)
    except LookupError:
        return _error(404, "practice_session_not_found")
    except PermissionError:
        return _error(403, "practice_solution_forbidden")
    except ValueError as exc:
        return _error(409, str(exc))
    return JSONResponse(solution, headers=_NO_STORE)
