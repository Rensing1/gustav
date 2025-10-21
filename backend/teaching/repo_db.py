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

from typing import List, Tuple, Optional, Dict
import os
import re
from urllib.parse import urlparse
from uuid import UUID

try:
    import psycopg
    HAVE_PSYCOPG = True
except Exception:  # pragma: no cover - optional in some dev envs
    psycopg = None  # type: ignore
    HAVE_PSYCOPG = False
else:  # pragma: no cover - import errors handled above
    try:
        from psycopg.errors import UniqueViolation  # type: ignore
    except Exception:  # pragma: no cover - fallback when errors module unavailable
        UniqueViolation = None  # type: ignore


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

    # --- Units -----------------------------------------------------------------
    def list_units_for_author(self, *, author_id: str, limit: int, offset: int) -> List[dict]:
        """Return units authored by `author_id` with pagination (teacher scope)."""
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
                cur.execute(
                    """
                    select id::text,
                           title,
                           summary,
                           author_id,
                           to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                           to_char(updated_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
                    from public.learning_units
                    where author_id = %s
                    order by created_at desc, id
                    limit %s offset %s
                    """,
                    (author_id, int(limit), int(offset)),
                )
                rows = cur.fetchall() or []
        return [
            {
                "id": r[0],
                "title": r[1],
                "summary": r[2],
                "author_id": r[3],
                "created_at": r[4],
                "updated_at": r[5],
            }
            for r in rows
        ]

    def create_unit(self, *, title: str, summary: Optional[str], author_id: str) -> dict:
        """
        Persist a unit for the given author.

        Behavior:
            - Enforces simple validation (non-empty title, summary length).
            - Sets RLS context so only the author can mutate the row.
        """
        title = (title or "").strip()
        if not title or len(title) > 200:
            raise ValueError("invalid_title")
        if summary is not None:
            summary = summary.strip()
            if summary and len(summary) > 2000:
                raise ValueError("invalid_summary")
            if summary == "":
                summary = None
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
                cur.execute(
                    """
                    insert into public.learning_units (title, summary, author_id)
                    values (%s, %s, %s)
                    returning id::text,
                              title,
                              summary,
                              author_id,
                              to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                              to_char(updated_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
                    """,
                    (title, summary, author_id),
                )
                row = cur.fetchone()
                conn.commit()
        return {
            "id": row[0],
            "title": row[1],
            "summary": row[2],
            "author_id": row[3],
            "created_at": row[4],
            "updated_at": row[5],
        }

    def update_unit_owned(self, unit_id: str, author_id: str, *, title=_UNSET, summary=_UNSET) -> Optional[dict]:
        """
        Update fields of a unit when the caller is the author.

        Parameters:
            unit_id: Target unit identifier.
            author_id: Expected author (used for RLS + WHERE clause).
            title/summary: Optional updates; omitted values remain unchanged.
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
        if summary is not _UNSET:
            if summary is None:
                sets.append(("summary", None))
            else:
                s = summary.strip()
                if s and len(s) > 2000:
                    raise ValueError("invalid_summary")
                sets.append(("summary", s or None))
        if not sets:
            return self.get_unit_for_author(unit_id, author_id)
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
                try:
                    from psycopg import sql as _sql  # type: ignore

                    assignments = []
                    params = []
                    for col, val in sets:
                        assignments.append(_sql.SQL("{} = %s").format(_sql.Identifier(col)))
                        params.append(val)
                    params.extend([unit_id, author_id])
                    stmt = _sql.SQL(
                        """
                        update public.learning_units
                        set {assign}
                        where id = %s and author_id = %s
                        returning id::text,
                                 title,
                                 summary,
                                 author_id,
                                 to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                                 to_char(updated_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
                        """
                    ).format(assign=_sql.SQL(", ").join(assignments))
                    cur.execute(stmt, params)
                except Exception:
                    params = [val for _, val in sets] + [unit_id, author_id]
                    cols = ", ".join([f"{col} = %s" for col, _ in sets])
                    cur.execute(
                        f"""
                        update public.learning_units
                        set {cols}
                        where id = %s and author_id = %s
                        returning id::text,
                                 title,
                                 summary,
                                 author_id,
                                 to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                                 to_char(updated_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
                        """,
                        params,
                    )
                row = cur.fetchone()
                if not row:
                    return None
                conn.commit()
        return {
            "id": row[0],
            "title": row[1],
            "summary": row[2],
            "author_id": row[3],
            "created_at": row[4],
            "updated_at": row[5],
        }

    def get_unit_for_author(self, unit_id: str, author_id: str) -> Optional[dict]:
        """Fetch a unit enforcing author ownership through RLS."""
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
                cur.execute(
                    """
                    select id::text,
                           title,
                           summary,
                           author_id,
                           to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                           to_char(updated_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
                    from public.learning_units
                    where id = %s
                    """,
                    (unit_id,),
                )
                row = cur.fetchone()
                if not row:
                    return None
        return {
            "id": row[0],
            "title": row[1],
            "summary": row[2],
            "author_id": row[3],
            "created_at": row[4],
            "updated_at": row[5],
        }

    def delete_unit_owned(self, unit_id: str, author_id: str) -> bool:
        """Delete a unit owned by `author_id` (RLS + explicit ownership guard)."""
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
                cur.execute(
                    "delete from public.learning_units where id = %s and author_id = %s",
                    (unit_id, author_id),
                )
                conn.commit()
                return cur.rowcount > 0

    def unit_exists_for_author(self, unit_id: str, author_id: str) -> bool:
        """Check whether the unit exists and is owned by `author_id` via SECURITY DEFINER helper."""
        try:
            with psycopg.connect(self._dsn) as conn:
                with conn.cursor() as cur:
                    cur.execute("select public.unit_exists_for_author(%s, %s)", (author_id, unit_id))
                    r = cur.fetchone()
                    if r is not None:
                        return bool(r[0])
        except Exception:
            pass
        return self.get_unit_for_author(unit_id, author_id) is not None

    def unit_exists(self, unit_id: str) -> Optional[bool]:
        """Check existence (ignoring ownership) using SECURITY DEFINER helper."""
        try:
            with psycopg.connect(self._dsn) as conn:
                with conn.cursor() as cur:
                    cur.execute("select public.unit_exists(%s)", (unit_id,))
                    r = cur.fetchone()
                    if r is not None:
                        return bool(r[0])
        except Exception:
            return None
        return None

    # --- Unit sections ---------------------------------------------------------
    def list_sections_for_author(self, unit_id: str, author_id: str) -> List[dict]:
        """List sections of a unit authored by the caller.

        Why:
            Web adapter needs an owner-scoped listing that respects RLS and
            ordering semantics for display and validation.

        Parameters:
            unit_id: Target learning unit UUID string.
            author_id: Caller identity (OIDC sub). Used to set RLS context.

        Behavior:
            - Returns sections for the specified unit ordered by `position, id`.
            - Returns an empty list for non-owners due to RLS filtering.

        Security:
            - Sets `app.current_sub = author_id` to activate RLS policies
              (author-only access via join to `learning_units`).
        """
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
                cur.execute(
                    """
                    select id::text,
                           unit_id::text,
                           title,
                           position,
                           to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                           to_char(updated_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
                    from public.unit_sections
                    where unit_id = %s
                    order by position asc, id
                    """,
                    (unit_id,),
                )
                rows = cur.fetchall() or []
        return [
            {
                "id": r[0],
                "unit_id": r[1],
                "title": r[2],
                "position": r[3],
                "created_at": r[4],
                "updated_at": r[5],
            }
            for r in rows
        ]

    def create_section(self, unit_id: str, title: str, author_id: str) -> dict:
        """Create a new section at the next position within a unit.

        Why:
            Sections are ordered within a unit. New sections append to the end
            in a concurrency-safe way.

        Parameters:
            unit_id: Target unit UUID string (must be authored by `author_id`).
            title: Section title (1..200 chars).
            author_id: Caller identity; sets RLS context.

        Behavior:
            - Validates minimal constraints (non-empty title, max length 200).
            - Computes `position = max(position) + 1` for the unit.
            - Returns persisted row as dict.

        Concurrency:
            - Locks existing rows in `unit_sections` for the unit to prevent
              race conditions when computing the next position.

        Security:
            - RLS requires the unit to be authored by `author_id`.
        """
        title = (title or "").strip()
        if not title or len(title) > 200:
            raise ValueError("invalid_title")
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
                # Ensure the unit is owned/visible; lock current rows for order safety
                cur.execute(
                    "select id from public.unit_sections where unit_id = %s for update",
                    (unit_id,),
                )
                # Compute next position within the unit
                cur.execute(
                    "select coalesce(max(position), 0) + 1 from public.unit_sections where unit_id = %s",
                    (unit_id,),
                )
                next_pos = int(cur.fetchone()[0])
                cur.execute(
                    """
                    insert into public.unit_sections (unit_id, title, position)
                    values (%s, %s, %s)
                    returning id::text,
                              unit_id::text,
                              title,
                              position,
                              to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                              to_char(updated_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
                    """,
                    (unit_id, title, next_pos),
                )
                row = cur.fetchone()
                conn.commit()
        return {
            "id": row[0],
            "unit_id": row[1],
            "title": row[2],
            "position": row[3],
            "created_at": row[4],
            "updated_at": row[5],
        }

    def update_section_title(self, unit_id: str, section_id: str, title: str, author_id: str) -> Optional[dict]:
        """Update the title of a section within a unit owned by the caller.

        Why:
            Allow authors to rename sections without changing ordering.

        Behavior:
            - Returns updated row on success; None when row not visible (not found or not owned).

        Security:
            - RLS ensures only the author's sections are mutable.
        """
        if title is None:
            raise ValueError("invalid_title")
        t = (title or "").strip()
        if not t or len(t) > 200:
            raise ValueError("invalid_title")
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
                cur.execute(
                    """
                    update public.unit_sections
                    set title = %s
                    where id = %s and unit_id = %s
                    returning id::text,
                              unit_id::text,
                              title,
                              position,
                              to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                              to_char(updated_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
                    """,
                    (t, section_id, unit_id),
                )
                row = cur.fetchone()
                if not row:
                    return None
                conn.commit()
        return {
            "id": row[0],
            "unit_id": row[1],
            "title": row[2],
            "position": row[3],
            "created_at": row[4],
            "updated_at": row[5],
        }

    def delete_section(self, unit_id: str, section_id: str, author_id: str) -> bool:
        """Delete a section and resequence remaining positions within the unit.

        Why:
            Maintain contiguous ordering (1..n) after deletions to keep UX simple.

        Behavior:
            - Returns True on delete; False if the row is not visible (not found/not owned).

        Security:
            - RLS restricts visibility to the author; non-owners get False.
        """
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
                # Lock target row to ensure stable resequencing
                cur.execute(
                    "select id from public.unit_sections where id = %s and unit_id = %s for update",
                    (section_id, unit_id),
                )
                row = cur.fetchone()
                if not row:
                    return False
                cur.execute(
                    "delete from public.unit_sections where id = %s and unit_id = %s",
                    (section_id, unit_id),
                )
                # Resequence positions contiguously (1..n)
                cur.execute(
                    """
                    with ordered as (
                      select id, row_number() over (order by position asc, id) as rn
                      from public.unit_sections
                      where unit_id = %s
                    )
                    update public.unit_sections u
                    set position = o.rn
                    from ordered o
                    where u.id = o.id
                    """,
                    (unit_id,),
                )
                conn.commit()
                return True

    def reorder_unit_sections_owned(self, unit_id: str, author_id: str, section_ids: List[str]) -> List[dict]:
        """Atomically reorder sections for a unit the author owns.

        Why:
            Reordering must be safe under concurrency and preserve uniqueness of
            `(unit_id, position)` without gaps or duplicates.

        Behavior:
            - Validates exact set equality of submitted vs existing IDs.
            - Updates positions to 1..n in a single transaction and returns the
              new ordered list.

        Security:
            - RLS restricts the visible `existing` set to the author's unit.
            - Cross-unit IDs are detected: existing_set check + presence in table
              → LookupError to map to 404 at the web layer.
        """
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
                cur.execute(
                    """
                    select id::text
                    from public.unit_sections
                    where unit_id = %s
                    order by position asc, id
                    """,
                    (unit_id,),
                )
                existing = [row[0] for row in (cur.fetchall() or [])]
                if not existing:
                    raise ValueError("no_sections")
                existing_set = set(existing)
                submitted_set = set(section_ids)
                if submitted_set != existing_set or len(section_ids) != len(existing):
                    extra = submitted_set - existing_set
                    if extra:
                        cur.execute(
                            "select count(*) from public.unit_sections where id = any(%s)",
                            (list(extra),),
                        )
                        c = cur.fetchone()
                        if c and int(c[0]) > 0:
                            raise LookupError("section_not_in_unit")
                    raise ValueError("section_mismatch")
                # Deferrable unique constraint allows in-place position updates
                cur.execute("set constraints unit_sections_unit_id_position_key deferred")
                orderings = list(range(1, len(section_ids) + 1))
                cur.execute(
                    """
                    with new_order as (
                      select sid, ord from unnest(%s::uuid[], %s::int[]) as t(sid, ord)
                    )
                    update public.unit_sections s
                    set position = n.ord
                    from new_order n
                    where s.id = n.sid
                      and s.unit_id = %s
                    """,
                    (section_ids, orderings, unit_id),
                )
                cur.execute(
                    """
                    select id::text,
                           unit_id::text,
                           title,
                           position,
                           to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                           to_char(updated_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
                    from public.unit_sections
                    where unit_id = %s
                    order by position asc, id
                    """,
                    (unit_id,),
                )
                rows = cur.fetchall() or []
                conn.commit()
        return [
            {
                "id": r[0],
                "unit_id": r[1],
                "title": r[2],
                "position": r[3],
                "created_at": r[4],
                "updated_at": r[5],
            }
            for r in rows
        ]

    # --- Course modules ---------------------------------------------------------
    def list_course_modules_for_owner(self, course_id: str, owner_sub: str) -> List[dict]:
        """Return modules for a course owned by `owner_sub`, ordered by position."""
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, true)", (owner_sub,))
                cur.execute(
                    """
                    select id::text,
                           course_id::text,
                           unit_id::text,
                           position,
                           context_notes,
                           to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                           to_char(updated_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
                    from public.course_modules
                    where course_id = %s
                    order by position asc, id
                    """,
                    (course_id,),
                )
                rows = cur.fetchall() or []
        return [
            {
                "id": r[0],
                "course_id": r[1],
                "unit_id": r[2],
                "position": r[3],
                "context_notes": r[4],
                "created_at": r[5],
                "updated_at": r[6],
            }
            for r in rows
        ]

    def create_course_module_owned(self, course_id: str, owner_sub: str, *, unit_id: str, context_notes: Optional[str]) -> dict:
        """
        Attach a unit as a module within an owned course.

        Validation:
            - Notes trimmed to None when blank; length limited to 2000 characters.
            - Unique constraint violations bubble up as ValueError("duplicate_module").
        """
        try:
            unit_uuid = str(UUID(str(unit_id)))
        except (ValueError, TypeError) as exc:
            raise ValueError("invalid_unit_id") from exc
        notes = None
        if context_notes is not None:
            notes = context_notes.strip()
            if notes == "":
                notes = None
            if notes and len(notes) > 2000:
                raise ValueError("invalid_context_notes")
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, true)", (owner_sub,))
                try:
                    cur.execute(
                        """
                        with next_pos as (
                          select coalesce(max(position), 0) + 1 as pos
                          from public.course_modules
                          where course_id = %s
                        )
                        insert into public.course_modules (course_id, unit_id, position, context_notes)
                        select %s, %s, next_pos.pos, %s
                        from next_pos
                        returning id::text,
                                  course_id::text,
                                  unit_id::text,
                                  position,
                                  context_notes,
                                  to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                                  to_char(updated_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
                        """,
                        (course_id, course_id, unit_uuid, notes),
                    )
                except Exception as exc:
                    sqlstate = getattr(exc, "sqlstate", None) or getattr(exc, "pgcode", None)
                    if UniqueViolation and isinstance(exc, UniqueViolation):
                        conn.rollback()
                        raise ValueError("duplicate_module") from exc
                    if sqlstate == "23505":
                        conn.rollback()
                        raise ValueError("duplicate_module") from exc
                    raise
                row = cur.fetchone()
                if not row:
                    conn.rollback()
                    raise PermissionError("module_insert_forbidden")
                conn.commit()
        return {
            "id": row[0],
            "course_id": row[1],
            "unit_id": row[2],
            "position": row[3],
            "context_notes": row[4],
            "created_at": row[5],
            "updated_at": row[6],
        }

    def reorder_course_modules_owned(self, course_id: str, owner_sub: str, module_ids: List[str]) -> List[dict]:
        """
        Reorder modules for a course owned by `owner_sub`.

        Behavior:
            - Validates the requested set matches the course modules exactly.
            - Uses a two-phase update (offset then final order) to avoid unique(position) conflicts.
        """
        if not module_ids:
            raise ValueError("empty_reorder")
        try:
            normalized_ids = [str(UUID(str(mid))) for mid in module_ids]
        except (ValueError, TypeError) as exc:
            raise ValueError("invalid_module_id") from exc
        module_ids = normalized_ids
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, true)", (owner_sub,))
                cur.execute(
                    """
                    select id::text
                    from public.course_modules
                    where course_id = %s
                    order by position asc, id
                    """,
                    (course_id,),
                )
                existing = [row[0] for row in (cur.fetchall() or [])]
                if not existing:
                    raise ValueError("no_modules")
                existing_set = set(existing)
                submitted_set = set(module_ids)
                # Distinguish between missing/extra IDs before mutating the DB.
                if submitted_set != existing_set or len(module_ids) != len(existing):
                    extra = submitted_set - existing_set
                    if extra:
                        cur.execute(
                            """
                            select count(*) from public.course_modules
                            where id = any(%s)
                            """,
                            (list(extra),),
                        )
                        row = cur.fetchone()
                        count = row[0] if row else 0
                        if count:
                            raise LookupError("module_not_found")
                    raise ValueError("module_mismatch")
                cur.execute("set constraints course_modules_course_id_position_key deferred")
                orderings = list(range(1, len(module_ids) + 1))
                cur.execute(
                    """
                    with new_order as (
                      select module_id, ord
                      from unnest(%s::uuid[], %s::int[]) as t(module_id, ord)
                    )
                    update public.course_modules m
                    set position = new_order.ord
                    from new_order
                    where m.id = new_order.module_id
                      and m.course_id = %s
                    """,
                    (module_ids, orderings, course_id),
                )
                cur.execute(
                    """
                    select id::text,
                           course_id::text,
                           unit_id::text,
                           position,
                           context_notes,
                           to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                           to_char(updated_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
                    from public.course_modules
                    where course_id = %s
                    order by position asc, id
                    """,
                    (course_id,),
                )
                rows = cur.fetchall() or []
                conn.commit()
        return [
            {
                "id": r[0],
                "course_id": r[1],
                "unit_id": r[2],
                "position": r[3],
                "context_notes": r[4],
                "created_at": r[5],
                "updated_at": r[6],
            }
            for r in rows
        ]

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
