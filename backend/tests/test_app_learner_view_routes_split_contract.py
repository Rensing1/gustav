"""Contracts for keeping learner app routes outside the app-route hotspot."""

from __future__ import annotations

import importlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_learner_routes_live_in_focused_router_module() -> None:
    app_routes = importlib.import_module("backend.web.routes.app")
    learner_routes = importlib.import_module("backend.web.routes.app_learner_view_routes")

    assert app_routes.get_learner_home is learner_routes.get_learner_home
    assert app_routes.get_learner_concern_box is learner_routes.get_learner_concern_box
    assert app_routes.create_learner_concern_box_entry is learner_routes.create_learner_concern_box_entry


def test_app_hotspot_no_longer_defines_learner_route_handlers_or_payload() -> None:
    source = (REPO_ROOT / "backend" / "web" / "routes" / "app.py").read_text(encoding="utf-8")

    assert "class ConcernBoxEntryCreatePayload(" not in source
    assert "async def get_learner_home(" not in source
    assert "async def get_learner_concern_box(" not in source
    assert "async def create_learner_concern_box_entry(" not in source


def test_learner_router_owns_learner_paths() -> None:
    learner_routes = importlib.import_module("backend.web.routes.app_learner_view_routes")

    paths = {getattr(route, "path", "") for route in learner_routes.app_learner_view_router.routes}

    assert "/api/learning/views/learner-home" in paths
    assert "/api/learning/views/concern-box" in paths
    assert "/api/learning/concern-box/entries" in paths
