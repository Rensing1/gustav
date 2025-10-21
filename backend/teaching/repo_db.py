"""
Postgres-backed repository for Teaching (courses & memberships).

Security:
- Access with a limited-role DSN so Row Level Security (RLS) guards every query.
- Service-role DSNs are reserved for migrations and session storage plumbing.

Design:
- Minimal psycopg3 usage; each call opens a short-lived connection.
- Returns plain dicts to keep the web adapter independent of ORM.
"""
from __future__ import annotations

from typing import List, Tuple, Optional
import os
import re
from urllib.parse import urlparse

try:
    import psycopg
    HAVE_PSYCOPG = True
except Exception:  # pragma: no cover - optional in some dev envs
    psycopg = None  # type: ignore
    HAVE_PSYCOPG = False


def _default_limited_dsn() -> str:
    host = os.getenv("TEST_DB_HOST", "127.0.0.1")
    port = os.getenv("TEST_DB_PORT", "54322")
    return f"postgresql://gustav_limited:gustav-limited@{host}:{port}/postgres"


def _dsn() -> str:
    """Resolve the DSN for DB access, always falling back to limited-role credentials."""
    candidates = [
        os.getenv("TEACHING_DATABASE_URL"),
        os.getenv("TEACHING_DB_URL"),
        os.getenv("RLS_TEST_DSN"),
        os.getenv("DATABASE_URL"),
        os.getenv("SUPABASE_DB_URL"),
        _default_limited_dsn(),
    ]
    for dsn in candidates:
        if dsn:
            return dsn
    raise RuntimeError("Database DSN unavailable for DBTeachingRepo")


def _iso(ts) -> str:
    # Expect timestamptz; convert to ISO string via SQL or fetch as text
    # We fetch via to_char at query time for predictability across drivers.
    return str(ts)

_UNSET = object()


class DBTeachingRepo:
    def __init__(self, dsn: Optional[str] = None) -> None:
        """Initialize a Postgres-backed repository with RLS-first safety.

        Why:
            Teaching endpoints must never bypass Row Level Security. We enforce
            that the configured DSN uses the limited application role by
            default. This prevents accidental usage of a service-role DSN which
            would silently disable RLS and undermine owner checks.

        Parameters:
            dsn: Optional explicit DSN. When omitted, resolves from env with a
                 safe fallback to the limited test DSN.

        Behavior:
            - Rejects DSNs whose username is not 'gustav_limited' unless
              ALLOW_SERVICE_DSN_FOR_TESTING=true is set (dev/testing only).
            - Does not open a connection eagerly; connections are per-call.
        """
        if not HAVE_PSYCOPG:
            raise RuntimeError("psycopg3 is required for DBTeachingRepo")
        self._dsn = dsn or _dsn()
        # Enforce limited-role DSN by default. Allow override explicitly for dev/tests.
        user = self._dsn_username(self._dsn)
        allow_override = str(os.getenv("ALLOW_SERVICE_DSN_FOR_TESTING", "")).lower() == "true"
        if user != "gustav_limited" and not allow_override:
            raise RuntimeError(
                "TeachingRepo requires limited-role DSN (gustav_limited). Set TEACHING_DATABASE_URL "
                "to a limited DSN or export ALLOW_SERVICE_DSN_FOR_TESTING=true to override in dev."
            )

    @staticmethod
    def _dsn_username(dsn: str) -> str:
        try:
            p = urlparse(dsn)
            if p.username:
                return p.username
        except Exception:
            pass
        m = re.match(r"^[a-z]+:\/\/(?P<u>[^:]+):?[^@]*@", dsn or "")
        return m.group("u") if m else ""

    # --- Courses ----------------------------------------------------------------
    def create_course(self, *, title: str, subject: str | None, grade_level: str | None, term: str | None, teacher_id: str) -> dict:
        title = title.strip()
        if not title or len(title) > 200:
            raise ValueError("invalid_title")
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                # RLS: set local current_sub for this transaction
                cur.execute("select set_config('app.current_sub', %s, true)", (teacher_id,))
                cur.execute(
                    """
                    insert into public.courses (title, subject, grade_level, term, teacher_id)
                    values (%s, %s, %s, %s, %s)
                    returning id::text,
                              title,
                              subject,
                              grade_level,
                              term,
                              teacher_id,
                              to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"') as created_at,
                              to_char(updated_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"') as updated_at
                    """,
                    (title, subject, grade_level, term, teacher_id),
                )
                row = cur.fetchone()
                conn.commit()
        return {
            "id": row[0],
            "title": row[1],
            "subject": row[2],
            "grade_level": row[3],
            "term": row[4],
            "teacher_id": row[5],
            "created_at": row[6],
            "updated_at": row[7],
        }

    def list_courses_for_teacher(self, *, teacher_id: str, limit: int, offset: int) -> List[dict]:
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, true)", (teacher_id,))
                cur.execute(
                    """
                    select id::text, title, subject, grade_level, term, teacher_id,
                           to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                           to_char(updated_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
                    from public.courses
                    where teacher_id = %s
                    order by created_at desc, id
                    limit %s offset %s
                    """,
                    (teacher_id, int(limit), int(offset)),
                )
                rows = cur.fetchall() or []
        return [
            {
                "id": r[0],
                "title": r[1],
                "subject": r[2],
                "grade_level": r[3],
                "term": r[4],
                "teacher_id": r[5],
                "created_at": r[6],
                "updated_at": r[7],
            }
            for r in rows
        ]

    def list_courses_for_student(self, *, student_id: str, limit: int, offset: int) -> List[dict]:
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, true)", (student_id,))
                cur.execute(
                    """
                    select c.id::text, c.title, c.subject, c.grade_level, c.term, c.teacher_id,
                           to_char(c.created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                           to_char(c.updated_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
                    from public.courses c
                    join public.course_memberships m on m.course_id = c.id
                    where m.student_id = %s
                    order by c.created_at desc, c.id
                    limit %s offset %s
                    """,
                    (student_id, int(limit), int(offset)),
                )
                rows = cur.fetchall() or []
        return [
            {
                "id": r[0],
                "title": r[1],
                "subject": r[2],
                "grade_level": r[3],
                "term": r[4],
                "teacher_id": r[5],
                "created_at": r[6],
                "updated_at": r[7],
            }
            for r in rows
        ]

    def get_course(self, course_id: str) -> Optional[dict]:
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                # best-effort: owner id is required by policy; derive via sub param on callers
                cur.execute(
                    """
                    select id::text, title, subject, grade_level, term, teacher_id,
                           to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                           to_char(updated_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
                    from public.courses where id = %s
                    """,
                    (course_id,),
                )
                r = cur.fetchone()
                if not r:
                    return None
        return {
            "id": r[0],
            "title": r[1],
            "subject": r[2],
            "grade_level": r[3],
            "term": r[4],
            "teacher_id": r[5],
            "created_at": r[6],
            "updated_at": r[7],
        }

    # --- Owner-scoped helpers (RLS-friendly) ------------------------------------
    def get_course_for_owner(self, course_id: str, owner_sub: str) -> Optional[dict]:
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, true)", (owner_sub,))
                cur.execute(
                    """
                    select id::text, title, subject, grade_level, term, teacher_id,
                           to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                           to_char(updated_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
                    from public.courses where id = %s
                    """,
                    (course_id,),
                )
                r = cur.fetchone()
                if not r:
                    return None
        return {
            "id": r[0],
            "title": r[1],
            "subject": r[2],
            "grade_level": r[3],
            "term": r[4],
            "teacher_id": r[5],
            "created_at": r[6],
            "updated_at": r[7],
        }

    def update_course_owned(self, course_id: str, owner_sub: str, *, title=_UNSET, subject=_UNSET, grade_level=_UNSET, term=_UNSET) -> Optional[dict]:
        """Update fields for a course owned by `owner_sub`.

        Why:
            Owner-only mutation must respect RLS and also defend-in-depth at the
            SQL layer to avoid privilege escalation if RLS is misconfigured.

        Parameters:
            course_id: Course identifier (uuid string)
            owner_sub: Subject id (teacher) expected to own the course
            title/subject/grade_level/term: Optional fields to update; omitted
                fields are left unchanged.

        Returns:
            Updated row as dict or None when not visible/updated.

        Security:
            - Sets `app.current_sub` to the owner.
            - Adds explicit `teacher_id = owner_sub` in the WHERE clause.
        """
        sets = []
        params: list = []
        if title is not _UNSET:
            if title is None:
                raise ValueError("invalid_title")
            t = (title or "").strip()
            if not t or len(t) > 200:
                raise ValueError("invalid_title")
            sets.append(("title", t))
        if subject is not _UNSET:
            sets.append(("subject", subject))
        if grade_level is not _UNSET:
            sets.append(("grade_level", grade_level))
        if term is not _UNSET:
            sets.append(("term", term))
        if not sets:
            return self.get_course_for_owner(course_id, owner_sub)
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, true)", (owner_sub,))
                try:
                    from psycopg import sql as _sql  # type: ignore
                    assignments = []
                    params = []
                    for col, val in sets:
                        assignments.append(_sql.SQL("{} = %s").format(_sql.Identifier(col)))
                        params.append(val)
                    params.extend([course_id, owner_sub])
                    stmt = _sql.SQL(
                        """
                        update public.courses set {assign}
                        where id = %s and teacher_id = %s
                        returning id::text, title, subject, grade_level, term, teacher_id,
                            to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                            to_char(updated_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
                        """
                    ).format(assign=_sql.SQL(", ").join(assignments))
                    cur.execute(stmt, params)
                except Exception:
                    # Fallback in environments without psycopg.sql
                    params = [val for _, val in sets] + [course_id, owner_sub]
                    cols = ", ".join([f"{col} = %s" for col, _ in sets])
                    cur.execute(
                        f"""
                        update public.courses set {cols}
                        where id = %s and teacher_id = %s
                        returning id::text, title, subject, grade_level, term, teacher_id,
                            to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                            to_char(updated_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
                        """,
                        params,
                    )
                r = cur.fetchone()
                if not r:
                    return None
                conn.commit()
        return {
            "id": r[0],
            "title": r[1],
            "subject": r[2],
            "grade_level": r[3],
            "term": r[4],
            "teacher_id": r[5],
            "created_at": r[6],
            "updated_at": r[7],
        }

    def delete_course_owned(self, course_id: str, owner_sub: str) -> bool:
        """Delete a course if and only if `owner_sub` owns it.

        Security:
            - Sets `app.current_sub` for RLS.
            - Enforces `teacher_id = owner_sub` in SQL WHERE clause.
        """
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, true)", (owner_sub,))
                cur.execute(
                    "delete from public.courses where id = %s and teacher_id = %s",
                    (course_id, owner_sub),
                )
                conn.commit()
                return True

    # --- Existence checks (prefer SECURITY DEFINER helpers) ---------------------
    def course_exists_for_owner(self, course_id: str, owner_sub: str) -> bool:
        """Check existence+ownership in one step.

        Behavior:
            - Uses SECURITY DEFINER helper `public.course_exists_for_owner` when
              present, which verifies ownership without relying on RLS.
            - Falls back to `get_course_for_owner` under RLS constraints.
        """
        try:
            with psycopg.connect(self._dsn) as conn:
                with conn.cursor() as cur:
                    cur.execute("select public.course_exists_for_owner(%s, %s)", (owner_sub, course_id))
                    r = cur.fetchone()
                    if r is not None:
                        return bool(r[0])
        except Exception:
            pass
        return self.get_course_for_owner(course_id, owner_sub) is not None

    def course_exists(self, course_id: str) -> Optional[bool]:
        """Return True/False when determinable, else None to avoid RLS-misclassification.

        Why:
            Under a limited-role DSN, RLS might hide rows owned by others.
            Existence must therefore use a SECURITY DEFINER helper that is
            independent of caller identity.
        """
        try:
            with psycopg.connect(self._dsn) as conn:
                with conn.cursor() as cur:
                    cur.execute("select public.course_exists(%s)", (course_id,))
                    r = cur.fetchone()
                    if r is not None:
                        return bool(r[0])
        except Exception:
            return None
        return None

    def list_members_for_owner(self, course_id: str, owner_sub: str, limit: int, offset: int) -> List[Tuple[str, str]]:
        """Return the roster for a course owned by `owner_sub` using the SECURITY DEFINER helper.

        Why:
            We rely on `public.get_course_members` so that the owner can read members without
            triggering RLS recursion on `course_memberships`.

        Behavior:
            - Returns `(student_id, joined_at_iso)` tuples ordered by join time.
            - Enforces pagination via helper-level clamping (max 50).

        Permissions:
            Caller must be a teacher who owns the course; helper enforces ownership.
        """
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, true)", (owner_sub,))
                # Helper runs with definer privileges and applies its own limit/offset guards.
                cur.execute(
                    """
                    select student_id,
                           to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
                    from public.get_course_members(%s, %s, %s, %s)
                    """,
                    (owner_sub, course_id, int(limit), int(offset)),
                )
                rows = cur.fetchall() or []
        return [(r[0], r[1]) for r in rows]

    def add_member_owned(self, course_id: str, owner_sub: str, student_id: str) -> bool:
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, true)", (owner_sub,))
                cur.execute(
                    """
                    insert into public.course_memberships (course_id, student_id)
                    values (%s, %s)
                    on conflict do nothing
                    """,
                    (course_id, student_id),
                )
                inserted = cur.rowcount == 1
                conn.commit()
        return inserted

    def remove_member_owned(self, course_id: str, owner_sub: str, student_id: str) -> None:
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, true)", (owner_sub,))
                cur.execute(
                    "delete from public.course_memberships where course_id = %s and student_id = %s",
                    (course_id, student_id),
                )
                conn.commit()

    def update_course(self, course_id: str, *, title=_UNSET, subject=_UNSET, grade_level=_UNSET, term=_UNSET) -> Optional[dict]:
        # Build dynamic update only for provided fields
        sets: list[tuple[str, object | None]] = []
        if title is not _UNSET:
            if title is None:
                raise ValueError("invalid_title")
            t = (title or "").strip()
            if not t or len(t) > 200:
                raise ValueError("invalid_title")
            sets.append(("title", t))
        if subject is not _UNSET:
            sets.append(("subject", subject))
        if grade_level is not _UNSET:
            sets.append(("grade_level", grade_level))
        if term is not _UNSET:
            sets.append(("term", term))
        if not sets:
            # nothing to update; return current row
            return self.get_course(course_id)
        with psycopg.connect(self._dsn, autocommit=True) as conn:
            with conn.cursor() as cur:
                try:
                    from psycopg import sql as _sql  # type: ignore
                    assignments = []
                    params = []
                    for col, val in sets:
                        assignments.append(_sql.SQL("{} = %s").format(_sql.Identifier(col)))
                        params.append(val)
                    params.append(course_id)
                    stmt = _sql.SQL(
                        """
                        update public.courses set {assign}
                        where id = %s
                        returning id::text, title, subject, grade_level, term, teacher_id,
                            to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                            to_char(updated_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
                        """
                    ).format(assign=_sql.SQL(", ").join(assignments))
                    cur.execute(stmt, params)
                except Exception:
                    params = [val for _, val in sets] + [course_id]
                    cols = ", ".join([f"{col} = %s" for col, _ in sets])
                    cur.execute(
                        f"""
                        update public.courses set {cols}
                        where id = %s
                        returning id::text, title, subject, grade_level, term, teacher_id,
                            to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                            to_char(updated_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
                        """,
                        params,
                    )
                r = cur.fetchone()
                if not r:
                    return None
        return {
            "id": r[0],
            "title": r[1],
            "subject": r[2],
            "grade_level": r[3],
            "term": r[4],
            "teacher_id": r[5],
            "created_at": r[6],
            "updated_at": r[7],
        }

    def delete_course(self, course_id: str) -> bool:
        with psycopg.connect(self._dsn, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("delete from public.courses where id = %s", (course_id,))
                # rowcount not reliable across drivers; attempt fetch not needed
                return True

    # --- Memberships -------------------------------------------------------------
    def add_member(self, course_id: str, student_id: str) -> bool:
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into public.course_memberships (course_id, student_id)
                    values (%s, %s)
                    on conflict do nothing
                    """,
                    (course_id, student_id),
                )
                inserted = cur.rowcount == 1
                conn.commit()
        return inserted

    def list_members(self, course_id: str, limit: int, offset: int) -> List[Tuple[str, str]]:
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select student_id,
                           to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
                    from public.course_memberships
                    where course_id = %s
                    order by created_at asc, student_id
                    limit %s offset %s
                    """,
                    (course_id, int(limit), int(offset)),
                )
                rows = cur.fetchall() or []
        return [(r[0], r[1]) for r in rows]

    def remove_member(self, course_id: str, student_id: str) -> None:
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "delete from public.course_memberships where course_id = %s and student_id = %s",
                    (course_id, student_id),
                )
                conn.commit()
