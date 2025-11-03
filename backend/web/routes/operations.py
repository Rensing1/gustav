"""Operations endpoints (internal tooling for teachers/operators)."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.learning.workers import health as worker_health

operations_router = APIRouter(tags=["Operations"])


def _private_response(body: dict, *, status_code: int) -> JSONResponse:
    return JSONResponse(body, status_code=status_code, headers={"Cache-Control": "private, no-store"})


def _require_teacher_or_operator(request: Request):
    user = getattr(request.state, "user", None)
    if not user:
        return None, _private_response({"error": "unauthenticated"}, status_code=401)
    roles = user.get("roles")
    if not isinstance(roles, list) or not any(role in ("teacher", "operator") for role in roles):
        return None, _private_response({"error": "forbidden"}, status_code=403)
    return user, None


@operations_router.get("/internal/health/learning-worker")
async def learning_worker_health(request: Request):
    """
    Return diagnostics for the learning worker pipeline.

    Permissions:
        Caller must have `teacher` or `operator` role (auth via gustav_session).
    """
    _, error = _require_teacher_or_operator(request)
    if error:
        return error

    probe = await worker_health.LEARNING_WORKER_HEALTH_SERVICE.probe()
    body = {
        "status": probe.status,
        "currentRole": probe.current_role,
        "checks": [
            {"check": check.check, "status": check.status, "detail": check.detail}
            for check in probe.checks
        ],
    }
    status_code = 200 if probe.status == "healthy" else 503
    return _private_response(body, status_code=status_code)
