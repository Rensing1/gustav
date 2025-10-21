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
    host = os.getenv("TEST_DB_HOST", "127.0.0.1")
    port = os.getenv("TEST_DB_PORT", "54322")
    dsn = os.getenv("DATABASE_URL") or f"postgresql://gustav_limited:gustav-limited@{host}:{port}/postgres"
    if not _probe_dsn(dsn):
        pytest.skip("Database not reachable; apply migrations and expose limited DSN")

    from teaching.repo_db import DBTeachingRepo  # type: ignore

    repo = DBTeachingRepo(dsn=dsn)
    # Create
    c = repo.create_course(title="Chemie EF", subject="Chemie", grade_level="EF", term="2025-1", teacher_id="teacher-db-1")
    assert c["title"] == "Chemie EF"
    assert c["teacher_id"] == "teacher-db-1"

    # List for teacher
    arr = repo.list_courses_for_teacher(teacher_id="teacher-db-1", limit=10, offset=0)
    assert any(x["id"] == c["id"] for x in arr)


def test_db_repo_memberships_enforce_owner_rls():
    host = os.getenv("TEST_DB_HOST", "127.0.0.1")
    port = os.getenv("TEST_DB_PORT", "54322")
    dsn = os.getenv("DATABASE_URL") or f"postgresql://gustav_limited:gustav-limited@{host}:{port}/postgres"
    if not _probe_dsn(dsn):
        pytest.skip("Database not reachable; apply migrations and expose limited DSN")

    from teaching.repo_db import DBTeachingRepo  # type: ignore

    repo = DBTeachingRepo(dsn=dsn)
    course = repo.create_course(
        title="Geschichte EF",
        subject="Geschichte",
        grade_level="EF",
        term="2025-2",
        teacher_id="teacher-owner",
    )
    # Owner adds a member via owner-scoped helper
    added = repo.add_member_owned(course_id=course["id"], owner_sub="teacher-owner", student_id="student-secret")
    assert added is True

    # Non-owner teacher must not see the member — RLS should hide the row completely
    leaked = repo.list_members_for_owner(course_id=course["id"], owner_sub="teacher-other", limit=10, offset=0)
    assert leaked == []

    # Owner still sees the membership
    visible = repo.list_members_for_owner(course_id=course["id"], owner_sub="teacher-owner", limit=10, offset=0)
    subs = [sid for sid, _joined in visible]
    assert "student-secret" in subs


def test_course_memberships_insert_blocked_for_non_owner():
    host = os.getenv("TEST_DB_HOST", "127.0.0.1")
    port = os.getenv("TEST_DB_PORT", "54322")
    dsn = os.getenv("DATABASE_URL") or f"postgresql://gustav_limited:gustav-limited@{host}:{port}/postgres"
    if not _probe_dsn(dsn):
        pytest.skip("Database not reachable; apply migrations and expose limited DSN")

    import psycopg  # type: ignore
    from psycopg import errors  # type: ignore

    owner = "teacher-owner-insert"
    intruder = "teacher-intruder"

    from teaching.repo_db import DBTeachingRepo  # type: ignore

    repo = DBTeachingRepo(dsn=dsn)
    course = repo.create_course(
        title="Politik EF",
        subject=None,
        grade_level=None,
        term=None,
        teacher_id=owner,
    )

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, false)", (intruder,))
            with pytest.raises(errors.InsufficientPrivilege):
                cur.execute(
                    "insert into public.course_memberships (course_id, student_id) values (%s, %s)",
                    (course["id"], "student-hijack"),
                )
