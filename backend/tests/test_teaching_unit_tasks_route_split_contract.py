"""Contracts for the teaching unit-task route split."""

from __future__ import annotations

import importlib
from pathlib import Path

from fastapi.routing import APIRoute


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEACHING_SOURCE = PROJECT_ROOT / "backend" / "web" / "routes" / "teaching.py"
TASKS_SOURCE = PROJECT_ROOT / "backend" / "web" / "routes" / "teaching_unit_tasks.py"
MAIN_ROUTER_SOURCE = PROJECT_ROOT / "backend" / "web" / "main_router_wiring.py"

TASK_ROUTE_PATHS = {
    "/api/teaching/units/{unit_id}/sections/{section_id}/tasks",
    "/api/teaching/units/{unit_id}/sections/{section_id}/tasks/{task_id}",
    "/api/teaching/units/{unit_id}/sections/{section_id}/tasks/reorder",
    "/api/teaching/units/{unit_id}/modules/{module_id}/tasks",
    "/api/teaching/units/{unit_id}/modules/{module_id}/tasks/{task_id}",
    "/api/teaching/units/{unit_id}/modules/{module_id}/tasks/reorder",
}


def test_unit_task_routes_are_owned_by_dedicated_router_module() -> None:
    """Task routes stay on the same paths but move to a dedicated router."""

    import backend.web.main as main

    tasks_router = importlib.import_module("backend.web.routes.teaching_unit_tasks")
    wiring_source = MAIN_ROUTER_SOURCE.read_text(encoding="utf-8")
    teaching_source = TEACHING_SOURCE.read_text(encoding="utf-8")

    assert hasattr(tasks_router, "teaching_unit_tasks_router")
    assert "teaching_unit_tasks_router" in wiring_source

    registered = {
        route.path: route.endpoint.__module__
        for route in main.app.routes
        if isinstance(route, APIRoute) and route.path in TASK_ROUTE_PATHS
    }

    assert set(registered) == TASK_ROUTE_PATHS
    assert set(registered.values()) == {"backend.web.routes.teaching_unit_tasks"}

    for path in TASK_ROUTE_PATHS:
        for method in ("get", "post", "patch", "delete"):
            assert f"@teaching_router.{method}(\"{path}\"" not in teaching_source


def test_unit_task_router_owns_handlers_without_teaching_delegation() -> None:
    """Task handlers should not keep the large Teaching adapter as implementation."""

    tasks_source = TASKS_SOURCE.read_text(encoding="utf-8")
    teaching_source = TEACHING_SOURCE.read_text(encoding="utf-8")
    handler_names = (
        "list_section_tasks",
        "create_section_task",
        "update_section_task",
        "delete_section_task",
        "reorder_section_tasks",
        "list_module_tasks",
        "create_module_task",
        "update_module_task",
        "delete_module_task",
        "reorder_module_tasks",
    )

    assert "from backend.web.routes import teaching as teaching_routes" not in tasks_source
    for fn_name in handler_names:
        assert f"def {fn_name}(" in tasks_source
        assert f"teaching_routes.{fn_name}(" not in tasks_source
        assert f"async def {fn_name}(" not in teaching_source
