"""
DB security — SECURITY DEFINER helper must bind owner to session, not parameter.

Why:
    The function `public.remove_course_membership(owner, course, student)` must
    not authorize based on the passed `owner` argument. Instead, it must rely on
    `app.current_sub` to ensure the caller actually owns the course. This test
    asserts that a mismatched session owner cannot delete, while a matching
    session owner can delete regardless of the `owner` argument value.
"""
from __future__ import annotations

import os
import pytest

from backend.tests.utils.db import require_db_or_skip as _require_db_or_skip


def _dsn() -> str:
    host = os.getenv("TEST_DB_HOST", "127.0.0.1")
    port = os.getenv("TEST_DB_PORT", "54322")
    user = os.getenv("APP_DB_USER", "gustav_app")
    password = os.getenv("APP_DB_PASSWORD", "CHANGE_ME_DEV")
    return os.getenv("DATABASE_URL") or f"postgresql://{user}:{password}@{host}:{port}/postgres"


@pytest.mark.anyio
async def test_remove_course_membership_binds_to_session_owner() -> None:
    _require_db_or_skip()
    try:
        import psycopg  # type: ignore
    except Exception:
        pytest.skip("psycopg not available")

    # Use the teaching repo to prepare data quickly
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore
    except Exception:
        pytest.skip("DBTeachingRepo unavailable")

    repo = DBTeachingRepo()
    real_owner = "teacher-own-binding"
    attacker = "teacher-attacker-binding"
    student = "student-binding-target"

    course = repo.create_course(title="BindOwner", subject=None, grade_level=None, term=None, teacher_id=real_owner)
    repo.add_member_owned(course["id"], real_owner, student)

    dsn = _dsn()
    # Case 1: Session is attacker; passing real_owner as arg must NOT delete
    with psycopg.connect(dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (attacker,))
            cur.execute(
                "select public.remove_course_membership(%s, %s::uuid, %s)",
                (real_owner, course["id"], student),
            )
        conn.commit()
    roster_still = repo.list_members_for_owner(course["id"], real_owner, limit=50, offset=0)
    assert any(sid == student for sid, _ in roster_still)

    # Case 2: Session is real_owner; passing attacker as arg MUST delete
    with psycopg.connect(dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (real_owner,))
            cur.execute(
                "select public.remove_course_membership(%s, %s::uuid, %s)",
                (attacker, course["id"], student),
            )
        conn.commit()
    roster_after = repo.list_members_for_owner(course["id"], real_owner, limit=50, offset=0)
    assert all(sid != student for sid, _ in roster_after)
