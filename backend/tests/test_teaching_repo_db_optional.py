"""
Optional DB test for Teaching repository (skips when DB is unreachable).

Applies only when a Postgres database is reachable via DATABASE_URL.
Requires that migrations have been applied (e.g., `supabase migration up`).
"""
from __future__ import annotations

import os
import pytest


def _fallback_login_dsn() -> str:
    host = os.getenv("TEST_DB_HOST", "127.0.0.1")
    port = os.getenv("TEST_DB_PORT", "54322")
    user = os.getenv("APP_DB_USER", "gustav_app")
    password = os.getenv("APP_DB_PASSWORD", "CHANGE_ME_DEV")
    return f"postgresql://{user}:{password}@{host}:{port}/postgres"


def _probe_dsn(dsn: str) -> bool:
    try:
        import psycopg  # type: ignore
        with psycopg.connect(dsn, connect_timeout=1) as _:
            return True
    except Exception:
        return False


@pytest.mark.anyio
async def test_db_repo_create_and_list_courses_when_db_available():
    dsn = os.getenv("DATABASE_URL") or _fallback_login_dsn()
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
    dsn = os.getenv("DATABASE_URL") or _fallback_login_dsn()
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
    dsn = os.getenv("DATABASE_URL") or _fallback_login_dsn()
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


def test_create_section_retry_fetches_row_after_unique_violation(monkeypatch: pytest.MonkeyPatch):
    """Ensure create_section returns the inserted row when retrying after 23505."""
    from teaching import repo_db  # type: ignore

    if not getattr(repo_db, "HAVE_PSYCOPG", False):
        pytest.skip("psycopg not available")

    class FakeUniqueViolation(Exception):
        sqlstate = "23505"
        pgcode = "23505"

    unit_id = "00000000-0000-0000-0000-000000000001"
    expected_id = "00000000-0000-0000-0000-000000000099"
    state = {
        "first_insert": True,
        "insert_attempts": 0,
        "rolled_back": False,
        "committed": False,
        "unit_id": unit_id,
        "title": None,
        "expected_id": expected_id,
        "unique_exc": FakeUniqueViolation("duplicate"),
    }

    class FakeCursor:
        def __init__(self, shared_state):
            self._state = shared_state
            self._last = None
            self._closed = False

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            self._closed = True
            return False

        def execute(self, query, params=None):
            normalized = " ".join(query.split()).lower()
            if "set_config" in normalized:
                return
            if "select id from public.units" in normalized:
                return
            if "select id from public.unit_sections where unit_id" in normalized:
                return
            if "select coalesce(max(position)" in normalized:
                self._last = "select_next"
                return
            if "insert into public.unit_sections" in normalized:
                self._state["insert_attempts"] += 1
                # Track title/position from payload
                if params:
                    self._state["title"] = params[1]
                if self._state["first_insert"]:
                    self._state["first_insert"] = False
                    self._last = None
                    raise self._state["unique_exc"]
                self._last = "insert_returning"
                return
            raise AssertionError(f"Unexpected query: {query}")

        def fetchone(self):
            if self._closed:
                raise repo_db.psycopg.InterfaceError("cursor already closed")  # type: ignore[attr-defined]
            if self._last == "select_next":
                return (1,)
            if self._last == "insert_returning":
                return (
                    self._state["expected_id"],
                    self._state["unit_id"],
                    self._state["title"],
                    1,
                    "2025-01-01T00:00:00+00:00",
                    "2025-01-01T00:00:00+00:00",
                )
            return None

    class FakeConn:
        def __init__(self, shared_state):
            self._state = shared_state

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def cursor(self):
            return FakeCursor(self._state)

        def rollback(self):
            self._state["rolled_back"] = True

        def commit(self):
            self._state["committed"] = True

    def fake_connect(_dsn):
        return FakeConn(state)

    monkeypatch.setattr(repo_db, "UniqueViolation", FakeUniqueViolation)
    monkeypatch.setattr(repo_db.psycopg, "connect", fake_connect)

    repo = repo_db.DBTeachingRepo(dsn="postgresql://gustav_limited:any@localhost/postgres")
    section = repo.create_section(unit_id=unit_id, title=" Retry ", author_id="teacher-sec-retry")

    assert state["insert_attempts"] == 2
    assert state["rolled_back"] is True
    assert state["committed"] is True
    assert section["id"] == expected_id
    assert section["title"] == "Retry"
    assert section["position"] == 1
