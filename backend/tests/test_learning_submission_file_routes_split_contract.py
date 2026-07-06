"""Contracts for keeping Learning submission file routes outside the hotspot."""

from __future__ import annotations

import importlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_submission_file_routes_and_helpers_live_in_focused_module() -> None:
    learning = importlib.import_module("backend.web.routes.learning")
    submission_files = importlib.import_module("backend.web.routes.learning_submission_files")

    assert learning._attach_submission_files is submission_files.attach_submission_files
    assert learning._submission_file_href is submission_files.submission_file_href
    assert learning._normalize_download_disposition is submission_files.normalize_download_disposition
    assert learning.list_submissions is submission_files.list_submissions
    assert learning.get_submission_file is submission_files.get_submission_file


def test_learning_hotspot_no_longer_defines_submission_file_routes_or_helpers() -> None:
    source = (REPO_ROOT / "backend" / "web" / "routes" / "learning.py").read_text(encoding="utf-8")

    assert "def _attach_submission_files(" not in source
    assert "def _submission_file_href(" not in source
    assert "def _normalize_download_disposition(" not in source
    assert "async def list_submissions(" not in source
    assert "async def get_submission_file(" not in source


def test_submission_file_router_owns_history_and_file_paths() -> None:
    submission_files = importlib.import_module("backend.web.routes.learning_submission_files")

    paths = {getattr(route, "path", "") for route in submission_files.learning_submission_files_router.routes}

    assert "/api/learning/courses/{course_id}/tasks/{task_id}/submissions" in paths
    assert "/api/learning/courses/{course_id}/tasks/{task_id}/submissions/{submission_id}/file" in paths
