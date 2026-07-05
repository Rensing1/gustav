"""Contracts for the teaching course route split."""

from __future__ import annotations

import importlib
from pathlib import Path

from fastapi.routing import APIRoute


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEACHING_SOURCE = PROJECT_ROOT / "backend" / "web" / "routes" / "teaching.py"
COURSES_SOURCE = PROJECT_ROOT / "backend" / "web" / "routes" / "teaching_courses.py"
MAIN_ROUTER_SOURCE = PROJECT_ROOT / "backend" / "web" / "main_router_wiring.py"

COURSE_ROUTE_PATHS = {
    "/api/teaching/courses",
    "/api/teaching/courses/{course_id}",
}


def test_course_routes_are_owned_by_dedicated_router_module() -> None:
    """Course endpoints should move to a dedicated router with unchanged paths."""

    import backend.web.main as main

    courses_router = importlib.import_module("backend.web.routes.teaching_courses")
    wiring_source = MAIN_ROUTER_SOURCE.read_text(encoding="utf-8")
    teaching_source = TEACHING_SOURCE.read_text(encoding="utf-8")

    assert hasattr(courses_router, "teaching_courses_router")
    assert "teaching_courses_router" in wiring_source

    registered = {
        route.path: route.endpoint.__module__
        for route in main.app.routes
        if isinstance(route, APIRoute) and route.path in COURSE_ROUTE_PATHS
    }

    assert set(registered) == COURSE_ROUTE_PATHS
    assert set(registered.values()) == {"backend.web.routes.teaching_courses"}

    for path in COURSE_ROUTE_PATHS:
        for method in ("get", "post", "patch", "delete"):
            assert f"@teaching_router.{method}(\"{path}\"" not in teaching_source


def test_course_router_owns_handlers_without_teaching_delegation() -> None:
    """Course handlers should not keep the large Teaching adapter as implementation."""

    course_source = COURSES_SOURCE.read_text(encoding="utf-8")
    teaching_source = TEACHING_SOURCE.read_text(encoding="utf-8")
    handler_names = (
        "list_courses",
        "create_course",
        "get_course",
        "update_course",
        "delete_course",
    )

    assert "from backend.web.routes import teaching as teaching_routes" not in course_source
    for fn_name in handler_names:
        assert f"def {fn_name}(" in course_source
        assert f"teaching_routes.{fn_name}(" not in course_source
        assert f"async def {fn_name}(" not in teaching_source
