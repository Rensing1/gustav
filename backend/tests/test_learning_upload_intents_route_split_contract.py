"""Contracts for keeping Learning upload-intent routes outside the route hotspot."""

from __future__ import annotations

import importlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_learning_upload_intent_route_lives_in_focused_router_module() -> None:
    learning = importlib.import_module("backend.web.routes.learning")
    upload_intents = importlib.import_module("backend.web.routes.learning_upload_intents")

    assert learning.create_upload_intent is upload_intents.create_upload_intent


def test_learning_hotspot_no_longer_defines_upload_intent_handler() -> None:
    source = (REPO_ROOT / "backend" / "web" / "routes" / "learning.py").read_text(encoding="utf-8")

    assert "async def create_upload_intent(" not in source


def test_learning_upload_intent_router_owns_public_path() -> None:
    upload_intents = importlib.import_module("backend.web.routes.learning_upload_intents")

    paths = {getattr(route, "path", "") for route in upload_intents.learning_upload_intents_router.routes}

    assert "/api/learning/courses/{course_id}/tasks/{task_id}/upload-intents" in paths
