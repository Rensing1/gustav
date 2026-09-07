"""HTTP adapters for released course/unit sections with explicit dependencies."""

from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.learning.usecases.sections import (
    ListSectionsInput,
    ListSectionsUseCase,
    ListUnitSectionsInput,
    ListUnitSectionsUseCase,
)
from backend.web.learning_content_query import parse_include
from backend.web.learning_section_providers import learning_section_providers
from backend.web.routes.app_session_helpers import current_user, private_headers
from backend.web.routes.learning_material_files import attach_section_material_files
from backend.web.security.guards import has_role

learning_section_router = APIRouter(tags=["Learning"])


def _private_headers() -> dict[str, str]:
    return {**private_headers(), "Vary": "Origin"}


def _require_student(request: Request):
    """Reject unauthorized callers before constructing the DB adapter."""
    user = current_user(request)
    if not user:
        return None, JSONResponse(
            {"error": "unauthenticated"}, status_code=401, headers=_private_headers()
        )
    if not has_role(user, "student"):
        return None, JSONResponse(
            {"error": "forbidden"}, status_code=403, headers=_private_headers()
        )
    return user, None


@learning_section_router.get("/api/learning/courses/{course_id}/sections")
def list_sections(
    request: Request,
    course_id: str,
    include: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    """List released sections for a course (student-only).

    Intent:
        Return only sections released to the authenticated student.

    Permissions:
        Caller must have the `student` role and be enrolled in the course.
    """
    user, error = _require_student(request)
    if error:
        return error

    try:
        UUID(course_id)
    except ValueError:
        return JSONResponse(
            {"error": "bad_request", "detail": "invalid_uuid"},
            status_code=400,
            headers=_private_headers(),
        )

    try:
        include_materials, include_tasks = parse_include(include)
    except ValueError:
        return JSONResponse(
            {"error": "bad_request", "detail": "invalid_include"},
            status_code=400,
            headers=_private_headers(),
        )

    input_data = ListSectionsInput(
        student_sub=str(user.get("sub", "")),
        course_id=course_id,
        include_materials=include_materials,
        include_tasks=include_tasks,
        # Clamp happens in the use case to keep adapter thin
        limit=limit,
        offset=offset,
    )

    try:
        repo = learning_section_providers(request).repository()
        sections = ListSectionsUseCase(repo).execute(input_data)
    except PermissionError:
        return JSONResponse({"error": "forbidden"}, status_code=403, headers=_private_headers())
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_private_headers())

    sections = attach_section_material_files(
        repo=repo,
        student_sub=str(user.get("sub", "")),
        course_id=course_id,
        sections=sections,
    )
    return JSONResponse(sections, headers=_private_headers())


@learning_section_router.get("/api/learning/courses/{course_id}/units/{unit_id}/sections")
def list_unit_sections(
    request: Request,
    course_id: str,
    unit_id: str,
    include: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    """List released sections for a specific unit (student-only).

    Why:
        Unit-scoped endpoint aligns with the SSR unit page and avoids
        client-side filtering. Returns 200 with an array that may be empty.

    Permissions:
        Caller must have the `student` role and be enrolled in the course.
        The unit must belong to the course; otherwise respond with 404 to avoid
        leaking existence details.
    """
    user, error = _require_student(request)
    if error:
        return error

    # Validate path params eagerly to align with contract detail=invalid_uuid
    try:
        UUID(course_id)
        UUID(unit_id)
    except ValueError:
        return JSONResponse(
            {"error": "bad_request", "detail": "invalid_uuid"},
            status_code=400,
            headers=_private_headers(),
        )

    try:
        include_materials, include_tasks = parse_include(include)
    except ValueError:
        return JSONResponse(
            {"error": "bad_request", "detail": "invalid_include"},
            status_code=400,
            headers=_private_headers(),
        )

    input_data = ListUnitSectionsInput(
        student_sub=str(user.get("sub", "")),
        course_id=course_id,
        unit_id=unit_id,
        include_materials=include_materials,
        include_tasks=include_tasks,
        limit=limit,
        offset=offset,
    )
    try:
        repo = learning_section_providers(request).repository()
        sections = ListUnitSectionsUseCase(repo).execute(input_data)
    except PermissionError:
        return JSONResponse({"error": "forbidden"}, status_code=403, headers=_private_headers())
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_private_headers())

    # 200 with possibly empty list
    sections = attach_section_material_files(
        repo=repo,
        student_sub=str(user.get("sub", "")),
        course_id=course_id,
        sections=sections,
    )
    return JSONResponse(sections, headers=_private_headers())
