"""Contracts for splitting task-centric H5P authoring out of teaching.py.

Why:
    The Teaching router is a hotspot. The first route-split slice should move a
    cohesive, task-centric H5P authoring group into its own adapter module while
    keeping the public API paths unchanged.
"""

from __future__ import annotations

import importlib
from pathlib import Path

from fastapi.routing import APIRoute


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEACHING_SOURCE = PROJECT_ROOT / "backend" / "web" / "routes" / "teaching.py"
TEACHING_H5P_SOURCE = PROJECT_ROOT / "backend" / "web" / "routes" / "teaching_h5p.py"
H5P_ROUTE_PATHS = {
    "/api/teaching/units/{unit_id}/sections/{section_id}/tasks/{task_id}/h5p/editor-model",
    "/api/teaching/units/{unit_id}/sections/{section_id}/tasks/{task_id}/h5p/save",
    "/api/teaching/units/{unit_id}/sections/{section_id}/tasks/{task_id}/h5p/import",
    "/api/teaching/units/{unit_id}/sections/{section_id}/tasks/{task_id}/h5p/export",
    "/api/teaching/units/{unit_id}/sections/{section_id}/tasks/{task_id}/h5p/reset",
    "/api/teaching/units/{unit_id}/modules/{module_id}/tasks/{task_id}/h5p/import",
    "/api/teaching/units/{unit_id}/modules/{module_id}/tasks/{task_id}/h5p/reset",
}
SHARED_HELPER_DEFINITION_MARKERS = {
    "def _role_in",
    "def _current_sub",
    "def _require_teacher",
    "def _is_uuid_like",
    "def _json_private",
    "def _private_error",
}
H5P_AUTHORING_HELPER_MARKERS = {
    "H5P_INTERNAL_BASE",
    "H5P_DEFAULT_MAX_UPLOAD_BYTES",
    "H5P_UPLOAD_CHUNK_BYTES",
    "def _safe_header_value",
    "def _h5p_max_upload_bytes",
    "def _read_h5p_upload_file",
    "def _h5p_internal_auth_headers",
    "async def _request_h5p_service",
    "async def _call_request_h5p_service",
    "def _get_owned_h5p_task",
    "def _proxy_h5p_error_response",
    "async def _rollback_h5p_content",
    "class H5PTaskSavePayload",
}


def test_task_h5p_routes_are_owned_by_dedicated_router_module() -> None:
    """The H5P route split must preserve paths while moving endpoint ownership."""

    import backend.web.main as main

    h5p_routes = importlib.import_module("backend.web.routes.teaching_h5p")
    wiring_source = (PROJECT_ROOT / "backend" / "web" / "main_router_wiring.py").read_text(encoding="utf-8")
    teaching_source = TEACHING_SOURCE.read_text(encoding="utf-8")

    assert hasattr(h5p_routes, "teaching_h5p_router")
    assert "teaching_h5p_router" in wiring_source

    registered = {
        route.path: route.endpoint.__module__
        for route in main.app.routes
        if isinstance(route, APIRoute) and route.path in H5P_ROUTE_PATHS
    }

    assert set(registered) == H5P_ROUTE_PATHS
    assert set(registered.values()) == {"backend.web.routes.teaching_h5p"}

    for route_path in H5P_ROUTE_PATHS:
        assert route_path not in teaching_source


def test_task_h5p_authoring_helpers_live_with_the_h5p_router() -> None:
    """The route split should not leave H5P authoring plumbing in teaching.py."""

    h5p_routes = importlib.import_module("backend.web.routes.teaching_h5p")
    teaching_source = TEACHING_SOURCE.read_text(encoding="utf-8")

    for marker in H5P_AUTHORING_HELPER_MARKERS:
        assert marker not in teaching_source

    for helper_name in (
        "H5PTaskSavePayload",
        "_h5p_internal_auth_headers",
        "_request_h5p_service",
        "_call_request_h5p_service",
        "_read_h5p_upload_file",
        "_rollback_h5p_content",
    ):
        assert hasattr(h5p_routes, helper_name)


def test_h5p_router_uses_explicit_shared_teaching_helpers() -> None:
    """Shared response and identity helpers should not stay hidden in teaching.py."""

    shared_helpers = importlib.import_module("backend.web.routes.teaching_shared")
    teaching_source = TEACHING_SOURCE.read_text(encoding="utf-8")
    h5p_source = TEACHING_H5P_SOURCE.read_text(encoding="utf-8")

    for marker in SHARED_HELPER_DEFINITION_MARKERS:
        assert marker not in teaching_source

    for helper_name in (
        "_role_in",
        "_current_sub",
        "_require_teacher",
        "_is_uuid_like",
        "_json_private",
        "_private_error",
    ):
        assert hasattr(shared_helpers, helper_name)
        assert f"teaching.{helper_name}" not in h5p_source

    assert "from backend.web.routes.teaching_shared import" in teaching_source
    assert "from backend.web.routes.teaching_shared import" in h5p_source


def test_task_serializer_is_owned_by_dedicated_serialization_module() -> None:
    """Task response shaping should not remain hidden in the large Teaching router."""

    serializers = importlib.import_module("backend.web.routes.teaching_serialization")
    teaching_source = TEACHING_SOURCE.read_text(encoding="utf-8")
    h5p_source = TEACHING_H5P_SOURCE.read_text(encoding="utf-8")

    assert hasattr(serializers, "_serialize_task")
    assert "def _serialize_task" not in teaching_source
    assert "from backend.web.routes.teaching_serialization import" in teaching_source
    assert "from backend.web.routes.teaching_serialization import" in h5p_source
    assert "teaching._serialize_task" not in h5p_source

    serialized = serializers._serialize_task(  # type: ignore[attr-defined]
        {
            "id": "task-1",
            "kind": "h5p",
            "criteria": None,
            "h5p_content_id": "123",
            "h5p_display_options": {"frame": False},
        }
    )

    assert serialized["criteria"] == []
    assert serialized["h5p"] == {"content_id": "123", "display_options": {"frame": False}}
    assert serialized["visual"] is None
    assert "h5p_content_id" not in serialized
    assert "h5p_display_options" not in serialized


def test_h5p_router_uses_explicit_task_service_provider() -> None:
    """H5P authoring should not reach back into teaching.py for task services."""

    task_services = importlib.import_module("backend.web.routes.teaching_task_services")
    h5p_source = TEACHING_H5P_SOURCE.read_text(encoding="utf-8")

    assert hasattr(task_services, "_get_tasks_service")
    assert "from backend.web.routes import teaching_task_services" in h5p_source
    assert "teaching_task_services._get_tasks_service" in h5p_source
    assert "teaching._get_tasks_service" not in h5p_source


def test_h5p_router_uses_explicit_teaching_guard_module() -> None:
    """H5P authoring should import shared guards instead of reaching into teaching.py."""

    guards = importlib.import_module("backend.web.routes.teaching_guards")
    h5p_source = TEACHING_H5P_SOURCE.read_text(encoding="utf-8")

    assert hasattr(guards, "_guard_unit_author")
    assert hasattr(guards, "_csrf_guard")
    assert hasattr(guards, "configure_teaching_guard_repo_provider")
    assert "from backend.web.routes import teaching_guards" in h5p_source
    assert "teaching_guards._guard_unit_author" in h5p_source
    assert "teaching_guards._csrf_guard" in h5p_source
    assert "teaching._guard_unit_author" not in h5p_source
    assert "teaching._csrf_guard" not in h5p_source


def test_h5p_router_uses_explicit_module_authoring_boundary() -> None:
    """H5P authoring should not reach into teaching.py for module section lookup."""

    authoring = importlib.import_module("backend.web.routes.teaching_authoring")
    h5p_source = TEACHING_H5P_SOURCE.read_text(encoding="utf-8")

    assert hasattr(authoring, "_resolve_module_section_for_authoring_mutation")
    assert hasattr(authoring, "configure_teaching_authoring_repo_provider")
    assert "from backend.web.routes import teaching_authoring" in h5p_source
    assert "teaching_authoring._resolve_module_section_for_authoring_mutation" in h5p_source
    assert "\nfrom backend.web.routes import teaching\n" not in h5p_source
    assert "\nfrom backend.web.routes import teaching as " not in h5p_source
    assert "teaching._" not in h5p_source
