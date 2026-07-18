"""Contracts for Teaching DB live-query helper ownership."""

from __future__ import annotations

import importlib
from pathlib import Path
from types import SimpleNamespace

import psycopg
import pytest

from backend.teaching.errors import TeachingRepositoryUnavailable


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPO_SOURCE = PROJECT_ROOT / "backend" / "teaching" / "repo_db.py"
LIVE_QUERIES_SOURCE = PROJECT_ROOT / "backend" / "teaching" / "repo_live_queries.py"

LIVE_QUERY_METHODS = (
    "list_unit_latest_submission_aggregates_for_owner",
    "list_unit_live_helper_rows",
    "list_unit_live_submission_state_by_task",
    "list_unit_live_average_scores_by_submission_id",
    "list_unit_live_summary_fallback_rows",
    "list_unit_live_task_ids_for_student",
    "list_unit_live_latest_changed_at_by_pairs",
    "list_unit_live_delta_fallback_rows",
    "get_statement_timestamp",
    "get_latest_submission_for_owner",
    "get_latest_submission_file_for_owner",
)


def test_live_query_implementations_live_outside_repo_hotspot() -> None:
    """Live dashboard SQL should live in a focused module, not in DBTeachingRepo."""

    repo_db = importlib.import_module("backend.teaching.repo_db")
    live_queries = importlib.import_module("backend.teaching.repo_live_queries")
    repo_source = REPO_SOURCE.read_text(encoding="utf-8")
    live_source = LIVE_QUERIES_SOURCE.read_text(encoding="utf-8")

    assert hasattr(repo_db, "_repo_live_queries")
    assert repo_db._repo_live_queries is live_queries

    for method_name in LIVE_QUERY_METHODS:
        assert f"def {method_name}(" in repo_source
        assert f"repo_live_queries.{method_name}(" in repo_source
        assert f"def {method_name}(" in live_source

    assert "from public.get_unit_latest_submission_aggregates_for_owner(" not in repo_source
    assert "from public.get_unit_latest_submissions_for_owner(" not in repo_source
    assert "list_unit_live_delta_fallback_rows" in live_source


class _LatestSubmissionCursor:
    """Record SQL and fail only at the required latest-submission helper."""

    def __init__(self, helper_error: Exception) -> None:
        self.helper_error = helper_error
        self.queries: list[str] = []
        self.last_query = ""

    def execute(self, sql: str, _params=None) -> None:
        self.last_query = " ".join(str(sql).split()).lower()
        self.queries.append(self.last_query)
        if "from public.get_latest_submission_for_owner(" in self.last_query:
            raise self.helper_error

    def fetchone(self):
        if "from public.unit_tasks" in self.last_query:
            return ("native", "Read the task", None)
        if "select exists(" in self.last_query:
            return (True,)
        return None

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _tb):
        return False


class _LatestSubmissionConnection:
    def __init__(self, cursor: _LatestSubmissionCursor) -> None:
        self._cursor = cursor

    def cursor(self) -> _LatestSubmissionCursor:
        return self._cursor

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _tb):
        return False


def _psycopg_failing_at_latest_helper(helper_error: Exception):
    cursor = _LatestSubmissionCursor(helper_error)
    connection = _LatestSubmissionConnection(cursor)
    module = SimpleNamespace(
        connect=lambda _dsn: connection,
        errors=psycopg.errors,
    )
    return module, cursor


def _get_latest_submission(live_queries, psycopg_module):
    return live_queries.get_latest_submission_for_owner(
        dsn="postgresql://limited-role.invalid/postgres",
        psycopg_module=psycopg_module,
        owner_sub="teacher-sub",
        course_id="00000000-0000-0000-0000-000000000001",
        unit_id="00000000-0000-0000-0000-000000000002",
        task_id="00000000-0000-0000-0000-000000000003",
        student_sub="student-sub",
    )


def _get_latest_submission_file(live_queries, psycopg_module):
    return live_queries.get_latest_submission_file_for_owner(
        dsn="postgresql://limited-role.invalid/postgres",
        psycopg_module=psycopg_module,
        owner_sub="teacher-sub",
        course_id="00000000-0000-0000-0000-000000000001",
        unit_id="00000000-0000-0000-0000-000000000002",
        task_id="00000000-0000-0000-0000-000000000003",
        student_sub="student-sub",
    )


def test_missing_latest_submission_helper_is_repository_unavailable() -> None:
    """A missing migration must not trigger a weaker direct table read."""

    live_queries = importlib.import_module("backend.teaching.repo_live_queries")
    psycopg_module, cursor = _psycopg_failing_at_latest_helper(
        psycopg.errors.UndefinedFunction("required helper is missing")
    )

    with pytest.raises(TeachingRepositoryUnavailable):
        _get_latest_submission(live_queries, psycopg_module)

    assert not any("from public.learning_submissions" in query for query in cursor.queries)


def test_missing_latest_submission_file_helper_is_repository_unavailable() -> None:
    """The file projection uses the same required schema helper as the detail."""

    live_queries = importlib.import_module("backend.teaching.repo_live_queries")
    psycopg_module, _cursor = _psycopg_failing_at_latest_helper(
        psycopg.errors.UndefinedFunction("required helper is missing")
    )

    with pytest.raises(TeachingRepositoryUnavailable):
        _get_latest_submission_file(live_queries, psycopg_module)


def test_unexpected_latest_submission_helper_error_propagates() -> None:
    """Unexpected defects must reach the web adapter's private 500 mapping."""

    live_queries = importlib.import_module("backend.teaching.repo_live_queries")
    psycopg_module, cursor = _psycopg_failing_at_latest_helper(
        ValueError("unexpected row mapping failure")
    )

    with pytest.raises(ValueError, match="unexpected row mapping failure"):
        _get_latest_submission(live_queries, psycopg_module)

    assert not any("from public.learning_submissions" in query for query in cursor.queries)
