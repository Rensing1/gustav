"""
Filius migration contract.

Intent:
    Schema migrations must allow Filius task kinds and FLS file submissions
    without adding Filius-specific columns.
"""

from __future__ import annotations

from pathlib import Path


def test_filius_unit_tasks_kind_migration_allows_filius() -> None:
    sql = Path("supabase/migrations/20260507118000_unit_tasks_kind_filius.sql").read_text(encoding="utf-8").lower()

    assert "unit_tasks_kind_check" in sql
    assert "'filius'" in sql
    assert "alter table public.unit_tasks" in sql


def test_filius_learning_submissions_migration_allows_fls_mime() -> None:
    sql = Path("supabase/migrations/20260507119000_learning_submissions_file_kind_filius_fls.sql").read_text(encoding="utf-8").lower()

    assert "learning_submissions_file_kind" in sql
    assert "application/x.filius.fls" in sql
    assert "alter table if exists public.learning_submissions" in sql
