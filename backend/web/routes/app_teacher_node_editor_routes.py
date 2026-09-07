"""HTTP adapter for the teacher's content editor, with explicit dependencies."""

from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.teaching.services.node_editor import (
    NodeEditorAccessDenied,
    NodeEditorNotFound,
    NodeEditorRepositoryIncomplete,
    NodeEditorService,
)
from backend.web.routes.app_session_helpers import current_user, private_headers, user_payload
from backend.web.security.guards import has_any_role
from backend.web.teacher_editor_providers import teacher_editor_providers

app_teacher_node_editor_router = APIRouter(tags=["App"])


@app_teacher_node_editor_router.get("/api/teaching/views/units/{unit_id}/nodes/{node_id}/editor")
def get_teacher_unit_node_editor(request: Request, unit_id: str, node_id: str):
    """Allow teachers/admins to read only their own content; run DB work in the threadpool."""
    user = current_user(request)
    if user is None:
        return JSONResponse(
            {"error": "unauthenticated"}, status_code=401, headers=private_headers()
        )
    if not has_any_role(user, {"teacher", "admin"}):
        return JSONResponse({"error": "forbidden"}, status_code=403, headers=private_headers())
    for value, detail in ((unit_id, "invalid_unit_id"), (node_id, "invalid_node_id")):
        try:
            UUID(value)
        except (ValueError, TypeError):
            return JSONResponse(
                {"error": "bad_request", "detail": detail},
                status_code=400,
                headers=private_headers(),
            )

    service = NodeEditorService(teacher_editor_providers(request).repository())
    try:
        body = service.read(str(user.get("sub") or ""), unit_id, node_id)
    except NodeEditorAccessDenied:
        return JSONResponse({"error": "forbidden"}, status_code=403, headers=private_headers())
    except NodeEditorNotFound:
        return JSONResponse({"error": "not_found"}, status_code=404, headers=private_headers())
    except NodeEditorRepositoryIncomplete:
        return JSONResponse(
            {"error": "service_unavailable"}, status_code=503, headers=private_headers()
        )
    return JSONResponse({"user": user_payload(user), **body}, headers=private_headers())
