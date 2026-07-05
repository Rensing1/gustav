"""Teaching unit material routes split out of the larger teaching adapter."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Request

from backend.web.routes import teaching as teaching_routes


teaching_unit_materials_router = APIRouter(tags=["Teaching"])

_get_repo = teaching_routes._get_repo
_REPO = teaching_routes._REPO
REPO = teaching_routes.REPO
STORAGE_ADAPTER = teaching_routes.STORAGE_ADAPTER
_STORAGE_ADAPTER_OVERRIDE_ACTIVE = teaching_routes._STORAGE_ADAPTER_OVERRIDE_ACTIVE


@teaching_unit_materials_router.get("/api/teaching/units/{unit_id}/sections/{section_id}/materials")
async def list_section_materials(request: Request, unit_id: str, section_id: str):
    """List markdown materials of a section for its author."""

    return await teaching_routes.list_section_materials(
        request=request,
        unit_id=unit_id,
        section_id=section_id,
    )


@teaching_unit_materials_router.post("/api/teaching/units/{unit_id}/sections/{section_id}/materials")
async def create_section_material(
    request: Request,
    unit_id: str,
    section_id: str,
    payload: teaching_routes.MaterialCreatePayload,
):
    """Create a markdown material in a section."""

    return await teaching_routes.create_section_material(
        request=request,
        unit_id=unit_id,
        section_id=section_id,
        payload=payload,
    )


@teaching_unit_materials_router.patch("/api/teaching/units/{unit_id}/sections/{section_id}/materials/{material_id}")
async def update_section_material(
    request: Request,
    unit_id: str,
    section_id: str,
    material_id: str,
    payload: teaching_routes.MaterialUpdatePayload,
):
    """Update a markdown material in a section."""

    return await teaching_routes.update_section_material(
        request=request,
        unit_id=unit_id,
        section_id=section_id,
        material_id=material_id,
        payload=payload,
    )


@teaching_unit_materials_router.delete("/api/teaching/units/{unit_id}/sections/{section_id}/materials/{material_id}")
async def delete_section_material(request: Request, unit_id: str, section_id: str, material_id: str):
    """Delete a material in a section."""

    return await teaching_routes.delete_section_material(
        request=request,
        unit_id=unit_id,
        section_id=section_id,
        material_id=material_id,
    )


@teaching_unit_materials_router.post("/api/teaching/units/{unit_id}/sections/{section_id}/materials/upload-intents")
async def create_section_material_upload_intent(
    request: Request,
    unit_id: str,
    section_id: str,
    payload: teaching_routes.MaterialUploadIntentPayload,
):
    """Create a presigned upload intent for a file material."""

    return await teaching_routes.create_section_material_upload_intent(
        request=request,
        unit_id=unit_id,
        section_id=section_id,
        payload=payload,
    )


@teaching_unit_materials_router.post("/api/teaching/units/{unit_id}/sections/{section_id}/materials/finalize")
async def finalize_section_material_upload(
    request: Request,
    unit_id: str,
    section_id: str,
    payload: teaching_routes.MaterialFinalizePayload,
):
    """Finalize a file-material upload in a section."""

    return await teaching_routes.finalize_section_material_upload(
        request=request,
        unit_id=unit_id,
        section_id=section_id,
        payload=payload,
    )


@teaching_unit_materials_router.post("/api/teaching/units/{unit_id}/modules/{module_id}/materials")
async def create_module_material(
    request: Request,
    unit_id: str,
    module_id: str,
    payload: teaching_routes.MaterialCreatePayload,
):
    """Create a material in a module-backed section."""

    return await teaching_routes.create_module_material(
        request=request,
        unit_id=unit_id,
        module_id=module_id,
        payload=payload,
    )


@teaching_unit_materials_router.patch("/api/teaching/units/{unit_id}/modules/{module_id}/materials/{material_id}")
async def update_module_material(
    request: Request,
    unit_id: str,
    module_id: str,
    material_id: str,
    payload: teaching_routes.MaterialUpdatePayload,
):
    """Update a material in a module-backed section."""

    return await teaching_routes.update_module_material(
        request=request,
        unit_id=unit_id,
        module_id=module_id,
        material_id=material_id,
        payload=payload,
    )


@teaching_unit_materials_router.delete("/api/teaching/units/{unit_id}/modules/{module_id}/materials/{material_id}")
async def delete_module_material(
    request: Request,
    unit_id: str,
    module_id: str,
    material_id: str,
):
    """Delete a material in a module-backed section."""

    return await teaching_routes.delete_module_material(
        request=request,
        unit_id=unit_id,
        module_id=module_id,
        material_id=material_id,
    )


@teaching_unit_materials_router.post("/api/teaching/units/{unit_id}/modules/{module_id}/materials/reorder")
async def reorder_module_materials(
    request: Request,
    unit_id: str,
    module_id: str,
    payload: teaching_routes.MaterialReorderPayload,
):
    """Reorder materials in a module-backed section."""

    return await teaching_routes.reorder_module_materials(
        request=request,
        unit_id=unit_id,
        module_id=module_id,
        payload=payload,
    )


@teaching_unit_materials_router.post("/api/teaching/units/{unit_id}/modules/{module_id}/materials/upload-intents")
async def create_module_material_upload_intent(
    request: Request,
    unit_id: str,
    module_id: str,
    payload: teaching_routes.MaterialUploadIntentPayload,
):
    """Create a file-material upload intent in a module-backed section."""

    return await teaching_routes.create_module_material_upload_intent(
        request=request,
        unit_id=unit_id,
        module_id=module_id,
        payload=payload,
    )


@teaching_unit_materials_router.post("/api/teaching/units/{unit_id}/modules/{module_id}/materials/finalize")
async def finalize_module_material_upload(
    request: Request,
    unit_id: str,
    module_id: str,
    payload: teaching_routes.MaterialFinalizePayload,
):
    """Finalize a file-material upload in a module-backed section."""

    return await teaching_routes.finalize_module_material_upload(
        request=request,
        unit_id=unit_id,
        module_id=module_id,
        payload=payload,
    )


@teaching_unit_materials_router.get(
    "/api/teaching/units/{unit_id}/sections/{section_id}/materials/{material_id}/download-url"
)
async def get_section_material_download_url(
    request: Request,
    unit_id: str,
    section_id: str,
    material_id: str,
    disposition: Optional[str] = None,
):
    """Generate a short-lived file download URL for a material."""

    return await teaching_routes.get_section_material_download_url(
        request=request,
        unit_id=unit_id,
        section_id=section_id,
        material_id=material_id,
        disposition=disposition,
    )


@teaching_unit_materials_router.post("/api/teaching/units/{unit_id}/sections/{section_id}/materials/reorder")
async def reorder_section_materials(
    request: Request,
    unit_id: str,
    section_id: str,
    payload: teaching_routes.MaterialReorderPayload,
):
    """Reorder materials in a section."""

    return await teaching_routes.reorder_section_materials(
        request=request,
        unit_id=unit_id,
        section_id=section_id,
        payload=payload,
    )

