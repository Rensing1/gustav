"""
Contract test (schema): H5P access-check should stay performant.

Why:
    `DBLearningRepo.is_h5p_content_released_for_student` filters by
    `unit_tasks.kind='h5p'` and `unit_tasks.h5p_content_id = <id>`.
    A partial index on H5P rows keeps this check fast as the number of tasks
    grows.

This test is intentionally lightweight:
    - If a real DB is available, it asserts the index exists.
    - Otherwise, it asserts the migration contains the index DDL (single source
      of truth).
"""

from __future__ import annotations

import os
from pathlib import Path


import pytest


pytestmark = pytest.mark.db_write


def test_h5p_access_check_index_exists_or_is_migrated():
    root = Path(__file__).resolve().parents[2]
    migration = root / "supabase" / "migrations" / "20260112121000_learning_h5p_access_check_index.sql"

    # Prefer a live assertion when a service DSN is available.
    dsn = os.getenv("SERVICE_ROLE_DSN") or os.getenv("RLS_TEST_SERVICE_DSN")
    try:
        import psycopg  # type: ignore
    except Exception:
        psycopg = None  # type: ignore

    if dsn and psycopg is not None:
        with psycopg.connect(dsn, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select exists (
                             select 1
                               from pg_indexes
                              where schemaname = 'public'
                                and tablename = 'unit_tasks'
                                and indexname = 'idx_unit_tasks_h5p_content_id'
                           )
                    """
                )
                assert bool((cur.fetchone() or [False])[0]) is True
        return

    # Static fallback: validate the migration defines the index.
    sql = migration.read_text(encoding="utf-8")
    low = sql.lower()
    assert "create index" in low
    assert "idx_unit_tasks_h5p_content_id" in sql
    assert "unit_tasks" in low
    assert "where" in low and "kind" in low and "h5p" in low
