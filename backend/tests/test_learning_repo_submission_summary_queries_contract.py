"""Contracts for keeping Learning task-submission summaries outside repo_db."""

from __future__ import annotations

import importlib
from pathlib import Path
from uuid import uuid4

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPO_SOURCE = PROJECT_ROOT / "backend" / "learning" / "repo_db.py"
QUERY_SOURCE = PROJECT_ROOT / "backend" / "learning" / "repo_submission_summary_queries.py"


def test_submission_summary_query_lives_outside_learning_repo_hotspot() -> None:
    repo_db = importlib.import_module("backend.learning.repo_db")
    query_module = importlib.import_module("backend.learning.repo_submission_summary_queries")
    repo_source = REPO_SOURCE.read_text(encoding="utf-8")
    query_source = QUERY_SOURCE.read_text(encoding="utf-8")

    assert "with latest as (" not in repo_source
    assert "def task_submission_summary_map(" in query_source
    assert repo_db._repo_submission_summary_queries is query_module


def test_submission_summary_separates_h5p_completion_from_latest_score() -> None:
    query_module = importlib.import_module("backend.learning.repo_submission_summary_queries")
    task_id = str(uuid4())

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def execute(self, query, params):
            self.query = query
            self.params = params

        def fetchall(self):
            return [
                (
                    task_id,
                    "h5p",
                    "submit",
                    "completed",
                    0,
                    1,
                    "2026-09-24T08:02:00+00:00",
                    "2026-09-24T08:02:00+00:00",
                    True,
                )
            ]

    class Connection:
        def __init__(self):
            self.cursor_instance = Cursor()

        def cursor(self):
            return self.cursor_instance

    connection = Connection()
    summary = query_module.task_submission_summary_map(
        connection,
        student_sub="student-1",
        course_id=str(uuid4()),
        task_ids=[task_id],
        set_current_sub=lambda *_args: None,
        set_current_course_id=lambda *_args: None,
    )

    assert summary[task_id]["h5p_completed"] is True
    assert summary[task_id]["score_raw"] == 0
    assert summary[task_id]["score_max"] == 1
    assert "bool_or(score_raw = score_max)" in connection.cursor_instance.query
