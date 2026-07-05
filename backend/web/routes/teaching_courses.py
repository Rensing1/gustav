"""Teaching course routes split out of the larger teaching adapter."""

from __future__ import annotations

from fastapi import APIRouter, Request

from backend.web.routes import teaching as teaching_routes


teaching_courses_router = APIRouter(tags=["Teaching"])

_get_repo = teaching_routes._get_repo
_REPO = teaching_routes._REPO
REPO = teaching_routes.REPO
STORAGE_ADAPTER = teaching_routes.STORAGE_ADAPTER
_STORAGE_ADAPTER_OVERRIDE_ACTIVE = teaching_routes._STORAGE_ADAPTER_OVERRIDE_ACTIVE


@teaching_courses_router.get("/api/teaching/courses")
async def list_courses(request: Request, limit: int = 10, offset: int = 0):
    """List all courses owned by teachers or joined by students."""

    return await teaching_routes.list_courses(request=request, limit=limit, offset=offset)


@teaching_courses_router.post("/api/teaching/courses")
async def create_course(request: Request, payload: teaching_routes.CourseCreate):
    """Create a new course owned by the calling teacher."""

    return await teaching_routes.create_course(request=request, payload=payload)


@teaching_courses_router.get("/api/teaching/courses/{course_id}")
async def get_course(request: Request, course_id: str):
    """Get one course by id."""

    return await teaching_routes.get_course(request=request, course_id=course_id)


@teaching_courses_router.patch("/api/teaching/courses/{course_id}")
async def update_course(request: Request, course_id: str, payload: teaching_routes.CourseUpdate):
    """Update course metadata of an owned course."""

    return await teaching_routes.update_course(request=request, course_id=course_id, payload=payload)


@teaching_courses_router.delete("/api/teaching/courses/{course_id}")
async def delete_course(request: Request, course_id: str):
    """Delete a course and its memberships."""

    return await teaching_routes.delete_course(request=request, course_id=course_id)
