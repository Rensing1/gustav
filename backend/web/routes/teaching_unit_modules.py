"""Teaching unit phase and module routes split out of the larger teaching adapter."""

from __future__ import annotations

from fastapi import APIRouter, Request

from backend.web.routes import teaching as teaching_routes


teaching_unit_modules_router = APIRouter(tags=["Teaching"])

_get_repo = teaching_routes._get_repo
_REPO = teaching_routes._REPO
REPO = teaching_routes.REPO
STORAGE_ADAPTER = teaching_routes.STORAGE_ADAPTER
_STORAGE_ADAPTER_OVERRIDE_ACTIVE = teaching_routes._STORAGE_ADAPTER_OVERRIDE_ACTIVE


@teaching_unit_modules_router.get("/api/teaching/units/{unit_id}/phases")
async def list_unit_phases(request: Request, unit_id: str):
    """List phases of a modular unit (author only)."""

    return await teaching_routes.list_unit_phases(request=request, unit_id=unit_id)


@teaching_unit_modules_router.post("/api/teaching/units/{unit_id}/phases")
async def create_unit_phase(request: Request, unit_id: str, payload: teaching_routes.UnitPhaseCreatePayload):
    """Create a phase in a modular unit (author only); appends at the next position."""

    return await teaching_routes.create_unit_phase(request=request, unit_id=unit_id, payload=payload)


@teaching_unit_modules_router.patch("/api/teaching/units/{unit_id}/phases/{phase_id}")
async def update_unit_phase(
    request: Request,
    unit_id: str,
    phase_id: str,
    payload: teaching_routes.UnitPhaseUpdatePayload,
):
    """Rename a phase in a modular unit (author only)."""

    return await teaching_routes.update_unit_phase(
        request=request,
        unit_id=unit_id,
        phase_id=phase_id,
        payload=payload,
    )


@teaching_unit_modules_router.delete("/api/teaching/units/{unit_id}/phases/{phase_id}")
async def delete_unit_phase(request: Request, unit_id: str, phase_id: str):
    """Delete a phase (and all modules/edges/content inside it) (author only)."""

    return await teaching_routes.delete_unit_phase(request=request, unit_id=unit_id, phase_id=phase_id)


@teaching_unit_modules_router.post("/api/teaching/units/{unit_id}/phases/reorder")
async def reorder_unit_phases(request: Request, unit_id: str, payload: teaching_routes.UnitPhaseReorderPayload):
    """Reorder phases (author only) transactionally to positions 1..n as provided."""

    return await teaching_routes.reorder_unit_phases(request=request, unit_id=unit_id, payload=payload)


@teaching_unit_modules_router.get("/api/teaching/units/{unit_id}/modules/graph")
async def get_unit_modules_graph(request: Request, unit_id: str):
    """Return the authoring graph payload for a modular unit (author only)."""

    return await teaching_routes.get_unit_modules_graph(request=request, unit_id=unit_id)


@teaching_unit_modules_router.get("/api/teaching/units/{unit_id}/modules/{module_id}/content-target")
async def get_unit_module_content_target(request: Request, unit_id: str, module_id: str):
    """Return the backing section id for a modular unit module."""

    return await teaching_routes.get_unit_module_content_target(
        request=request,
        unit_id=unit_id,
        module_id=module_id,
    )


@teaching_unit_modules_router.post("/api/teaching/units/{unit_id}/modules")
async def create_unit_module(
    request: Request,
    unit_id: str,
    payload: teaching_routes.UnitModuleCreatePayload,
):
    """Create a module (graph node) inside a phase (author only)."""

    return await teaching_routes.create_unit_module(request=request, unit_id=unit_id, payload=payload)


@teaching_unit_modules_router.post("/api/teaching/units/{unit_id}/modules/edges")
async def create_unit_module_edge(
    request: Request,
    unit_id: str,
    payload: teaching_routes.UnitModuleEdgePayload,
):
    """Create a dependency edge within a modular unit (author only)."""

    return await teaching_routes.create_unit_module_edge(request=request, unit_id=unit_id, payload=payload)


@teaching_unit_modules_router.delete("/api/teaching/units/{unit_id}/modules/edges")
async def delete_unit_module_edge(
    request: Request,
    unit_id: str,
    payload: teaching_routes.UnitModuleEdgePayload,
):
    """Delete a dependency edge using request-body module ids (author only)."""

    return await teaching_routes.delete_unit_module_edge(request=request, unit_id=unit_id, payload=payload)


@teaching_unit_modules_router.delete("/api/teaching/units/{unit_id}/modules/{from_module_id}/edges/{to_module_id}")
async def delete_unit_module_edge_by_path(
    request: Request,
    unit_id: str,
    from_module_id: str,
    to_module_id: str,
):
    """Delete a dependency edge using path params (author only)."""

    return await teaching_routes.delete_unit_module_edge_by_path(
        request=request,
        unit_id=unit_id,
        from_module_id=from_module_id,
        to_module_id=to_module_id,
    )


@teaching_unit_modules_router.patch("/api/teaching/units/{unit_id}/modules/{module_id}")
async def update_unit_module(
    request: Request,
    unit_id: str,
    module_id: str,
    payload: teaching_routes.UnitModuleUpdatePayload,
):
    """Update module settings (author only)."""

    return await teaching_routes.update_unit_module(
        request=request,
        unit_id=unit_id,
        module_id=module_id,
        payload=payload,
    )


@teaching_unit_modules_router.delete("/api/teaching/units/{unit_id}/modules/{module_id}")
async def delete_unit_module(request: Request, unit_id: str, module_id: str):
    """Delete a module and its backing content (author only)."""

    return await teaching_routes.delete_unit_module(request=request, unit_id=unit_id, module_id=module_id)


@teaching_unit_modules_router.post("/api/teaching/units/{unit_id}/phases/{phase_id}/modules/reorder")
async def reorder_unit_phase_modules(
    request: Request,
    unit_id: str,
    phase_id: str,
    payload: teaching_routes.UnitModuleReorderPayload,
):
    """Reorder (and move) modules for a phase (author only)."""

    return await teaching_routes.reorder_unit_phase_modules(
        request=request,
        unit_id=unit_id,
        phase_id=phase_id,
        payload=payload,
    )

