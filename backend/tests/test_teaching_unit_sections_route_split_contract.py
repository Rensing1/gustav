"""Contracts for the teaching unit-section route split."""

from __future__ import annotations

import importlib
from pathlib import Path

from fastapi.routing import APIRoute


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEACHING_SOURCE = PROJECT_ROOT / "backend" / "web" / "routes" / "teaching.py"
SECTIONS_SOURCE = PROJECT_ROOT / "backend" / "web" / "routes" / "teaching_unit_sections.py"
MAIN_ROUTER_SOURCE = PROJECT_ROOT / "backend" / "web" / "main_router_wiring.py"

SECTION_ROUTE_PATHS = {
    "/api/teaching/units/{unit_id}/sections",
    "/api/teaching/units/{unit_id}/sections/{section_id}",
    "/api/teaching/units/{unit_id}/sections/reorder",
}


def test_unit_sections_routes_are_owned_by_dedicated_router_module() -> None:
    """Section routes should be owned by a dedicated router with the same runtime paths."""

    import backend.web.main as main

    sections_router = importlib.import_module("backend.web.routes.teaching_unit_sections")
    wiring_source = MAIN_ROUTER_SOURCE.read_text(encoding="utf-8")
    teaching_source = TEACHING_SOURCE.read_text(encoding="utf-8")

    assert hasattr(sections_router, "teaching_unit_sections_router")
    assert "teaching_unit_sections_router" in wiring_source

    registered = {
        route.path: route.endpoint.__module__
        for route in main.app.routes
        if isinstance(route, APIRoute) and route.path in SECTION_ROUTE_PATHS
    }

    assert set(registered) == SECTION_ROUTE_PATHS
    assert set(registered.values()) == {"backend.web.routes.teaching_unit_sections"}

    for path in SECTION_ROUTE_PATHS:
        for method in ("get", "post", "patch", "delete"):
            marker = f"@teaching_router.{method}(\"{path}\""
            assert marker not in teaching_source


def test_unit_sections_router_owns_handlers_without_teaching_delegation() -> None:
    """Section handlers should not keep the large Teaching adapter as implementation."""

    sections_source = SECTIONS_SOURCE.read_text(encoding="utf-8")
    teaching_source = TEACHING_SOURCE.read_text(encoding="utf-8")
    handler_names = (
        "list_sections",
        "create_section",
        "update_section",
        "delete_section",
        "reorder_sections",
    )

    assert "from backend.web.routes import teaching as teaching_routes" not in sections_source
    for fn_name in handler_names:
        assert f"def {fn_name}(" in sections_source
        assert f"teaching_routes.{fn_name}(" not in sections_source
        assert f"async def {fn_name}(" not in teaching_source
