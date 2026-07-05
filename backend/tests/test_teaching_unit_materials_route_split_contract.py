"""Contracts for the teaching unit-material route split."""

from __future__ import annotations

import importlib
from pathlib import Path

from fastapi.routing import APIRoute


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEACHING_SOURCE = PROJECT_ROOT / "backend" / "web" / "routes" / "teaching.py"
MATERIALS_SOURCE = PROJECT_ROOT / "backend" / "web" / "routes" / "teaching_unit_materials.py"
MAIN_ROUTER_SOURCE = PROJECT_ROOT / "backend" / "web" / "main_router_wiring.py"


MATERIAL_ROUTE_PATHS = {
    "/api/teaching/units/{unit_id}/sections/{section_id}/materials",
    "/api/teaching/units/{unit_id}/sections/{section_id}/materials/{material_id}",
    "/api/teaching/units/{unit_id}/sections/{section_id}/materials/upload-intents",
    "/api/teaching/units/{unit_id}/sections/{section_id}/materials/finalize",
    "/api/teaching/units/{unit_id}/sections/{section_id}/materials/{material_id}/download-url",
    "/api/teaching/units/{unit_id}/sections/{section_id}/materials/reorder",
    "/api/teaching/units/{unit_id}/modules/{module_id}/materials",
    "/api/teaching/units/{unit_id}/modules/{module_id}/materials/{material_id}",
    "/api/teaching/units/{unit_id}/modules/{module_id}/materials/reorder",
    "/api/teaching/units/{unit_id}/modules/{module_id}/materials/upload-intents",
    "/api/teaching/units/{unit_id}/modules/{module_id}/materials/finalize",
}


def test_unit_material_routes_are_owned_by_dedicated_router_module() -> None:
    """Material routes should live under a dedicated router with unchanged runtime paths."""

    import backend.web.main as main

    materials_router = importlib.import_module("backend.web.routes.teaching_unit_materials")
    wiring_source = MAIN_ROUTER_SOURCE.read_text(encoding="utf-8")
    teaching_source = TEACHING_SOURCE.read_text(encoding="utf-8")

    assert hasattr(materials_router, "teaching_unit_materials_router")
    assert "teaching_unit_materials_router" in wiring_source

    registered = {
        route.path: route.endpoint.__module__
        for route in main.app.routes
        if isinstance(route, APIRoute) and route.path in MATERIAL_ROUTE_PATHS
    }

    assert set(registered) == MATERIAL_ROUTE_PATHS
    assert set(registered.values()) == {"backend.web.routes.teaching_unit_materials"}

    for path in MATERIAL_ROUTE_PATHS:
        for method in ("get", "post", "patch", "delete"):
            marker = f"@teaching_router.{method}(\"{path}\""
            assert marker not in teaching_source


def test_unit_material_router_owns_handlers_without_teaching_delegation() -> None:
    """Material route handlers must live in the dedicated router module."""

    materials_source = MATERIALS_SOURCE.read_text(encoding="utf-8")
    teaching_source = TEACHING_SOURCE.read_text(encoding="utf-8")

    assert "from backend.web.routes import teaching as teaching_routes" not in materials_source

    owned_handlers = (
        "list_section_materials",
        "create_section_material",
        "update_section_material",
        "delete_section_material",
        "create_section_material_upload_intent",
        "finalize_section_material_upload",
        "create_module_material",
        "update_module_material",
        "delete_module_material",
        "reorder_module_materials",
        "create_module_material_upload_intent",
        "finalize_module_material_upload",
        "get_section_material_download_url",
        "reorder_section_materials",
    )

    for fn_name in owned_handlers:
        assert f"def {fn_name}(" in materials_source
        assert f"teaching_routes.{fn_name}(" not in materials_source
        assert f"async def {fn_name}(" not in teaching_source
