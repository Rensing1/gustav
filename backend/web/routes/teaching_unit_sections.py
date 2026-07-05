"""Teaching unit section routes split out of the larger teaching adapter."""

from __future__ import annotations

from fastapi import APIRouter, Request

from backend.web.routes import teaching as teaching_routes


teaching_unit_sections_router = APIRouter(tags=["Teaching"])

_get_repo = teaching_routes._get_repo
_REPO = teaching_routes._REPO
REPO = teaching_routes.REPO
STORAGE_ADAPTER = teaching_routes.STORAGE_ADAPTER
_STORAGE_ADAPTER_OVERRIDE_ACTIVE = teaching_routes._STORAGE_ADAPTER_OVERRIDE_ACTIVE


@teaching_unit_sections_router.get("/api/teaching/units/{unit_id}/sections")
async def list_sections(request: Request, unit_id: str):
    """List sections of a learning unit (author only)."""

    return await teaching_routes.list_sections(request=request, unit_id=unit_id)


@teaching_unit_sections_router.post("/api/teaching/units/{unit_id}/sections")
async def create_section(request: Request, unit_id: str, payload: teaching_routes.SectionCreatePayload):
    """Create a section in a unit."""

    return await teaching_routes.create_section(request=request, unit_id=unit_id, payload=payload)


@teaching_unit_sections_router.patch("/api/teaching/units/{unit_id}/sections/{section_id}")
async def update_section(
    request: Request,
    unit_id: str,
    section_id: str,
    payload: teaching_routes.SectionUpdatePayload,
):
    """Update section title."""

    return await teaching_routes.update_section(
        request=request,
        unit_id=unit_id,
        section_id=section_id,
        payload=payload,
    )


@teaching_unit_sections_router.delete("/api/teaching/units/{unit_id}/sections/{section_id}")
async def delete_section(request: Request, unit_id: str, section_id: str):
    """Delete a section."""

    return await teaching_routes.delete_section(request=request, unit_id=unit_id, section_id=section_id)


@teaching_unit_sections_router.post("/api/teaching/units/{unit_id}/sections/reorder")
async def reorder_sections(request: Request, unit_id: str, payload: teaching_routes.SectionReorderPayload):
    """Reorder sections."""

    return await teaching_routes.reorder_sections(request=request, unit_id=unit_id, payload=payload)

