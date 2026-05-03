"""Regression tests for batch-scoped legacy migration reads."""

from __future__ import annotations

import pytest

from backend.tools import legacy_migration

pytestmark = pytest.mark.legacy_migration


class _Cursor:
    def __init__(self, *, has_batch_column: bool) -> None:
        self.has_batch_column = has_batch_column
        self.calls: list[tuple[str, tuple[object, ...]]] = []
        self._last_sql = ""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql: str, params: tuple[object, ...] | None = None) -> None:
        self._last_sql = str(sql)
        self.calls.append((self._last_sql, tuple(params or ())))

    def fetchone(self):
        if "information_schema.columns" in self._last_sql:
            return (1,) if self.has_batch_column else None
        return None

    def fetchall(self):
        if "from staging.courses" in self._last_sql:
            return [("00000000-0000-0000-0000-000000000001", "Scoped Course", "00000000-0000-0000-0000-000000000002")]
        return []


class _Conn:
    def __init__(self, *, has_batch_column: bool = True) -> None:
        self.cursor_obj = _Cursor(has_batch_column=has_batch_column)

    def cursor(self):
        return self.cursor_obj


def test_load_staging_courses_filters_by_import_batch_id() -> None:
    conn = _Conn()

    rows = legacy_migration._load_staging_courses(  # type: ignore[attr-defined]
        conn,
        batch_id="11111111-1111-1111-1111-111111111111",
    )

    assert len(rows) == 1
    select_sql, select_params = conn.cursor_obj.calls[-1]
    assert "from staging.courses where import_batch_id = %s::uuid" in select_sql
    assert select_params == ("11111111-1111-1111-1111-111111111111",)


def test_batch_id_requires_import_batch_id_column() -> None:
    conn = _Conn(has_batch_column=False)

    with pytest.raises(RuntimeError, match="import_batch_id"):
        legacy_migration._load_staging_courses(  # type: ignore[attr-defined]
            conn,
            batch_id="11111111-1111-1111-1111-111111111111",
        )
