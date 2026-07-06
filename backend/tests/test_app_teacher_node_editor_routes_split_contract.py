"""Contracts for keeping teacher node-editor BFF routes outside app.py."""

from __future__ import annotations

import importlib
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_SOURCE = PROJECT_ROOT / "backend" / "web" / "routes" / "app.py"
NODE_ROUTES_SOURCE = PROJECT_ROOT / "backend" / "web" / "routes" / "app_teacher_node_editor_routes.py"


def test_teacher_node_editor_route_lives_outside_app_hotspot() -> None:
    app = importlib.import_module("backend.web.routes.app")
    node_routes = importlib.import_module("backend.web.routes.app_teacher_node_editor_routes")
    app_source = APP_SOURCE.read_text(encoding="utf-8")
    node_source = NODE_ROUTES_SOURCE.read_text(encoding="utf-8")

    assert app.app_teacher_node_editor_router is node_routes.app_teacher_node_editor_router
    assert app.get_teacher_unit_node_editor is node_routes.get_teacher_unit_node_editor
    assert '@app_router.get("/api/teaching/views/units/{unit_id}/nodes/{node_id}/editor")' not in app_source
    assert '@app_teacher_node_editor_router.get("/api/teaching/views/units/{unit_id}/nodes/{node_id}/editor")' in node_source
