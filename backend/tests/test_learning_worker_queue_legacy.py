"""
Learning worker queue regression tests.

Why:
    We must retire the legacy table `learning_submission_ocr_jobs`. Until that happens,
    `_resolve_queue_table` may silently fall back to the legacy table which the worker
    cannot update/delete safely. These tests drive the refactor by demanding (a) a hard
    failure when only the legacy table exists and (b) a migration that drops the table.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pytest

from backend.learning.workers import process_learning_submission_jobs as worker


class _RegclassCursor:
    """Minimal cursor stub that emulates `select to_regclass(...)` calls."""

    def __init__(self, existing: Iterable[str]):
        self._existing = set(existing)
        self._last_lookup: str | None = None

    def __enter__(self) -> "_RegclassCursor":  # pragma: no cover - trivial
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # pragma: no cover - trivial
        return None

    def execute(self, query: str, params: object | None = None) -> None:
        # Supports both parametrized and literal `to_regclass` queries.
        if params:
            self._last_lookup = str(params[0]).split(".")[-1]
            return
        lower = query.lower()
        if "learning_submission_jobs" in lower:
            self._last_lookup = "learning_submission_jobs"
        elif "learning_submission_ocr_jobs" in lower:
            self._last_lookup = "learning_submission_ocr_jobs"
        else:  # pragma: no cover - unexpected query shape
            raise AssertionError(f"Unsupported query: {query}")

    def fetchone(self):
        if self._last_lookup in self._existing:
            # Simulate tuple row `(regclass,)`
            return (f"public.{self._last_lookup}",)
        return (None,)


class _RegclassConnection:
    """psycopg-compatible connection stub producing `_RegclassCursor` objects."""

    def __init__(self, existing: Iterable[str]):
        self._existing = existing

    def cursor(self):
        return _RegclassCursor(self._existing)


def test_resolve_queue_table_rejects_legacy_only():
    """Only the modern queue table is supported; legacy fallback must explode."""

    conn = _RegclassConnection(existing={"learning_submission_ocr_jobs"})

    with pytest.raises(RuntimeError):
        worker._resolve_queue_table(conn)  # type: ignore[arg-type]


def test_supabase_migrations_drop_legacy_queue():
    """Supabase migrations must explicitly drop `learning_submission_ocr_jobs`."""

    repo_root = Path(__file__).resolve().parents[2]
    migrations_dir = repo_root / "supabase" / "migrations"
    drop_snippet = "drop table if exists public.learning_submission_ocr_jobs"
    snippets = [
        drop_snippet in path.read_text()
        for path in migrations_dir.glob("*.sql")
    ]

    assert any(snippets), "Missing migration that removes learning_submission_ocr_jobs"
