"""
DB-level constraints for section visibility releases.

Validates that:
- CHECK constraint enforces (visible=true -> released_at NOT NULL) and
  (visible=false -> released_at IS NULL).
- Schema enforces NOT NULL for released_by.

Skips automatically when a Postgres DSN is not reachable.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest


pytestmark = pytest.mark.anyio("asyncio")


def _pick_dsn() -> str:
    user = os.getenv("APP_DB_USER", "gustav_app")
    password = os.getenv("APP_DB_PASSWORD", "CHANGE_ME_DEV")
    return (
        os.getenv("RLS_TEST_DSN")
        or os.getenv("TEACHING_DATABASE_URL")
        or os.getenv("DATABASE_URL")
        or f"postgresql://{user}:{password}@{os.getenv('TEST_DB_HOST', '127.0.0.1')}:{os.getenv('TEST_DB_PORT', '54322')}/postgres"
    )


def _require_db_or_skip() -> None:
    try:
        import psycopg  # type: ignore
    except Exception:
        pytest.skip("psycopg not available")
    dsn = _pick_dsn()
    try:
        with psycopg.connect(dsn, connect_timeout=1):
            return
    except Exception:
        pytest.skip("Database not reachable for DB constraint tests")


@pytest.mark.anyio
async def test_module_section_releases_check_constraint_and_not_null():
    _require_db_or_skip()

    # Use the repo to arrange valid course/module/section under RLS constraints
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore
    except Exception:
        pytest.skip("DB repo unavailable")

    repo = DBTeachingRepo()
    owner = "teacher-visibility-db-constraints"
    course = repo.create_course(title="C", subject=None, grade_level=None, term=None, teacher_id=owner)
    unit = repo.create_unit(title="U", summary=None, author_id=owner)
    section = repo.create_section(unit_id=unit["id"], title="S", author_id=owner)
    module = repo.create_course_module_owned(course["id"], owner, unit_id=unit["id"], context_notes=None)

    import psycopg  # type: ignore

    dsn = _pick_dsn()
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            # Ensure RLS context is set for the owner
            cur.execute("select set_config('app.current_sub', %s, true)", (owner,))

            # 1) visible=true but released_at is NULL -> CHECK violation (23514)
            with pytest.raises(Exception) as e1:
                cur.execute(
                    """
                    insert into public.module_section_releases (course_module_id, section_id, visible, released_at, released_by)
                    values (%s, %s, true, null, %s)
                    """,
                    (module["id"], section["id"], owner),
                )
            assert getattr(e1.value, "sqlstate", None) == "23514"
            # Reset transaction state after error
            conn.rollback()

            # 2) visible=false but released_at is set -> CHECK violation (23514)
            with pytest.raises(Exception) as e2:
                cur.execute(
                    """
                    insert into public.module_section_releases (course_module_id, section_id, visible, released_at, released_by)
                    values (%s, %s, false, now(), %s)
                    """,
                    (module["id"], section["id"], owner),
                )
            assert getattr(e2.value, "sqlstate", None) in {"23514", "42501"}
            conn.rollback()

            # 3) Schema enforces NOT NULL for released_by
            cur.execute(
                """
                select is_nullable
                from information_schema.columns
                where table_schema='public'
                  and table_name='module_section_releases'
                  and column_name='released_by'
                """
            )
            row = cur.fetchone()
            assert row and row[0] == "NO"
