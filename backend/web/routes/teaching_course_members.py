"""Teaching course-member routes split out of the larger teaching adapter."""

from __future__ import annotations

from fastapi import APIRouter, Request

from backend.web.routes import teaching as teaching_routes


teaching_course_members_router = APIRouter(tags=["Teaching"])

_get_repo = teaching_routes._get_repo
_REPO = teaching_routes._REPO
REPO = teaching_routes.REPO
STORAGE_ADAPTER = teaching_routes.STORAGE_ADAPTER
_STORAGE_ADAPTER_OVERRIDE_ACTIVE = teaching_routes._STORAGE_ADAPTER_OVERRIDE_ACTIVE


@teaching_course_members_router.get("/api/teaching/courses/{course_id}/members")
async def list_members(request: Request, course_id: str, limit: int = 10, offset: int = 0):
    """List members for a course — owner-only."""

    return await teaching_routes.list_members(request=request, course_id=course_id, limit=limit, offset=offset)


@teaching_course_members_router.post("/api/teaching/courses/{course_id}/members")
async def add_member(
    request: Request,
    course_id: str,
    payload: teaching_routes.AddMember,
):
    """Add a student member to a course owned by the caller."""

    return await teaching_routes.add_member(request=request, course_id=course_id, payload=payload)


@teaching_course_members_router.delete("/api/teaching/courses/{course_id}/members/{student_sub}")
async def remove_member(request: Request, course_id: str, student_sub: str):
    """Remove a student member from a course owned by the caller."""

    return await teaching_routes.remove_member(request=request, course_id=course_id, student_sub=student_sub)

