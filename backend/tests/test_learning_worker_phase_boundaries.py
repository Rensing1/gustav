"""Worker SQL belongs to adapters; orchestration retains transaction ownership."""

import ast
import inspect

from backend.learning.workers import process_learning_submission_jobs as worker


def test_worker_database_operations_have_one_owner_outside_orchestration():
    for name in (
        "_fetch_submission", "_fetch_task_context", "_set_current_sub",
        "_persist_ai_usage_events", "_update_submission_completed",
        "_persist_cached_vision", "_unlease_job", "_mark_retry_metadata",
        "_mark_job_failed", "_update_submission_failed", "_delete_job",
    ):
        function = getattr(worker, name)
        assert function.__module__ == "backend.learning.workers.submission_job_persistence"
        tree = ast.parse(inspect.getsource(function))
        assert not any(
            isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr in {"commit", "rollback", "connect"}
            for node in ast.walk(tree)
        ), "Only the orchestration may open connections or close transaction phases"


def test_worker_persistence_never_imports_or_calls_ai_adapters():
    from backend.learning.workers import submission_job_persistence as persistence

    source = inspect.getsource(persistence)
    tree = ast.parse(source)
    imports = [
        node.module or "" if isinstance(node, ast.ImportFrom) else alias.name
        for node in ast.walk(tree) if isinstance(node, (ast.ImportFrom, ast.Import))
        for alias in node.names
    ]
    assert not any(
        token in module for module in imports
        for token in ("process_learning_submission_jobs", "fastapi", "dspy")
    )
    assert not any(
        isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"analyze", "analyze_dialog", "extract"}
        for node in ast.walk(tree)
    )
