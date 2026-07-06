"""Contracts for keeping teacher course view routes outside the app-route hotspot."""

from __future__ import annotations

import importlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_teacher_course_routes_live_in_focused_router_module() -> None:
    app_routes = importlib.import_module("backend.web.routes.app")
    course_routes = importlib.import_module("backend.web.routes.app_teacher_course_routes")

    assert app_routes.get_teacher_course_list is course_routes.get_teacher_course_list
    assert app_routes.get_teacher_course_context is course_routes.get_teacher_course_context
    assert app_routes.get_teacher_course_ai_usage is course_routes.get_teacher_course_ai_usage


def test_app_hotspot_no_longer_defines_teacher_course_handlers_or_helpers() -> None:
    source = (REPO_ROOT / "backend" / "web" / "routes" / "app.py").read_text(encoding="utf-8")

    assert "def _count_teacher_course_members(" not in source
    assert "def _list_teacher_course_cards(" not in source
    assert "def _list_teacher_course_members(" not in source
    assert "def _list_teacher_course_members_window(" not in source
    assert "def _parse_usage_filter_timestamp(" not in source
    assert "def _empty_usage_totals(" not in source
    assert "def _build_usage_totals(" not in source
    assert "def _list_teacher_course_ai_usage_events(" not in source
    assert "def _get_teacher_course(" not in source
    assert "async def get_teacher_course_list(" not in source
    assert "async def get_teacher_course_context(" not in source
    assert "async def get_teacher_course_ai_usage(" not in source


def test_teacher_course_router_owns_teacher_course_paths() -> None:
    course_routes = importlib.import_module("backend.web.routes.app_teacher_course_routes")

    paths = {getattr(route, "path", "") for route in course_routes.app_teacher_course_router.routes}

    assert "/api/teaching/views/courses" in paths
    assert "/api/teaching/views/courses/{course_id}/context" in paths
    assert "/api/teaching/views/courses/{course_id}/ai-usage" in paths
