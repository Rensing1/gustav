"""Contracts for the teaching unit modules/phases route split."""

from __future__ import annotations

import importlib
from pathlib import Path

from fastapi.routing import APIRoute


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEACHING_SOURCE = PROJECT_ROOT / "backend" / "web" / "routes" / "teaching.py"
UNIT_MODULE_SOURCE = PROJECT_ROOT / "backend" / "web" / "routes" / "teaching_unit_modules.py"
MAIN_ROUTER_SOURCE = PROJECT_ROOT / "backend" / "web" / "main_router_wiring.py"

UNIT_MODULE_ROUTE_PATHS = {
    "/api/teaching/units/{unit_id}/phases",
    "/api/teaching/units/{unit_id}/phases/{phase_id}",
    "/api/teaching/units/{unit_id}/phases/reorder",
    "/api/teaching/units/{unit_id}/modules/graph",
    "/api/teaching/units/{unit_id}/modules/{module_id}/content-target",
    "/api/teaching/units/{unit_id}/modules",
    "/api/teaching/units/{unit_id}/modules/edges",
    "/api/teaching/units/{unit_id}/modules/{from_module_id}/edges/{to_module_id}",
    "/api/teaching/units/{unit_id}/modules/{module_id}",
    "/api/teaching/units/{unit_id}/phases/{phase_id}/modules/reorder",
}


def test_unit_module_routes_are_owned_by_dedicated_router_module() -> None:
    """Unit module/phases routes stay on the same paths but move to dedicated router."""

    import backend.web.main as main

    modules_router = importlib.import_module("backend.web.routes.teaching_unit_modules")
    wiring_source = MAIN_ROUTER_SOURCE.read_text(encoding="utf-8")
    teaching_source = TEACHING_SOURCE.read_text(encoding="utf-8")

    assert hasattr(modules_router, "teaching_unit_modules_router")
    assert "teaching_unit_modules_router" in wiring_source

    registered = {
        route.path: route.endpoint.__module__
        for route in main.app.routes
        if isinstance(route, APIRoute) and route.path in UNIT_MODULE_ROUTE_PATHS
    }

    assert set(registered) == UNIT_MODULE_ROUTE_PATHS
    assert set(registered.values()) == {"backend.web.routes.teaching_unit_modules"}

    for path in UNIT_MODULE_ROUTE_PATHS:
        for method in ("get", "post", "patch", "delete"):
            marker = f"@teaching_router.{method}(\"{path}\""
            assert marker not in teaching_source


def test_unit_module_router_owns_handlers_without_teaching_delegation() -> None:
    """Unit module/phase handlers must live in the dedicated router module."""

    modules_source = UNIT_MODULE_SOURCE.read_text(encoding="utf-8")
    teaching_source = TEACHING_SOURCE.read_text(encoding="utf-8")

    assert "from backend.web.routes import teaching as teaching_routes" not in modules_source

    owned_handlers = (
        "list_unit_phases",
        "create_unit_phase",
        "update_unit_phase",
        "delete_unit_phase",
        "reorder_unit_phases",
        "get_unit_modules_graph",
        "get_unit_module_content_target",
        "create_unit_module",
        "create_unit_module_edge",
        "delete_unit_module_edge",
        "delete_unit_module_edge_by_path",
        "update_unit_module",
        "delete_unit_module",
        "reorder_unit_phase_modules",
    )

    for fn_name in owned_handlers:
        assert f"def {fn_name}(" in modules_source
        assert f"teaching_routes.{fn_name}(" not in modules_source
        assert f"async def {fn_name}(" not in teaching_source
