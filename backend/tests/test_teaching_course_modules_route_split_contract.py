"""Contracts for the teaching course-modules route split."""

from __future__ import annotations

import importlib
from pathlib import Path

from fastapi.routing import APIRoute


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEACHING_SOURCE = PROJECT_ROOT / "backend" / "web" / "routes" / "teaching.py"
COURSE_MODULES_SOURCE = PROJECT_ROOT / "backend" / "web" / "routes" / "teaching_course_modules.py"
MAIN_ROUTER_SOURCE = PROJECT_ROOT / "backend" / "web" / "main_router_wiring.py"

COURSE_MODULE_ROUTE_PATHS = {
    "/api/teaching/courses/{course_id}/modules",
    "/api/teaching/courses/{course_id}/modules/reorder",
    "/api/teaching/courses/{course_id}/modules/{module_id}",
    "/api/teaching/courses/{course_id}/modules/{module_id}/sections/{section_id}/visibility",
    "/api/teaching/courses/{course_id}/modules/{module_id}/sections/releases",
    "/api/teaching/courses/{course_id}/modules/{module_id}/sections",
}


def test_course_module_routes_are_owned_by_dedicated_router_module() -> None:
    """Moving the course module endpoints to a dedicated router keeps path behavior unchanged."""

    import backend.web.main as main

    course_module_routes = importlib.import_module("backend.web.routes.teaching_course_modules")
    wiring_source = MAIN_ROUTER_SOURCE.read_text(encoding="utf-8")
    teaching_source = TEACHING_SOURCE.read_text(encoding="utf-8")

    assert hasattr(course_module_routes, "teaching_course_modules_router")
    assert "teaching_course_modules_router" in wiring_source

    registered = {
        route.path: route.endpoint.__module__
        for route in main.app.routes
        if isinstance(route, APIRoute) and route.path in COURSE_MODULE_ROUTE_PATHS
    }

    assert set(registered) == COURSE_MODULE_ROUTE_PATHS
    assert set(registered.values()) == {"backend.web.routes.teaching_course_modules"}

    for path in COURSE_MODULE_ROUTE_PATHS:
        assert path not in teaching_source


def test_course_module_router_wrappers_delegate_to_teaching_module() -> None:
    """Wrapper functions should delegate to existing teaching handlers."""

    course_module_source = COURSE_MODULES_SOURCE.read_text(encoding="utf-8")
    expected_delegations = {
        "list_course_modules": "teaching_routes.list_course_modules(",
        "create_course_module": "teaching_routes.create_course_module(",
        "reorder_course_modules": "teaching_routes.reorder_course_modules(",
        "delete_course_module": "teaching_routes.delete_course_module(",
        "update_module_section_visibility": "teaching_routes.update_module_section_visibility(",
        "list_module_section_releases": "teaching_routes.list_module_section_releases(",
        "list_module_sections_with_visibility": "teaching_routes.list_module_sections_with_visibility(",
    }

    for fn_name, marker in expected_delegations.items():
        assert f"def {fn_name}(" in course_module_source
        assert marker in course_module_source
