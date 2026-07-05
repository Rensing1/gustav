"""Teaching live routes split out of the larger teaching router."""

from __future__ import annotations

from fastapi import APIRouter, Request

from backend.web.routes import teaching as teaching_routes


teaching_live_router = APIRouter(tags=["Teaching"])

_get_repo = teaching_routes._get_repo
_REPO = teaching_routes._REPO
REPO = teaching_routes.REPO
STORAGE_ADAPTER = teaching_routes.STORAGE_ADAPTER
_STORAGE_ADAPTER_OVERRIDE_ACTIVE = teaching_routes._STORAGE_ADAPTER_OVERRIDE_ACTIVE


@teaching_live_router.get("/api/teaching/courses/{course_id}/units/{unit_id}/submissions/summary")
async def get_unit_live_summary(
    request: Request,
    course_id: str,
    unit_id: str,
    updated_since: str | None = None,
    limit: int = 100,
    offset: int = 0,
    include_students: bool = True,
):
    """Live summary view for one course-unit matrix."""

    return await teaching_routes.get_unit_live_summary(
        request=request,
        course_id=course_id,
        unit_id=unit_id,
        updated_since=updated_since,
        limit=limit,
        offset=offset,
        include_students=include_students,
    )


@teaching_live_router.get("/api/teaching/courses/{course_id}/units/{unit_id}/submissions/delta")
async def get_unit_live_delta(
    request: Request,
    course_id: str,
    unit_id: str,
    updated_since: str,
    limit: int = 200,
    offset: int = 0,
):
    """Live delta polling changes for one course-unit matrix."""

    return await teaching_routes.get_unit_live_delta(
        request=request,
        course_id=course_id,
        unit_id=unit_id,
        updated_since=updated_since,
        limit=limit,
        offset=offset,
    )


@teaching_live_router.get("/api/teaching/courses/{course_id}/students/{student_sub:path}/submissions/overview")
async def get_student_live_overview(request: Request, course_id: str, student_sub: str):
    """Teacher-facing student overview across course units."""

    return await teaching_routes.get_student_live_overview(request=request, course_id=course_id, student_sub=student_sub)


@teaching_live_router.get(
    "/api/teaching/courses/{course_id}/units/{unit_id}/tasks/{task_id}/students/{student_sub:path}/submissions/latest"
)
async def get_latest_submission_detail(
    request: Request,
    course_id: str,
    unit_id: str,
    task_id: str,
    student_sub: str,
):
    """Latest submission detail helper for one student-task pair."""

    return await teaching_routes.get_latest_submission_detail(
        request=request,
        course_id=course_id,
        unit_id=unit_id,
        task_id=task_id,
        student_sub=student_sub,
    )


@teaching_live_router.get(
    "/api/teaching/courses/{course_id}/units/{unit_id}/tasks/{task_id}/students/{student_sub:path}/submissions/latest/file"
)
async def get_teaching_submission_file(
    request: Request,
    course_id: str,
    unit_id: str,
    task_id: str,
    student_sub: str,
    disposition: str | None = None,
):
    """Same-origin download helper for teacher-visible submission files."""

    return await teaching_routes.get_teaching_submission_file(
        request=request,
        course_id=course_id,
        unit_id=unit_id,
        task_id=task_id,
        student_sub=student_sub,
        disposition=disposition,
    )

