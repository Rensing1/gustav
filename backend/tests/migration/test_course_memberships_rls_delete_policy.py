"""
RLS policy — owners can delete memberships; others cannot.

Why:
    Ensure the row-level security delete policy `memberships_delete_owner_only`
    allows the course owner (via app.current_sub) to delete a membership and
    prevents other teachers from deleting it.
"""
from __future__ import annotations

import pytest

from backend.tests.utils.db import require_db_or_skip as _require_db_or_skip


def _dsn_from_repo(repo) -> str:
    """Return the limited-role DSN from the repo and assert RLS membership."""
    dsn = getattr(repo, "_dsn")
    try:
        import psycopg  # type: ignore

        with psycopg.connect(dsn) as conn:  # type: ignore[arg-type]
            with conn.cursor() as cur:
                cur.execute("select pg_has_role(current_user, 'gustav_limited', 'member')")
                has_rls_role = bool((cur.fetchone() or [False])[0])
        if not has_rls_role:
            pytest.skip("Database URL is not limited-role (gustav_limited member) — unsafe for RLS test")
    except Exception:
        # If verification fails we skip to avoid running with a permissive role.
        pytest.skip("Unable to verify limited-role DSN for RLS test")
    return dsn


@pytest.mark.anyio
async def test_rls_delete_policy_owner_can_delete_non_owner_cannot() -> None:
    _require_db_or_skip()
    try:
        import psycopg  # type: ignore
    except Exception:
        pytest.skip("psycopg not available")

    # Use the teaching repo to prepare data
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore
    except Exception:
        pytest.skip("DBTeachingRepo unavailable")

    repo = DBTeachingRepo()
    owner = "teacher-rls-owner"
    attacker = "teacher-rls-attacker"
    student = "student-rls-target"

    course = repo.create_course(title="RLSDelete", subject=None, grade_level=None, term=None, teacher_id=owner)
    repo.add_member_owned(course["id"], owner, student)

    dsn = _dsn_from_repo(repo)
    # Owner session: delete must succeed under RLS
    with psycopg.connect(dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (owner,))
            cur.execute(
                "delete from public.course_memberships where course_id = %s and student_id = %s",
                (course["id"], student),
            )
        conn.commit()
    roster_after_owner = repo.list_members_for_owner(course["id"], owner, limit=50, offset=0)
    assert all(sid != student for sid, _ in roster_after_owner)

    # Re-add and attempt delete as attacker — must fail (row remains)
    repo.add_member_owned(course["id"], owner, student)
    with psycopg.connect(dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (attacker,))
            cur.execute(
                "delete from public.course_memberships where course_id = %s and student_id = %s",
                (course["id"], student),
            )
        conn.commit()
    roster_after_attacker = repo.list_members_for_owner(course["id"], owner, limit=50, offset=0)
    assert any(sid == student for sid, _ in roster_after_attacker)
