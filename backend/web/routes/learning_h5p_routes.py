"""HTTP adapter for H5P access checks with explicit database dependencies."""

import re
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from backend.learning.usecases.h5p_access import (
    CheckH5PContentAccessInput,
    CheckH5PContentAccessUseCase,
)
from backend.web.learning_h5p_providers import learning_h5p_providers
from backend.web.routes.app_session_helpers import current_user, private_headers
from backend.web.security.guards import has_role

learning_h5p_router = APIRouter(tags=["Learning"])


@learning_h5p_router.get("/api/learning/courses/{course_id}/h5p/contents/{content_id}/access")
def check_h5p_content_access(request: Request, course_id: str, content_id: str):
    """Authorize a student's H5P content without disclosing inaccessible content.

    Parameters:
        course_id: Course UUID, validated before database access.
        content_id: Numeric H5P identifier, kept as an ASCII digit string.
        request: Authenticated context and explicitly installed dependencies.
    Permissions:
        Requires the student role. The existing use case and DB adapter enforce
        membership and at least one released linear or open/done modular task.
    Behavior:
        Return private 204 with no body when allowed, otherwise private 404.
        Reject missing identity, wrong role or invalid IDs before DB construction.
        Synchronous DB work runs in FastAPI's bounded threadpool.
    """
    headers = {**private_headers(), "Vary": "Origin"}
    user = current_user(request)
    if not user:
        return JSONResponse({"error": "unauthenticated"}, status_code=401, headers=headers)
    if not has_role(user, "student"):
        return JSONResponse({"error": "forbidden"}, status_code=403, headers=headers)
    try:
        UUID(course_id)
    except ValueError:
        return JSONResponse(
            {"error": "bad_request", "detail": "invalid_uuid"}, status_code=400, headers=headers
        )
    # Do not use \d: the public contract accepts ASCII digits only.
    if not re.fullmatch(r"[0-9]+", content_id):
        return JSONResponse(
            {"error": "bad_request", "detail": "invalid_content_id"},
            status_code=400,
            headers=headers,
        )
    repo = learning_h5p_providers(request).repository()
    allowed = CheckH5PContentAccessUseCase(repo).execute(
        CheckH5PContentAccessInput(
            student_sub=str(user.get("sub", "")), course_id=course_id, content_id=content_id
        )
    )
    if allowed:
        return Response(status_code=204, headers=headers)
    return JSONResponse({"error": "not_found"}, status_code=404, headers=headers)
