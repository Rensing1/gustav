"""Teaching course-module routes split out of the larger teaching adapter."""

from __future__ import annotations

from fastapi import APIRouter, Request

from backend.web.routes import teaching as teaching_routes


teaching_course_modules_router = APIRouter(tags=["Teaching"])

_get_repo = teaching_routes._get_repo
_REPO = teaching_routes._REPO
REPO = teaching_routes.REPO
STORAGE_ADAPTER = teaching_routes.STORAGE_ADAPTER
_STORAGE_ADAPTER_OVERRIDE_ACTIVE = teaching_routes._STORAGE_ADAPTER_OVERRIDE_ACTIVE


@teaching_course_modules_router.get("/api/teaching/courses/{course_id}/modules")
async def list_course_modules(request: Request, course_id: str):
    """List modules for a course owned by the current teacher."""

    return await teaching_routes.list_course_modules(request=request, course_id=course_id)


@teaching_course_modules_router.post("/api/teaching/courses/{course_id}/modules")
async def create_course_module(
    request: Request,
    course_id: str,
    payload: teaching_routes.CourseModuleCreatePayload,
):
    """Attach a unit as a module within an owned course."""

    return await teaching_routes.create_course_module(request=request, course_id=course_id, payload=payload)


@teaching_course_modules_router.post("/api/teaching/courses/{course_id}/modules/reorder")
async def reorder_course_modules(
    request: Request,
    course_id: str,
    payload: teaching_routes.CourseModuleReorderPayload,
):
    """Reorder modules in an owned course atomically."""

    return await teaching_routes.reorder_course_modules(request=request, course_id=course_id, payload=payload)


@teaching_course_modules_router.delete("/api/teaching/courses/{course_id}/modules/{module_id}")
async def delete_course_module(request: Request, course_id: str, module_id: str):
    """Detach a unit module from an owned course."""

    return await teaching_routes.delete_course_module(request=request, course_id=course_id, module_id=module_id)


@teaching_course_modules_router.patch(
    "/api/teaching/courses/{course_id}/modules/{module_id}/sections/{section_id}/visibility"
)
async def update_module_section_visibility(
    request: Request,
    course_id: str,
    module_id: str,
    section_id: str,
    payload: teaching_routes.ModuleSectionVisibilityPayload,
):
    """Toggle section visibility in a course module."""

    return await teaching_routes.update_module_section_visibility(
        request=request,
        course_id=course_id,
        module_id=module_id,
        section_id=section_id,
        payload=payload,
    )


@teaching_course_modules_router.get("/api/teaching/courses/{course_id}/modules/{module_id}/sections/releases")
async def list_module_section_releases(request: Request, course_id: str, module_id: str):
    """List release rows for module sections (owner only)."""

    return await teaching_routes.list_module_section_releases(request=request, course_id=course_id, module_id=module_id)


@teaching_course_modules_router.get("/api/teaching/courses/{course_id}/modules/{module_id}/sections")
async def list_module_sections_with_visibility(request: Request, course_id: str, module_id: str):
    """List unit sections for module with section-level visibility state."""

    return await teaching_routes.list_module_sections_with_visibility(
        request=request,
        course_id=course_id,
        module_id=module_id,
    )

