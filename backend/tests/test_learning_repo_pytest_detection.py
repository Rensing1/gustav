"""
Regression test: Learning repo pytest detection must work without env flags.

Why:
    Some guards in the Learning repository use `_running_under_pytest()` to
    avoid side effects during pytest (including collection). We should not rely
    solely on `PYTEST_CURRENT_TEST`, because that env var is not guaranteed in
    all phases.
"""

from __future__ import annotations

import pytest


def test_learning_repo_running_under_pytest_true_without_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)

    from backend.learning import repo_db

    assert repo_db._running_under_pytest() is True


def test_learning_repo_pytest_run_id_matches_db_isolation_helper(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GUSTAV_TEST_RUN_ID", raising=False)
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "backend/tests/test_example.py::test_case (call)")

    from backend.learning import repo_db
    from backend.tests.utils.db_isolation import current_test_run_id

    assert repo_db._pytest_test_run_id() == current_test_run_id()
