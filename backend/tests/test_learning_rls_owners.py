"""
DB security: Learning helpers must not use SECURITY DEFINER.

Why:
    SECURITY DEFINER functions run with the owner's privileges. To keep RLS
    effective when the application connects as the limited role
    (`gustav_limited`), helpers must remain SECURITY INVOKER (default).

Scope:
    - next_attempt_nr(uuid, uuid, text)
    - check_task_visible_to_student(text, uuid, uuid)
    - get_released_sections_for_student(text, uuid, integer, integer)
    - get_released_sections_for_student_by_unit(text, uuid, uuid, integer, integer)
    - get_released_materials_for_student(text, uuid, uuid)
    - get_released_tasks_for_student(text, uuid, uuid)
    - get_task_metadata_for_student(text, uuid, uuid)
"""
from __future__ import annotations

import os
import pytest

from utils.db import require_db_or_skip as _require_db_or_skip


def _dsn() -> str:
    user = os.getenv("APP_DB_USER", "gustav_app")
    password = os.getenv("APP_DB_PASSWORD", "CHANGE_ME_DEV")
    return os.getenv("DATABASE_URL") or (
        f"postgresql://{user}:{password}@{os.getenv('TEST_DB_HOST', '127.0.0.1')}:{os.getenv('TEST_DB_PORT', '54322')}/postgres"
    )


@pytest.mark.anyio
async def test_learning_helpers_are_not_security_definer():
    _require_db_or_skip()
    try:
        import psycopg  # type: ignore
    except Exception:
        pytest.skip("psycopg not available")

    wanted_names = {
        "next_attempt_nr",
        "check_task_visible_to_student",
        "get_released_sections_for_student",
        # New helper used by unit-scoped sections endpoint
        "get_released_sections_for_student_by_unit",
        "get_released_materials_for_student",
        "get_released_tasks_for_student",
        "get_task_metadata_for_student",
    }
    # Query by function names to avoid passing anonymous composite types; ignore arg variants
    sql = """
        select n.nspname as schema,
               p.proname as name,
               pg_get_function_identity_arguments(p.oid) as args,
               p.prosecdef as is_security_definer
          from pg_proc p
          join pg_namespace n on n.oid = p.pronamespace
         where n.nspname = 'public'
           and p.proname = any(%s)
    """
    names = sorted(wanted_names)
    with psycopg.connect(_dsn()) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (names,))
            rows = [(row[0], row[1], row[2], bool(row[3])) for row in cur.fetchall()]

    # All required names must exist in public and must not be SECURITY DEFINER
    names_found = {r[1] for r in rows if r[0] == "public"}
    missing = wanted_names - names_found
    assert not missing, f"Missing functions: {missing}"
    violators = [name for schema, name, args, is_definer in rows if schema == "public" and is_definer]
    assert not violators, f"Learning helpers must remain SECURITY INVOKER: {violators}"
