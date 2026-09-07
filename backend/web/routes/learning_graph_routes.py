"""HTTP adapter for the student graph, with explicit database dependencies."""

from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.learning.usecases.unit_graph import (
    GraphInvalidUnitType,
    GraphRepositoryIncomplete,
    LearningGraphUseCase,
)
from backend.web.learning_graph_providers import learning_graph_providers
from backend.web.routes.app_session_helpers import current_user, private_headers
from backend.web.security.guards import has_role

learning_graph_router = APIRouter(tags=["Learning"])


@learning_graph_router.get("/api/learning/courses/{course_id}/units/{unit_id}/modules/graph")
def get_modular_unit_graph(request: Request, course_id: str, unit_id: str):
    """Read a student's graph in the threadpool, preserving private 400/403/404/503 errors.

    Authentication and the student role are required before resolving a database
    dependency. The use case and repository enforce course membership and unit
    assignment; graph metadata does not grant access to locked module contents.
    """
    headers = {**private_headers(), "Vary": "Origin"}
    user = current_user(request)
    if not user:
        return JSONResponse({"error": "unauthenticated"}, status_code=401, headers=headers)
    if not has_role(user, "student"):
        return JSONResponse({"error": "forbidden"}, status_code=403, headers=headers)
    try:
        course_id_norm = str(UUID(course_id))
        unit_id_norm = str(UUID(unit_id))
    except ValueError:
        return JSONResponse(
            {"error": "bad_request", "detail": "invalid_uuid"}, status_code=400, headers=headers
        )

    use_case = LearningGraphUseCase(learning_graph_providers(request).repository())
    try:
        payload = use_case.read(str(user.get("sub", "")), course_id_norm, unit_id_norm)
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404, headers=headers)
    except GraphInvalidUnitType:
        return JSONResponse(
            {"error": "bad_request", "detail": "invalid_unit_type"},
            status_code=400,
            headers=headers,
        )
    except GraphRepositoryIncomplete:
        return JSONResponse({"error": "service_unavailable"}, status_code=503, headers=headers)
    return JSONResponse(payload, headers=headers)
