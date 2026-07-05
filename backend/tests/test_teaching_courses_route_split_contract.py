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


def test_course_router_wrappers_delegate_to_teaching_module() -> None:
    """Wrapper functions should delegate unchanged to teaching handlers."""

    course_source = COURSES_SOURCE.read_text(encoding="utf-8")
    expected_delegations = {
        "list_courses": "teaching_routes.list_courses(",
        "create_course": "teaching_routes.create_course(",
        "get_course": "teaching_routes.get_course(",
        "update_course": "teaching_routes.update_course(",
        "delete_course": "teaching_routes.delete_course(",
    }

    for fn_name, marker in expected_delegations.items():
        assert f"def {fn_name}(" in course_source
        assert marker in course_source
