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


def test_unit_router_wrappers_delegate_to_teaching_module() -> None:
    """Wrapper functions should delegate unchanged to teaching handlers."""

    units_source = UNITS_SOURCE.read_text(encoding="utf-8")
    expected_delegations = {
        "list_units": "teaching_routes.list_units(",
        "create_unit": "teaching_routes.create_unit(",
        "get_unit": "teaching_routes.get_unit(",
        "update_unit": "teaching_routes.update_unit(",
        "delete_unit": "teaching_routes.delete_unit(",
    }

    for fn_name, marker in expected_delegations.items():
        assert f"def {fn_name}(" in units_source
        assert marker in units_source
