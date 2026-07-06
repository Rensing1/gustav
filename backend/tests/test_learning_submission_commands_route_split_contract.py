"""Contracts for keeping Learning submission command routes outside the hotspot."""

from __future__ import annotations

import importlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_learning_submission_command_routes_live_in_focused_router_module() -> None:
    learning = importlib.import_module("backend.web.routes.learning")
    submission_commands = importlib.import_module("backend.web.routes.learning_submission_commands")

    assert learning.create_submission is submission_commands.create_submission
    assert learning.finalize_submission is submission_commands.finalize_submission


def test_learning_hotspot_no_longer_defines_submission_command_handlers() -> None:
    source = (REPO_ROOT / "backend" / "web" / "routes" / "learning.py").read_text(encoding="utf-8")

    assert "async def create_submission(" not in source
    assert "async def finalize_submission(" not in source


def test_learning_submission_command_router_owns_command_paths() -> None:
    submission_commands = importlib.import_module("backend.web.routes.learning_submission_commands")

    paths = {getattr(route, "path", "") for route in submission_commands.learning_submission_commands_router.routes}

    assert "/api/learning/courses/{course_id}/tasks/{task_id}/submissions" in paths
    assert "/api/learning/courses/{course_id}/tasks/{task_id}/submissions/finalize" in paths
