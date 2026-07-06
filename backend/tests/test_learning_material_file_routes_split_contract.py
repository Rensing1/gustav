"""Contracts for keeping learner material-file routes outside the Learning hotspot."""

from __future__ import annotations

import importlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_material_file_routes_live_in_focused_router_module() -> None:
    learning = importlib.import_module("backend.web.routes.learning")
    material_routes = importlib.import_module("backend.web.routes.learning_material_file_routes")

    assert learning.get_material_file is material_routes.get_material_file
    assert learning.get_material_file_legacy_alias is material_routes.get_material_file_legacy_alias


def test_learning_hotspot_no_longer_defines_material_file_route_handlers() -> None:
    source = (REPO_ROOT / "backend" / "web" / "routes" / "learning.py").read_text(encoding="utf-8")

    assert "async def get_material_file(" not in source
    assert "async def get_material_file_legacy_alias(" not in source


def test_material_file_router_owns_canonical_and_legacy_paths() -> None:
    material_routes = importlib.import_module("backend.web.routes.learning_material_file_routes")

    paths = {getattr(route, "path", "") for route in material_routes.learning_material_file_router.routes}

    assert "/api/learning/courses/{course_id}/materials/{material_id}/file" in paths
    assert "/api/learning/courses/{course_id}/sections/{section_id}/materials/{material_id}/file" in paths
