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

