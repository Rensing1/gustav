"""Teaching unit routes split out of the larger teaching adapter."""

from __future__ import annotations

from fastapi import APIRouter, Request

from backend.web.routes import teaching as teaching_routes


teaching_units_router = APIRouter(tags=["Teaching"])

_get_repo = teaching_routes._get_repo
_REPO = teaching_routes._REPO
REPO = teaching_routes.REPO
STORAGE_ADAPTER = teaching_routes.STORAGE_ADAPTER
_STORAGE_ADAPTER_OVERRIDE_ACTIVE = teaching_routes._STORAGE_ADAPTER_OVERRIDE_ACTIVE


@teaching_units_router.get("/api/teaching/units")
async def list_units(request: Request, limit: int = 20, offset: int = 0):
    """List units owned by the calling teacher."""

    return await teaching_routes.list_units(request=request, limit=limit, offset=offset)


@teaching_units_router.post("/api/teaching/units")
async def create_unit(request: Request, payload: teaching_routes.UnitCreatePayload):
    """Create a reusable unit owned by the calling teacher."""

    return await teaching_routes.create_unit(request=request, payload=payload)


@teaching_units_router.get("/api/teaching/units/{unit_id}")
async def get_unit(request: Request, unit_id: str):
    """Get one unit by id."""

    return await teaching_routes.get_unit(request=request, unit_id=unit_id)


@teaching_units_router.patch("/api/teaching/units/{unit_id}")
async def update_unit(request: Request, unit_id: str, payload: teaching_routes.UnitUpdatePayload):
    """Update unit metadata of an owned unit."""

    return await teaching_routes.update_unit(request=request, unit_id=unit_id, payload=payload)


@teaching_units_router.delete("/api/teaching/units/{unit_id}")
async def delete_unit(request: Request, unit_id: str):
    """Delete a unit and related content."""

    return await teaching_routes.delete_unit(request=request, unit_id=unit_id)
