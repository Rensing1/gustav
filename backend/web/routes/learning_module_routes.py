"""HTTP adapter for student module contents and authorized material links."""

from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.learning.usecases.modular_unit_access import InvalidModularUnitType
from backend.learning.usecases.module_content import (
    LearningModuleUseCase,
    ModuleRepositoryIncomplete,
)
from backend.web.learning_content_query import parse_include
from backend.web.learning_module_providers import learning_module_providers
from backend.web.routes.app_session_helpers import current_user, private_headers
from backend.web.routes.learning_material_files import attach_modular_material_files
from backend.web.security.guards import has_role

learning_module_router = APIRouter(tags=["Learning"])


@learning_module_router.get("/api/learning/courses/{course_id}/units/{unit_id}/modules/{module_id}")
def get_modular_unit_module_content(
    request: Request,
    course_id: str,
    unit_id: str,
    module_id: str,
    include: str | None = None,
):
    """Read a student's open/done module in the threadpool; private responses never leak denials.

    Validate identity, role, UUIDs and resource selection before building the
    repository. Only successful authorized content reads receive material links,
    using the same adapter for the additional visibility lookup.
    """
    headers = {**private_headers(), "Vary": "Origin"}
    user = current_user(request)
    if not user:
        return JSONResponse({"error": "unauthenticated"}, status_code=401, headers=headers)
    if not has_role(user, "student"):
        return JSONResponse({"error": "forbidden"}, status_code=403, headers=headers)
    try:
        course_id, unit_id, module_id = (
            str(UUID(course_id)),
            str(UUID(unit_id)),
            str(UUID(module_id)),
        )
    except ValueError:
        return JSONResponse(
            {"error": "bad_request", "detail": "invalid_uuid"}, status_code=400, headers=headers
        )
    try:
        materials, tasks = parse_include(include, default_materials=True, default_tasks=True)
    except ValueError:
        return JSONResponse(
            {"error": "bad_request", "detail": "invalid_include"}, status_code=400, headers=headers
        )
    student_sub = str(user.get("sub", ""))
    repo = learning_module_providers(request).repository()
    try:
        payload = LearningModuleUseCase(repo).read(
            student_sub,
            course_id,
            unit_id,
            module_id,
            include_materials=materials,
            include_tasks=tasks,
        )
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404, headers=headers)
    except InvalidModularUnitType:
        return JSONResponse(
            {"error": "bad_request", "detail": "invalid_unit_type"},
            status_code=400,
            headers=headers,
        )
    except ModuleRepositoryIncomplete:
        return JSONResponse({"error": "service_unavailable"}, status_code=503, headers=headers)
    payload = attach_modular_material_files(
        repo=repo,
        student_sub=student_sub,
        course_id=course_id,
        payload=payload,
    )
    return JSONResponse(payload, headers=headers)
