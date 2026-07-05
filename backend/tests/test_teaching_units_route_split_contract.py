"""Contracts for the teaching unit route split."""

from __future__ import annotations

import importlib
from pathlib import Path

from fastapi.routing import APIRoute


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEACHING_SOURCE = PROJECT_ROOT / "backend" / "web" / "routes" / "teaching.py"
UNITS_SOURCE = PROJECT_ROOT / "backend" / "web" / "routes" / "teaching_units.py"
MAIN_ROUTER_SOURCE = PROJECT_ROOT / "backend" / "web" / "main_router_wiring.py"

UNIT_ROUTE_PATHS = {
    "/api/teaching/units",
    "/api/teaching/units/{unit_id}",
}


def test_unit_routes_are_owned_by_dedicated_router_module() -> None:
    """Unit endpoints should move to a dedicated router with unchanged paths."""

    import backend.web.main as main

    units_router = importlib.import_module("backend.web.routes.teaching_units")
    wiring_source = MAIN_ROUTER_SOURCE.read_text(encoding="utf-8")
    teaching_source = TEACHING_SOURCE.read_text(encoding="utf-8")

    assert hasattr(units_router, "teaching_units_router")
    assert "teaching_units_router" in wiring_source

    registered = {
        route.path: route.endpoint.__module__
        for route in main.app.routes
        if isinstance(route, APIRoute) and route.path in UNIT_ROUTE_PATHS
    }

    assert set(registered) == UNIT_ROUTE_PATHS
    assert set(registered.values()) == {"backend.web.routes.teaching_units"}

    for path in UNIT_ROUTE_PATHS:
        for method in ("get", "post", "patch", "delete"):
            assert f"@teaching_router.{method}(\"{path}\"" not in teaching_source


def test_unit_router_owns_handlers_without_teaching_delegation() -> None:
    """Unit handlers should not keep the large Teaching adapter as implementation."""

    units_source = UNITS_SOURCE.read_text(encoding="utf-8")
    teaching_source = TEACHING_SOURCE.read_text(encoding="utf-8")
    handler_names = (
        "list_units",
        "create_unit",
        "get_unit",
        "update_unit",
        "delete_unit",
    )

    assert "from backend.web.routes import teaching as teaching_routes" not in units_source
    for fn_name in handler_names:
        assert f"def {fn_name}(" in units_source
        assert f"teaching_routes.{fn_name}(" not in units_source
        assert f"async def {fn_name}(" not in teaching_source
