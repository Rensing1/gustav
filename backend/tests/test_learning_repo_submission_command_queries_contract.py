"""Contracts for keeping Learning submission commands outside repo_db."""

from __future__ import annotations

import importlib
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPO_SOURCE = PROJECT_ROOT / "backend" / "learning" / "repo_db.py"
COMMAND_SOURCE = PROJECT_ROOT / "backend" / "learning" / "repo_submission_command_queries.py"


def test_submission_command_implementations_live_outside_learning_repo_hotspot() -> None:
    repo_db = importlib.import_module("backend.learning.repo_db")
    command_module = importlib.import_module("backend.learning.repo_submission_command_queries")
    repo_source = REPO_SOURCE.read_text(encoding="utf-8")
    command_source = COMMAND_SOURCE.read_text(encoding="utf-8")

    assert "def create_submission(repo, " in command_source
    assert "def finalize_latest_feedback_submission(" in command_source
    assert "repo," in command_source
    assert "def find_matching_inflight_feedback_submission(" in command_source
    assert "def create_submission(self, data: SubmissionInput)" in repo_source
    assert "def finalize_latest_feedback_submission(" in repo_source
    assert "repo_submission_command_queries.create_submission(" in repo_source
    assert "repo_submission_command_queries.finalize_latest_feedback_submission(" in repo_source
    assert "insert into public.learning_submissions" not in repo_source
    assert "insert into public.learning_submission_jobs" not in repo_source
    assert "public.next_attempt_nr" not in repo_source
    assert repo_db._repo_submission_command_queries is command_module
