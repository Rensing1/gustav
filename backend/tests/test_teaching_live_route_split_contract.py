"""Contracts for the Teaching live route split."""

from __future__ import annotations

import importlib
from pathlib import Path

from fastapi.routing import APIRoute


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEACHING_SOURCE = PROJECT_ROOT / "backend" / "web" / "routes" / "teaching.py"
TEACHING_LIVE_SOURCE = PROJECT_ROOT / "backend" / "web" / "routes" / "teaching_live.py"
MAIN_ROUTER_SOURCE = PROJECT_ROOT / "backend" / "web" / "main_router_wiring.py"
TEACHING_LIVE_ROUTES = {
    "/api/teaching/courses/{course_id}/units/{unit_id}/submissions/summary",
    "/api/teaching/courses/{course_id}/units/{unit_id}/submissions/delta",
    "/api/teaching/courses/{course_id}/students/{student_sub:path}/submissions/overview",
    "/api/teaching/courses/{course_id}/units/{unit_id}/tasks/{task_id}/students/{student_sub:path}/submissions/latest",
    "/api/teaching/courses/{course_id}/units/{unit_id}/tasks/{task_id}/students/{student_sub:path}/submissions/latest/file",
}


def test_live_routes_are_owned_by_dedicated_router_module() -> None:
    """The split should keep API paths and move endpoint ownership to `teaching_live.py`."""

    import backend.web.main as main

    _ = importlib.import_module("backend.web.routes.teaching_live")
    teaching_source = TEACHING_SOURCE.read_text(encoding="utf-8")
    live_router_source = TEACHING_LIVE_SOURCE.read_text(encoding="utf-8")
    wiring_source = MAIN_ROUTER_SOURCE.read_text(encoding="utf-8")

    assert "teaching_live_router" in wiring_source

    registered = {
        route.path: route.endpoint.__module__
        for route in main.app.routes
        if isinstance(route, APIRoute) and route.path in TEACHING_LIVE_ROUTES
    }

    assert set(registered) == TEACHING_LIVE_ROUTES
    assert set(registered.values()) == {"backend.web.routes.teaching_live"}

    for path in TEACHING_LIVE_ROUTES:
        assert path in live_router_source
        assert path not in teaching_source


def test_live_router_wrappers_delegate_to_teaching_module() -> None:
    """Wrapper functions should delegate unchanged behavior to the existing teaching handlers."""

    live_router_source = TEACHING_LIVE_SOURCE.read_text(encoding="utf-8")

    expected_delegations = {
        "get_unit_live_summary": "teaching_routes.get_unit_live_summary(",
        "get_unit_live_delta": "teaching_routes.get_unit_live_delta(",
        "get_student_live_overview": "teaching_routes.get_student_live_overview(",
        "get_latest_submission_detail": "teaching_routes.get_latest_submission_detail(",
        "get_teaching_submission_file": "teaching_routes.get_teaching_submission_file(",
    }

    for name, delegate in expected_delegations.items():
        assert f"def {name}(" in live_router_source
        assert delegate in live_router_source

    live_module = importlib.import_module("backend.web.routes.teaching_live")
    assert hasattr(live_module, "teaching_live_router")
