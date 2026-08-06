"""Contracts for keeping teacher concern-box routes outside the app-route hotspot."""

from __future__ import annotations

import importlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_teacher_concern_routes_live_in_focused_router_module() -> None:
    app_routes = importlib.import_module("backend.web.routes.app")
    concern_routes = importlib.import_module("backend.web.routes.app_teacher_concern_routes")

    assert app_routes.get_teacher_home is concern_routes.get_teacher_home
    assert app_routes.get_teacher_concern_box is concern_routes.get_teacher_concern_box
    assert app_routes.archive_teacher_concern_box_entry is concern_routes.archive_teacher_concern_box_entry
    assert app_routes.restore_teacher_concern_box_entry is concern_routes.restore_teacher_concern_box_entry


def test_app_hotspot_no_longer_defines_teacher_concern_handlers_or_helpers() -> None:
    source = (REPO_ROOT / "backend" / "web" / "routes" / "app.py").read_text(encoding="utf-8")

    assert "def _teacher_home_workstarter(" not in source
    assert "def _teacher_concern_box_scopes(" not in source
    assert "async def get_teacher_home(" not in source
    assert "async def get_teacher_concern_box(" not in source
    assert "async def archive_teacher_concern_box_entry(" not in source
    assert "async def restore_teacher_concern_box_entry(" not in source


def test_teacher_concern_router_owns_teacher_concern_paths() -> None:
    concern_routes = importlib.import_module("backend.web.routes.app_teacher_concern_routes")

    paths = {getattr(route, "path", "") for route in concern_routes.app_teacher_concern_router.routes}

    assert "/api/teaching/views/teacher-home" in paths
    assert "/api/teaching/views/concern-box" in paths
    assert "/api/teaching/concern-box/entries/{entry_id}/archive" in paths
    assert "/api/teaching/concern-box/entries/{entry_id}/restore" in paths
