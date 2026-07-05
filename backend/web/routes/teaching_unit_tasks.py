"""Teaching unit task routes split out of the larger teaching adapter."""

from __future__ import annotations

from fastapi import APIRouter, Request

from backend.web.routes import teaching as teaching_routes


teaching_unit_tasks_router = APIRouter(tags=["Teaching"])

_get_repo = teaching_routes._get_repo
_REPO = teaching_routes._REPO
REPO = teaching_routes.REPO
STORAGE_ADAPTER = teaching_routes.STORAGE_ADAPTER
_STORAGE_ADAPTER_OVERRIDE_ACTIVE = teaching_routes._STORAGE_ADAPTER_OVERRIDE_ACTIVE


@teaching_unit_tasks_router.get("/api/teaching/units/{unit_id}/sections/{section_id}/tasks")
async def list_section_tasks(request: Request, unit_id: str, section_id: str):
    """List tasks for a section."""

    return await teaching_routes.list_section_tasks(request=request, unit_id=unit_id, section_id=section_id)


@teaching_unit_tasks_router.post("/api/teaching/units/{unit_id}/sections/{section_id}/tasks")
async def create_section_task(
    request: Request,
    unit_id: str,
    section_id: str,
    payload: teaching_routes.TaskCreatePayload,
):
    """Create a task in a section."""

    return await teaching_routes.create_section_task(
        request=request,
        unit_id=unit_id,
        section_id=section_id,
        payload=payload,
    )


@teaching_unit_tasks_router.patch("/api/teaching/units/{unit_id}/sections/{section_id}/tasks/{task_id}")
async def update_section_task(
    request: Request,
    unit_id: str,
    section_id: str,
    task_id: str,
    payload: teaching_routes.TaskUpdatePayload,
):
    """Update a task in a section."""

    return await teaching_routes.update_section_task(
        request=request,
        unit_id=unit_id,
        section_id=section_id,
        task_id=task_id,
        payload=payload,
    )


@teaching_unit_tasks_router.delete("/api/teaching/units/{unit_id}/sections/{section_id}/tasks/{task_id}")
async def delete_section_task(
    request: Request,
    unit_id: str,
    section_id: str,
    task_id: str,
):
    """Delete a task in a section."""

    return await teaching_routes.delete_section_task(
        request=request,
        unit_id=unit_id,
        section_id=section_id,
        task_id=task_id,
    )


@teaching_unit_tasks_router.post("/api/teaching/units/{unit_id}/sections/{section_id}/tasks/reorder")
async def reorder_section_tasks(
    request: Request,
    unit_id: str,
    section_id: str,
    payload: teaching_routes.TaskReorderPayload,
):
    """Reorder tasks in a section."""

    return await teaching_routes.reorder_section_tasks(
        request=request,
        unit_id=unit_id,
        section_id=section_id,
        payload=payload,
    )


@teaching_unit_tasks_router.post("/api/teaching/units/{unit_id}/modules/{module_id}/tasks")
async def create_module_task(
    request: Request,
    unit_id: str,
    module_id: str,
    payload: teaching_routes.TaskCreatePayload,
):
    """Create a task in a module via section indirection."""

    return await teaching_routes.create_module_task(request=request, unit_id=unit_id, module_id=module_id, payload=payload)


@teaching_unit_tasks_router.patch("/api/teaching/units/{unit_id}/modules/{module_id}/tasks/{task_id}")
async def update_module_task(
    request: Request,
    unit_id: str,
    module_id: str,
    task_id: str,
    payload: teaching_routes.TaskUpdatePayload,
):
    """Update a task in a module via section indirection."""

    return await teaching_routes.update_module_task(
        request=request,
        unit_id=unit_id,
        module_id=module_id,
        task_id=task_id,
        payload=payload,
    )


@teaching_unit_tasks_router.delete("/api/teaching/units/{unit_id}/modules/{module_id}/tasks/{task_id}")
async def delete_module_task(request: Request, unit_id: str, module_id: str, task_id: str):
    """Delete a task in a module via section indirection."""

    return await teaching_routes.delete_module_task(request=request, unit_id=unit_id, module_id=module_id, task_id=task_id)


@teaching_unit_tasks_router.post("/api/teaching/units/{unit_id}/modules/{module_id}/tasks/reorder")
async def reorder_module_tasks(
    request: Request,
    unit_id: str,
    module_id: str,
    payload: teaching_routes.TaskReorderPayload,
):
    """Reorder tasks in a module-backed section with write scope only."""

    return await teaching_routes.reorder_module_tasks(request=request, unit_id=unit_id, module_id=module_id, payload=payload)

