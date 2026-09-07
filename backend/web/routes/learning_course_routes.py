"""Course reads with explicit dependencies and synchronous database execution."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.learning.usecases.courses import (
    ListCoursesInput,
    ListCoursesUseCase,
    ListCourseUnitsInput,
    ListCourseUnitsUseCase,
)
from backend.web.learning_course_providers import learning_course_providers
from backend.web.routes.app_session_helpers import current_user, private_headers
from backend.web.security.guards import has_role

learning_course_router = APIRouter(tags=["Learning"])


def _require_student(request: Request):
    """Reject missing authentication or role before constructing dependencies."""
    user = current_user(request)
    if not user:
        return None, JSONResponse(
            {"error": "unauthenticated"}, status_code=401, headers=private_headers()
        )
    if not has_role(user, "student"):
        return None, JSONResponse(
            {"error": "forbidden"}, status_code=403, headers=private_headers()
        )
    return user, None


@learning_course_router.get("/api/learning/courses")
def list_my_courses(request: Request, scope: str = "current", limit: int = 50, offset: int = 0):
    """List courses for the current student (alphabetical, minimal fields).

    Why:
        Dedicated Learning endpoint that exposes only student-facing fields and
        separates responsibilities from Teaching. This reduces accidental data
        leakage (e.g., teacher_id) and keeps the contract stable for learners.

    Parameters:
        request: FastAPI request carrying the authenticated user context.
        limit: Page size clamp to 1..100 (default 50).
        offset: Zero-based starting index (default 0).

    Behavior:
        - Requires an authenticated session with role "student".
        - Returns courses where the caller is a member, sorted by
          title asc, id asc (stable secondary order).
        - Uses private, no-store Cache-Control headers.

    Permissions:
        Caller must have the `student` role; membership filtering is enforced in
        the repository via RLS and explicit joins. Responds 403 if caller lacks
        the student role.
    """
    user, error = _require_student(request)
    if error:
        return error
    items = ListCoursesUseCase(learning_course_providers(request).repository()).execute(
        ListCoursesInput(
            student_sub=str(user.get("sub", "")),
            limit=int(limit or 50),
            offset=int(offset or 0),
            scope="past" if scope == "past" else "current",
        )
    )
    return JSONResponse(items, headers=private_headers())


@learning_course_router.get("/api/learning/courses/{course_id}/units")
def list_course_units(request: Request, course_id: str):
    """List learning units of a course for the current student.

    Why:
        Students need a read-only listing of units within a course ordered by
        the teacher-defined module position, independent from section releases.

    Parameters:
        request: FastAPI request with authenticated user context.
        course_id: UUID of the course; 400 when not UUID-like.

    Behavior:
        - Requires an authenticated session with role "student".
        - Responds 200 with an array of objects { unit: UnitPublic, position }.
        - Responds 404 when the course does not exist or the caller is not a
          member (intentionally indistinguishable to avoid leaking existence).
        - Responses include private Cache-Control headers.

    Permissions:
        Caller must have the `student` role (403 otherwise) and be a member of
        the course. Membership and ordering are enforced at the DB boundary.
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
            headers=private_headers(),
        )
    try:
        rows = ListCourseUnitsUseCase(learning_course_providers(request).repository()).execute(
            ListCourseUnitsInput(student_sub=str(user.get("sub", "")), course_id=str(course_id))
        )
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404, headers=private_headers())
    return JSONResponse(rows, headers=private_headers())
