"""Contracts for the teaching course-members route split."""

from __future__ import annotations

import importlib
from pathlib import Path

from fastapi.routing import APIRoute


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEACHING_SOURCE = PROJECT_ROOT / "backend" / "web" / "routes" / "teaching.py"
COURSE_MEMBERS_SOURCE = PROJECT_ROOT / "backend" / "web" / "routes" / "teaching_course_members.py"
MAIN_ROUTER_SOURCE = PROJECT_ROOT / "backend" / "web" / "main_router_wiring.py"

COURSE_MEMBER_ROUTE_PATHS = {
    "/api/teaching/courses/{course_id}/members",
    "/api/teaching/courses/{course_id}/members/{student_sub}",
}


def test_course_member_routes_are_owned_by_dedicated_router_module() -> None:
    """Member routes should stay on the same paths but be owned by a new router."""

    import backend.web.main as main

    members_router = importlib.import_module("backend.web.routes.teaching_course_members")
    wiring_source = MAIN_ROUTER_SOURCE.read_text(encoding="utf-8")
    teaching_source = TEACHING_SOURCE.read_text(encoding="utf-8")

    assert hasattr(members_router, "teaching_course_members_router")
    assert "teaching_course_members_router" in wiring_source

    registered = {
        route.path: route.endpoint.__module__
        for route in main.app.routes
        if isinstance(route, APIRoute) and route.path in COURSE_MEMBER_ROUTE_PATHS
    }

    assert set(registered) == COURSE_MEMBER_ROUTE_PATHS
    assert set(registered.values()) == {"backend.web.routes.teaching_course_members"}

    for path in COURSE_MEMBER_ROUTE_PATHS:
        assert path not in teaching_source


def test_course_member_router_owns_handlers_without_teaching_delegation() -> None:
    """Course-member handlers should not keep the large Teaching adapter as implementation."""

    course_member_source = COURSE_MEMBERS_SOURCE.read_text(encoding="utf-8")
    teaching_source = TEACHING_SOURCE.read_text(encoding="utf-8")
    handler_names = ("list_members", "add_member", "remove_member")

    assert "from backend.web.routes import teaching as teaching_routes" not in course_member_source
    for fn_name in handler_names:
        assert f"def {fn_name}(" in course_member_source
        assert f"teaching_routes.{fn_name}(" not in course_member_source
        assert f"async def {fn_name}(" not in teaching_source
