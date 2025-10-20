"""
Optional DB test for Teaching repository (skips when DB is unreachable).

Applies only when a Postgres database is reachable via DATABASE_URL.
Requires that migrations have been applied (e.g., `supabase migration up`).
"""
from __future__ import annotations

import os
import pytest


def _probe_dsn(dsn: str) -> bool:
    try:
        import psycopg  # type: ignore
        with psycopg.connect(dsn, connect_timeout=1) as _:
            return True
    except Exception:
        return False


@pytest.mark.anyio
async def test_db_repo_create_and_list_courses_when_db_available():
    dsn = os.getenv("DATABASE_URL") or ""
    if not dsn or not _probe_dsn(dsn):
        pytest.skip("Database not reachable; apply migrations and set DATABASE_URL to run this test")

    from teaching.repo_db import DBTeachingRepo  # type: ignore

    repo = DBTeachingRepo(dsn=dsn)
    # Create
    c = repo.create_course(title="Chemie EF", subject="Chemie", grade_level="EF", term="2025-1", teacher_id="teacher-db-1")
    assert c["title"] == "Chemie EF"
    assert c["teacher_id"] == "teacher-db-1"

    # List for teacher
    arr = repo.list_courses_for_teacher(teacher_id="teacher-db-1", limit=10, offset=0)
    assert any(x["id"] == c["id"] for x in arr)

