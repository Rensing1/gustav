"""
Filius migration contract.

Intent:
    Schema migrations must allow Filius task kinds and FLS file submissions
    without adding Filius-specific columns.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path


def test_filius_unit_tasks_kind_migration_allows_filius() -> None:
    sql = Path("supabase/migrations/20260507115800_unit_tasks_kind_filius.sql").read_text(encoding="utf-8").lower()

    assert "unit_tasks_kind_check" in sql
    assert "'filius'" in sql
    assert "alter table public.unit_tasks" in sql


def test_filius_learning_submissions_migration_allows_fls_mime() -> None:
    sql = Path("supabase/migrations/20260507115900_learning_submissions_file_kind_filius_fls.sql").read_text(encoding="utf-8").lower()

    assert "learning_submissions_file_kind" in sql
    assert "application/x.filius.fls" in sql
    assert "alter table if exists public.learning_submissions" in sql


def test_filius_migration_names_use_valid_supabase_timestamps() -> None:
    """Filius migrations must use real YYYYMMDDHHMMSS prefixes."""
    paths = sorted(Path("supabase/migrations").glob("*filius*.sql"))
    assert paths, "Expected Filius migration files"

    for path in paths:
        prefix = path.name.split("_", maxsplit=1)[0]
        datetime.strptime(prefix, "%Y%m%d%H%M%S")
