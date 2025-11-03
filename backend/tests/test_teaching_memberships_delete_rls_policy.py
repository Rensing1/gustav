"""
DB RLS — Owner can delete course memberships under limited role.

Why:
    We observed that removing a student from a course via the UI appeared to
    succeed but the member reappeared after reload. This test pins the intended
    behavior at the DB boundary: with Row Level Security enforced (limited
    role, no service-role fallback), the course owner must be allowed to delete
    a membership.

Approach:
    - Instantiate the Postgres-backed repo with the default limited DSN.
    - Ensure service-role fallback is disabled via env (monkeypatch).
    - Create a course as owner, add a membership, then remove it as owner.
    - Verify via the SECURITY DEFINER helper (owner-scoped list) that the
      membership is gone.

Skips automatically when no DB is reachable (local dev convenience).
"""
from __future__ import annotations

import os
import pytest

from backend.tests.utils.db import require_db_or_skip as _require_db_or_skip  # type: ignore


def test_owner_can_delete_membership_under_rls(monkeypatch: pytest.MonkeyPatch) -> None:
    _require_db_or_skip()

    # Disable any service-role fallback so we truly test RLS path
    monkeypatch.delenv("RLS_TEST_SERVICE_DSN", raising=False)
    monkeypatch.delenv("SERVICE_ROLE_DSN", raising=False)
    monkeypatch.delenv("SESSION_TEST_DSN", raising=False)
    monkeypatch.delenv("SESSION_DATABASE_URL", raising=False)

    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore
    except Exception:
        pytest.skip("DBTeachingRepo unavailable (psycopg missing)")

    repo = DBTeachingRepo()
    owner = "teacher-rls-delete-owner"
    student = "student-rls-delete-me"

    # Arrange: create course and add membership as owner (limited role path)
    course = repo.create_course(title="RLS Delete", subject=None, grade_level=None, term=None, teacher_id=owner)
    created = repo.add_member_owned(course["id"], owner, student)
    assert created is True or created is False  # idempotent semantics allowed

    # Act: delete as owner under RLS
    repo.remove_member_owned(course["id"], owner, student)

    # Assert: Verify via helper-backed list that student is not present
    roster = repo.list_members_for_owner(course["id"], owner, limit=50, offset=0)
    subs = [sid for sid, _ in roster]
    assert student not in subs

