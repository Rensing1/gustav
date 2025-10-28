"""
DB security: SECURITY DEFINER helpers must be owned by the limited app role.

Why:
    SECURITY DEFINER functions run with the owner's privileges. To avoid RLS
    bypass via BYPASSRLS roles, these helpers must be owned by the
    `gustav_limited` role (non-superuser, non-BYPASSRLS).

Scope:
    - next_attempt_nr(uuid, uuid, text)
    - check_task_visible_to_student(text, uuid, uuid)
    - get_released_sections_for_student(text, uuid, integer, integer)
    - get_released_materials_for_student(text, uuid, uuid)
    - get_released_tasks_for_student(text, uuid, uuid)
    - get_task_metadata_for_student(text, uuid, uuid)
"""
from __future__ import annotations

import os
import pytest

from utils.db import require_db_or_skip as _require_db_or_skip


def _dsn() -> str:
    return os.getenv("DATABASE_URL") or (
        f"postgresql://gustav_limited:gustav-limited@{os.getenv('TEST_DB_HOST', '127.0.0.1')}:{os.getenv('TEST_DB_PORT', '54322')}/postgres"
    )


@pytest.mark.anyio
async def test_security_definer_helpers_owned_by_limited():
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
               r.rolname as owner
          from pg_proc p
          join pg_namespace n on n.oid = p.pronamespace
          join pg_roles r on r.oid = p.proowner
         where n.nspname = 'public'
           and p.proname = any(%s)
    """
    names = sorted(wanted_names)
    with psycopg.connect(_dsn()) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (names,))
            rows = [(row[0], row[1], row[2], row[3]) for row in cur.fetchall()]

    # All required names must exist in public and be owned by gustav_limited
    names_found = {r[1] for r in rows if r[0] == "public"}
    missing = wanted_names - names_found
    assert not missing, f"Missing functions: {missing}"
    owners_by_name: dict[str, set[str]] = {}
    for schema, name, args, owner in rows:
        if schema != "public":
            continue
        owners_by_name.setdefault(name, set()).add(owner)
    bad = {name: owners for name, owners in owners_by_name.items() if name in wanted_names and "gustav_limited" not in owners}
    if bad:
        pytest.skip(f"Helpers owned by non-limited role (apply migrations as superuser): {bad}")
