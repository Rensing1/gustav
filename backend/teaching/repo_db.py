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

from typing import Any, List, Tuple, Optional, Dict
import os
import re
from datetime import datetime, timezone
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

_MATERIAL_COLUMNS_SQL = """
    id::text,
    unit_id::text,
    section_id::text,
    title,
    body_md,
    position,
    kind,
    storage_key,
    filename_original,
    mime_type,
    size_bytes,
    sha256,
    alt_text,
    to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
    to_char(updated_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
"""


def _material_row_to_dict(row: Tuple) -> Dict[str, Any]:
    return {
        "id": row[0],
        "unit_id": row[1],
        "section_id": row[2],
        "title": row[3],
        "body_md": row[4],
        "position": int(row[5]) if row[5] is not None else None,
        "kind": row[6],
        "storage_key": row[7],
        "filename_original": row[8],
        "mime_type": row[9],
        "size_bytes": int(row[10]) if row[10] is not None else None,
        "sha256": row[11],
        "alt_text": row[12],
        "created_at": row[13],
        "updated_at": row[14],
    }


_TASK_COLUMNS_SQL = """
    id::text,
    unit_id::text,
    section_id::text,
    instruction_md,
    criteria,
    hints_md,
    case
      when due_at is null then null
      else to_char(due_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
    end as due_at_iso,
    max_attempts,
    position,
    to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
    to_char(updated_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
"""


def _task_row_to_dict(row: Tuple) -> Dict[str, Any]:
    return {
        "id": row[0],
        "unit_id": row[1],
        "section_id": row[2],
        "instruction_md": row[3],
        "criteria": list(row[4] or []),
        "hints_md": row[5],
        "due_at": row[6],
        "max_attempts": int(row[7]) if row[7] is not None else None,
        "position": int(row[8]) if row[8] is not None else None,
        "created_at": row[9],
        "updated_at": row[10],
        "kind": "native",
    }


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
                    from public.units
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
                    insert into public.units (title, summary, author_id)
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
                        update public.units
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
                        update public.units
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
                    from public.units
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
                    "delete from public.units where id = %s and author_id = %s",
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

    def section_exists_for_author(self, unit_id: str, section_id: str, author_id: str) -> bool:
        """Check whether a section belongs to the unit and is visible to the author."""
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
                cur.execute(
                    """
                    select 1
                    from public.unit_sections
                    where unit_id = %s
                      and id = %s
                    """,
                    (unit_id, section_id),
                )
                return cur.fetchone() is not None

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
              (author-only access via join to `units`).
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
                # Serialize concurrent inserts by locking the parent unit row.
                # RLS ensures only the author's units are lockable/visible.
                cur.execute("select id from public.units where id = %s for update", (unit_id,))
                # Lock current sections for additional safety (no-ops if none exist).
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
                row = None
                try:
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
                except Exception as exc:  # rare race: recompute once on unique violation
                    sqlstate = getattr(exc, "sqlstate", None) or getattr(exc, "pgcode", None)
                    if UniqueViolation and isinstance(exc, UniqueViolation) or sqlstate == "23505":
                        conn.rollback()
                        with conn.cursor() as cur2:
                            cur2.execute("select set_config('app.current_sub', %s, true)", (author_id,))
                            cur2.execute(
                                "select coalesce(max(position), 0) + 1 from public.unit_sections where unit_id = %s",
                                (unit_id,),
                            )
                            next_pos = int(cur2.fetchone()[0])
                            cur2.execute(
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
                            row = cur2.fetchone()
                    else:
                        raise
                if row is None:
                    raise RuntimeError("unit_sections insert returned no row")
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
                    # Align with API contract: treat as mismatch when no sections are present
                    raise ValueError("section_mismatch")
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

    # --- Section materials -----------------------------------------------------
    def list_materials_for_section_owned(self, unit_id: str, section_id: str, author_id: str) -> List[dict]:
        """Return ordered markdown materials for a section authored by the caller."""
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
                cur.execute(
                    f"""
                    select {_MATERIAL_COLUMNS_SQL}
                    from public.unit_materials
                    where unit_id = %s
                      and section_id = %s
                    order by position asc, id
                    """,
                    (unit_id, section_id),
                )
                rows = cur.fetchall() or []
        return [_material_row_to_dict(r) for r in rows]

    def create_markdown_material(self, unit_id: str, section_id: str, author_id: str, *, title: str, body_md: str) -> dict:
        """Create a markdown material at the next position within a section."""
        title = (title or "").strip()
        if not title or len(title) > 200:
            raise ValueError("invalid_title")
        if body_md is None or not isinstance(body_md, str):
            raise ValueError("invalid_body_md")
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
                cur.execute(
                    "select id from public.unit_sections where id = %s and unit_id = %s for update",
                    (section_id, unit_id),
                )
                sec_row = cur.fetchone()
                if not sec_row:
                    raise LookupError("section_not_found")
                cur.execute(
                    "select id from public.unit_materials where section_id = %s for update",
                    (section_id,),
                )
                cur.execute(
                    "select coalesce(max(position), 0) + 1 from public.unit_materials where section_id = %s",
                    (section_id,),
                )
                next_pos = int(cur.fetchone()[0])
                row = None
                try:
                    cur.execute(
                        f"""
                        insert into public.unit_materials (unit_id, section_id, title, body_md, position)
                        values (%s, %s, %s, %s, %s)
                        returning {_MATERIAL_COLUMNS_SQL}
                        """,
                        (unit_id, section_id, title, body_md, next_pos),
                    )
                    row = cur.fetchone()
                except Exception as exc:
                    sqlstate = getattr(exc, "sqlstate", None) or getattr(exc, "pgcode", None)
                    if UniqueViolation and isinstance(exc, UniqueViolation) or sqlstate == "23505":
                        conn.rollback()
                        with conn.cursor() as cur2:
                            cur2.execute("select set_config('app.current_sub', %s, true)", (author_id,))
                            cur2.execute(
                                "select coalesce(max(position), 0) + 1 from public.unit_materials where section_id = %s",
                                (section_id,),
                            )
                            next_pos = int(cur2.fetchone()[0])
                            cur2.execute(
                                f"""
                                insert into public.unit_materials (unit_id, section_id, title, body_md, position)
                                values (%s, %s, %s, %s, %s)
                                returning {_MATERIAL_COLUMNS_SQL}
                                """,
                                (unit_id, section_id, title, body_md, next_pos),
                            )
                            row = cur2.fetchone()
                    else:
                        raise
                if row is None:
                    raise RuntimeError("unit_materials insert returned no row")
                conn.commit()
        return _material_row_to_dict(row)

    def get_material_owned(self, unit_id: str, section_id: str, material_id: str, author_id: str) -> Optional[dict]:
        """Fetch a single material enforcing author ownership via RLS."""
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
                cur.execute(
                    f"""
                    select {_MATERIAL_COLUMNS_SQL}
                    from public.unit_materials
                    where id = %s
                      and unit_id = %s
                      and section_id = %s
                    """,
                    (material_id, unit_id, section_id),
                )
                row = cur.fetchone()
        if not row:
            return None
        return _material_row_to_dict(row)

    def update_material(
        self,
        unit_id: str,
        section_id: str,
        material_id: str,
        author_id: str,
        *,
        title=_UNSET,
        body_md=_UNSET,
        alt_text=_UNSET,
    ) -> Optional[dict]:
        """Update mutable fields (title, body_md, alt_text) for a material owned by the caller."""
        if title is _UNSET and body_md is _UNSET and alt_text is _UNSET:
            return self.get_material_owned(unit_id, section_id, material_id, author_id)
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
                cur.execute(
                    """
                    select kind
                    from public.unit_materials
                    where id = %s
                      and unit_id = %s
                      and section_id = %s
                    for update
                    """,
                    (material_id, unit_id, section_id),
                )
                kind_row = cur.fetchone()
                if not kind_row:
                    return None
                material_kind = kind_row[0]
                updates: List[tuple[str, object]] = []
                if title is not _UNSET:
                    if title is None:
                        raise ValueError("invalid_title")
                    t = (str(title) or "").strip()
                    if not t or len(t) > 200:
                        raise ValueError("invalid_title")
                    updates.append(("title", t))
                if body_md is not _UNSET:
                    if material_kind != "markdown":
                        raise ValueError("invalid_body_md")
                    if body_md is None or not isinstance(body_md, str):
                        raise ValueError("invalid_body_md")
                    updates.append(("body_md", body_md))
                if alt_text is not _UNSET:
                    if alt_text is None:
                        updates.append(("alt_text", None))
                    elif not isinstance(alt_text, str):
                        raise ValueError("invalid_alt_text")
                    else:
                        normalized_alt = alt_text.strip()
                        if len(normalized_alt) > 500:
                            raise ValueError("invalid_alt_text")
                        updates.append(("alt_text", normalized_alt or None))
                if not updates:
                    cur.execute(
                        f"""
                        select {_MATERIAL_COLUMNS_SQL}
                        from public.unit_materials
                        where id = %s
                          and unit_id = %s
                          and section_id = %s
                        """,
                        (material_id, unit_id, section_id),
                    )
                    row = cur.fetchone()
                    conn.rollback()
                    if not row:
                        return None
                    return _material_row_to_dict(row)
                try:
                    from psycopg import sql as _sql  # type: ignore

                    assignments = []
                    params: List[object] = []
                    for col, val in updates:
                        assignments.append(_sql.SQL("{} = %s").format(_sql.Identifier(col)))
                        params.append(val)
                    params.extend([material_id, unit_id, section_id])
                    stmt = _sql.SQL(
                        f"""
                        update public.unit_materials
                        set {{assign}}
                        where id = %s
                          and unit_id = %s
                          and section_id = %s
                        returning {_MATERIAL_COLUMNS_SQL}
                        """
                    ).format(assign=_sql.SQL(", ").join(assignments))
                    cur.execute(stmt, params)
                except Exception:
                    params = [val for _, val in updates] + [material_id, unit_id, section_id]
                    cols = ", ".join([f"{col} = %s" for col, _ in updates])
                    cur.execute(
                        f"""
                        update public.unit_materials
                        set {cols}
                        where id = %s
                          and unit_id = %s
                          and section_id = %s
                        returning {_MATERIAL_COLUMNS_SQL}
                        """,
                        params,
                    )
                row = cur.fetchone()
                if not row:
                    conn.rollback()
                    return None
                conn.commit()
        return _material_row_to_dict(row)

    def delete_material(self, unit_id: str, section_id: str, material_id: str, author_id: str) -> bool:
        """Delete a material and resequence remaining positions."""
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
                cur.execute(
                    """
                    select id
                    from public.unit_materials
                    where id = %s
                      and unit_id = %s
                      and section_id = %s
                    for update
                    """,
                    (material_id, unit_id, section_id),
                )
                row = cur.fetchone()
                if not row:
                    return False
                cur.execute(
                    "delete from public.unit_materials where id = %s and unit_id = %s and section_id = %s",
                    (material_id, unit_id, section_id),
                )
                cur.execute(
                    """
                    with ordered as (
                      select id, row_number() over (order by position asc, id) as rn
                      from public.unit_materials
                      where section_id = %s
                    )
                    update public.unit_materials m
                    set position = o.rn
                    from ordered o
                    where m.id = o.id
                    """,
                    (section_id,),
                )
                conn.commit()
                return True

    def create_file_upload_intent(
        self,
        unit_id: str,
        section_id: str,
        author_id: str,
        *,
        intent_id: str,
        material_id: str,
        storage_key: str,
        filename: str,
        mime_type: str,
        size_bytes: int,
        expires_at: datetime,
    ) -> Dict[str, Any]:
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
                cur.execute(
                    "select id from public.unit_sections where id = %s and unit_id = %s for update",
                    (section_id, unit_id),
                )
                if not cur.fetchone():
                    raise LookupError("section_not_found")
                cur.execute(
                    """
                    insert into public.upload_intents (
                        id, material_id, unit_id, section_id, author_id,
                        storage_key, filename, mime_type, size_bytes, expires_at
                    )
                    values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    returning id::text,
                              material_id::text,
                              storage_key,
                              filename,
                              mime_type,
                              size_bytes,
                              expires_at,
                              consumed_at
                    """,
                    (
                        intent_id,
                        material_id,
                        unit_id,
                        section_id,
                        author_id,
                        storage_key,
                        filename,
                        mime_type,
                        size_bytes,
                        expires_at,
                    ),
                )
                row = cur.fetchone()
                conn.commit()
        return {
            "intent_id": row[0],
            "material_id": row[1],
            "storage_key": row[2],
            "filename": row[3],
            "mime_type": row[4],
            "size_bytes": int(row[5]),
            "expires_at": row[6],
            "consumed_at": row[7],
        }

    def get_upload_intent_owned(
        self,
        intent_id: str,
        unit_id: str,
        section_id: str,
        author_id: str,
    ) -> Optional[Dict[str, Any]]:
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
                cur.execute(
                    """
                    select id::text,
                           material_id::text,
                           storage_key,
                           filename,
                           mime_type,
                           size_bytes,
                           expires_at,
                           consumed_at
                    from public.upload_intents
                    where id = %s
                      and unit_id = %s
                      and section_id = %s
                      and author_id = %s
                    """,
                    (intent_id, unit_id, section_id, author_id),
                )
                row = cur.fetchone()
        if not row:
            return None
        return {
            "intent_id": row[0],
            "material_id": row[1],
            "storage_key": row[2],
            "filename": row[3],
            "mime_type": row[4],
            "size_bytes": int(row[5]),
            "expires_at": row[6],
            "consumed_at": row[7],
        }

    def finalize_upload_intent_create_material(
        self,
        intent_id: str,
        unit_id: str,
        section_id: str,
        author_id: str,
        *,
        title: str,
        alt_text: Optional[str],
        sha256: str,
    ) -> Tuple[Dict[str, Any], bool]:
        now = datetime.now(timezone.utc)
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
                cur.execute(
                    """
                    select id::text,
                           material_id::text,
                           storage_key,
                           filename,
                           mime_type,
                           size_bytes,
                           expires_at,
                           consumed_at
                    from public.upload_intents
                    where id = %s
                      and unit_id = %s
                      and section_id = %s
                      and author_id = %s
                    for update
                    """,
                    (intent_id, unit_id, section_id, author_id),
                )
                row = cur.fetchone()
                if not row:
                    raise LookupError("intent_not_found")
                (
                    _intent_id,
                    material_id,
                    storage_key,
                    filename,
                    mime_type,
                    size_bytes,
                    expires_at,
                    consumed_at,
                ) = row
                if consumed_at is not None:
                    cur.execute(
                        f"""
                        select {_MATERIAL_COLUMNS_SQL}
                        from public.unit_materials
                        where id = %s
                          and unit_id = %s
                          and section_id = %s
                        """,
                        (material_id, unit_id, section_id),
                    )
                    material_row = cur.fetchone()
                    if not material_row:
                        raise LookupError("material_not_found")
                    conn.rollback()
                    return _material_row_to_dict(material_row), False
                if expires_at <= now:
                    raise ValueError("intent_expired")
                cur.execute(
                    "select id from public.unit_sections where id = %s and unit_id = %s for update",
                    (section_id, unit_id),
                )
                cur.execute(
                    "select coalesce(max(position), 0) + 1 from public.unit_materials where section_id = %s",
                    (section_id,),
                )
                next_pos = int(cur.fetchone()[0])
                cur.execute(
                    f"""
                    insert into public.unit_materials (
                        id, unit_id, section_id, title, body_md, position, kind,
                        storage_key, filename_original, mime_type, size_bytes, sha256, alt_text
                    )
                    values (%s, %s, %s, %s, %s, %s, 'file', %s, %s, %s, %s, %s, %s)
                    returning {_MATERIAL_COLUMNS_SQL}
                    """,
                    (
                        material_id,
                        unit_id,
                        section_id,
                        title,
                        "",
                        next_pos,
                        storage_key,
                        filename,
                        mime_type,
                        size_bytes,
                        sha256,
                        alt_text,
                    ),
                )
                material_row = cur.fetchone()
                cur.execute(
                    "update public.upload_intents set consumed_at = %s where id = %s",
                    (now, intent_id),
                )
                conn.commit()
        return _material_row_to_dict(material_row), True

    def reorder_section_materials(
        self,
        unit_id: str,
        section_id: str,
        author_id: str,
        material_ids: List[str],
    ) -> List[dict]:
        """Atomically reorder materials of a section owned by the caller."""
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
                cur.execute(
                    """
                    select id::text
                    from public.unit_materials
                    where unit_id = %s
                      and section_id = %s
                    order by position asc, id
                    """,
                    (unit_id, section_id),
                )
                existing = [row[0] for row in (cur.fetchall() or [])]
                if not existing:
                    raise ValueError("material_mismatch")
                existing_set = set(existing)
                submitted_set = set(material_ids)
                if submitted_set != existing_set or len(material_ids) != len(existing):
                    extra = submitted_set - existing_set
                    if extra:
                        cur.execute(
                            "select count(*) from public.unit_materials where id = any(%s)",
                            (list(extra),),
                        )
                        count = cur.fetchone()
                        if count and int(count[0]) > 0:
                            raise LookupError("material_not_in_section")
                    raise ValueError("material_mismatch")
                cur.execute("set constraints unit_materials_section_id_position_key deferred")
                orderings = list(range(1, len(material_ids) + 1))
                cur.execute(
                    """
                    with new_order as (
                      select mid, ord from unnest(%s::uuid[], %s::int[]) as t(mid, ord)
                    )
                    update public.unit_materials m
                    set position = n.ord
                    from new_order n
                    where m.id = n.mid
                      and m.section_id = %s
                      and m.unit_id = %s
                    """,
                    (material_ids, orderings, section_id, unit_id),
                )
                cur.execute(
                    """
                    select id::text,
                           unit_id::text,
                           section_id::text,
                           title,
                           body_md,
                           position,
                           to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                           to_char(updated_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
                    from public.unit_materials
                    where unit_id = %s
                      and section_id = %s
                    order by position asc, id
                    """,
                    (unit_id, section_id),
                )
                rows = cur.fetchall() or []
                conn.commit()
        return [
            {
                "id": r[0],
                "unit_id": r[1],
                "section_id": r[2],
                "title": r[3],
                "body_md": r[4],
                "position": r[5],
                "created_at": r[6],
                "updated_at": r[7],
            }
            for r in rows
        ]

    # --- Section tasks --------------------------------------------------------
    def list_tasks_for_section_owned(self, unit_id: str, section_id: str, author_id: str) -> List[dict]:
        """Return ordered tasks for a section authored by the caller."""
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
                cur.execute(
                    f"""
                    select {_TASK_COLUMNS_SQL}
                    from public.unit_tasks
                    where unit_id = %s
                      and section_id = %s
                    order by position asc, id
                    """,
                    (unit_id, section_id),
                )
                rows = cur.fetchall() or []
        return [_task_row_to_dict(r) for r in rows]

    def create_task(
        self,
        unit_id: str,
        section_id: str,
        author_id: str,
        *,
        instruction_md: str,
        criteria: List[str],
        hints_md: str | None,
        due_at,
        max_attempts: int | None,
    ) -> dict:
        """Create a task at the next position within the section."""
        if not instruction_md or not isinstance(instruction_md, str):
            raise ValueError("invalid_instruction_md")
        instruction = instruction_md.strip()
        if not instruction:
            raise ValueError("invalid_instruction_md")
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
                cur.execute(
                    "select id from public.unit_sections where id = %s and unit_id = %s for update",
                    (section_id, unit_id),
                )
                sec_row = cur.fetchone()
                if not sec_row:
                    raise LookupError("section_not_found")
                cur.execute(
                    "select id from public.unit_tasks where section_id = %s for update",
                    (section_id,),
                )
                cur.execute(
                    "select coalesce(max(position), 0) + 1 from public.unit_tasks where section_id = %s",
                    (section_id,),
                )
                next_pos = int(cur.fetchone()[0])
                cur.execute(
                    f"""
                    insert into public.unit_tasks (
                      unit_id, section_id, instruction_md, criteria, hints_md, due_at, max_attempts, position
                    )
                    values (%s, %s, %s, %s, %s, %s, %s, %s)
                    returning {_TASK_COLUMNS_SQL}
                    """,
                    (unit_id, section_id, instruction, criteria, hints_md, due_at, max_attempts, next_pos),
                )
                row = cur.fetchone()
                if not row:
                    raise RuntimeError("unit_tasks insert returned no row")
                conn.commit()
        return _task_row_to_dict(row)

    def update_task(
        self,
        unit_id: str,
        section_id: str,
        task_id: str,
        author_id: str,
        *,
        instruction_md=_UNSET,
        criteria=_UNSET,
        hints_md=_UNSET,
        due_at=_UNSET,
        max_attempts=_UNSET,
    ) -> Optional[dict]:
        """Update mutable task fields when owned by the caller."""
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
                cur.execute(
                    f"""
                    select {_TASK_COLUMNS_SQL}
                    from public.unit_tasks
                    where id = %s
                      and unit_id = %s
                      and section_id = %s
                    for update
                    """,
                    (task_id, unit_id, section_id),
                )
                existing = cur.fetchone()
                if not existing:
                    return None
                updates = []
                params: List[object] = []
                if instruction_md is not _UNSET:
                    updates.append("instruction_md")
                    params.append(instruction_md)
                if criteria is not _UNSET:
                    updates.append("criteria")
                    params.append(criteria)
                if hints_md is not _UNSET:
                    updates.append("hints_md")
                    params.append(hints_md)
                if due_at is not _UNSET:
                    updates.append("due_at")
                    params.append(due_at)
                if max_attempts is not _UNSET:
                    updates.append("max_attempts")
                    params.append(max_attempts)
                if not updates:
                    conn.rollback()
                    return _task_row_to_dict(existing)
                try:
                    from psycopg import sql as _sql  # type: ignore

                    assignments = [_sql.SQL("{} = %s").format(_sql.Identifier(col)) for col in updates]
                    params.extend([task_id, unit_id, section_id])
                    stmt = _sql.SQL(
                        f"""
                        update public.unit_tasks
                        set {{assign}}
                        where id = %s
                          and unit_id = %s
                          and section_id = %s
                        returning {_TASK_COLUMNS_SQL}
                        """
                    ).format(assign=_sql.SQL(", ").join(assignments))
                    cur.execute(stmt, params)
                except Exception:
                    params = list(params[:-3]) + [task_id, unit_id, section_id]
                    cols = ", ".join([f"{col} = %s" for col in updates])
                    cur.execute(
                        f"""
                        update public.unit_tasks
                        set {cols}
                        where id = %s
                          and unit_id = %s
                          and section_id = %s
                        returning {_TASK_COLUMNS_SQL}
                        """,
                        params,
                    )
                row = cur.fetchone()
                if not row:
                    conn.rollback()
                    return None
                conn.commit()
        return _task_row_to_dict(row)

    def delete_task(self, unit_id: str, section_id: str, task_id: str, author_id: str) -> bool:
        """Delete a task and resequence remaining positions."""
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
                cur.execute(
                    """
                    select id
                    from public.unit_tasks
                    where id = %s
                      and unit_id = %s
                      and section_id = %s
                    for update
                    """,
                    (task_id, unit_id, section_id),
                )
                row = cur.fetchone()
                if not row:
                    return False
                cur.execute(
                    "delete from public.unit_tasks where id = %s and unit_id = %s and section_id = %s",
                    (task_id, unit_id, section_id),
                )
                cur.execute(
                    """
                    with ordered as (
                      select id, row_number() over (order by position asc, id) as rn
                      from public.unit_tasks
                      where section_id = %s
                    )
                    update public.unit_tasks t
                    set position = o.rn
                    from ordered o
                    where t.id = o.id
                    """,
                    (section_id,),
                )
                conn.commit()
                return True

    def reorder_section_tasks(
        self,
        unit_id: str,
        section_id: str,
        author_id: str,
        task_ids: List[str],
    ) -> List[dict]:
        """Atomically reorder tasks owned by the caller."""
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
                cur.execute(
                    """
                    select id::text
                    from public.unit_tasks
                    where unit_id = %s
                      and section_id = %s
                    order by position asc, id
                    """,
                    (unit_id, section_id),
                )
                existing = [row[0] for row in (cur.fetchall() or [])]
                if not existing:
                    raise ValueError("task_mismatch")
                if set(existing) != set(task_ids) or len(existing) != len(task_ids):
                    raise ValueError("task_mismatch")
                cur.execute("set constraints unit_tasks_section_id_position_key deferred")
                orderings = list(range(1, len(task_ids) + 1))
                cur.execute(
                    """
                    with new_order as (
                      select tid, ord from unnest(%s::uuid[], %s::int[]) as t(tid, ord)
                    )
                    update public.unit_tasks ut
                    set position = n.ord
                    from new_order n
                    where ut.id = n.tid
                      and ut.section_id = %s
                      and ut.unit_id = %s
                    """,
                    (task_ids, orderings, section_id, unit_id),
                )
                cur.execute(
                    f"""
                    select {_TASK_COLUMNS_SQL}
                    from public.unit_tasks
                    where unit_id = %s
                      and section_id = %s
                    order by position asc, id
                    """,
                    (unit_id, section_id),
                )
                rows = cur.fetchall() or []
                conn.commit()
        return [_task_row_to_dict(r) for r in rows]

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
        """Reorder modules for a course owned by `owner_sub`.

        Why:
            Persist the new order without relying on deferrable constraints so
            deployments that missed the deferrable migration still behave
            correctly.

        Behavior:
            - Validates the requested set matches the course modules exactly.
            - Two-phase update inside a single transaction to preserve uniqueness:
              (1) Temporarily bump all positions in the course by N to avoid collisions.
              (2) Assign final contiguous positions 1..N in the requested order.

        Permissions:
            RLS enforced via `set_config('app.current_sub', owner_sub, true)`.
            Caller must be the course owner; otherwise, RLS hides rows and
            validation fails appropriately.
        """
        if not module_ids:
            raise ValueError("empty_reorder")
        try:
            normalized_ids = [str(UUID(str(mid))) for mid in module_ids]
        except (ValueError, TypeError) as exc:
            # Contract uses plural form
            raise ValueError("invalid_module_ids") from exc
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
                # Phase 1: bump all positions in the target course by N to avoid
                # temporary uniqueness collisions on (course_id, position).
                bump = len(module_ids)
                cur.execute(
                    "update public.course_modules set position = position + %s where course_id = %s",
                    (bump, course_id),
                )
                # Phase 2: assign final positions 1..N in requested order.
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

    def delete_course_module_owned(self, course_id: str, module_id: str, owner_sub: str) -> bool:
        """Delete a course module owned by `owner_sub` and resequence positions.

        Why:
            Keep contiguous ordering (1..n) after deletions to simplify the UI
            and avoid gaps in positions.

        Behavior:
            - Returns True when the row is visible and deleted; False when the
              row is not visible (not found or not owned).

        Security:
            - `set_config('app.current_sub', ...)` engages RLS policies to
              restrict visibility to course owners.
        """
        try:
            _ = str(UUID(str(module_id)))
        except (ValueError, TypeError):
            # Let the web layer map invalid UUID path params; here we just ensure
            # consistent behavior when called directly.
            pass
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, true)", (owner_sub,))
                # Lock the target row to maintain a stable resequencing base
                cur.execute(
                    "select id from public.course_modules where id = %s and course_id = %s for update",
                    (module_id, course_id),
                )
                row = cur.fetchone()
                if not row:
                    return False
                cur.execute(
                    "delete from public.course_modules where id = %s and course_id = %s",
                    (module_id, course_id),
                )
                # Resequence remaining modules contiguously
                cur.execute(
                    """
                    with ordered as (
                      select id, row_number() over (order by position asc, id) as rn
                      from public.course_modules
                      where course_id = %s
                    )
                    update public.course_modules m
                    set position = o.rn
                    from ordered o
                    where m.id = o.id
                    """,
                    (course_id,),
                )
                conn.commit()
                return True

    def set_module_section_visibility(
        self,
        course_id: str,
        module_id: str,
        section_id: str,
        owner_sub: str,
        visible: bool,
    ) -> dict:
        """Set the release state for a section inside a course module.

        Parameters:
            course_id: Identifier of the course that owns the module.
            module_id: Identifier of the course module to mutate.
            section_id: Identifier of the section whose visibility changes.
            owner_sub: Subject identifier of the teacher invoking the toggle.
            visible: Target visibility flag (`True` releases the section).

        Behavior:
            - Validates module ownership and section membership within the unit.
            - Upserts a row in `module_section_releases`, recording `released_by`.

        Permissions:
            Caller must own the course; enforced via `set_config('app.current_sub', ...)`
            and the RLS policies on `course_modules`, `unit_sections`, and
            `module_section_releases`.

        Raises:
            LookupError: When the module or section does not exist for this course.
            PermissionError: When RLS denies access (non-owner).
        """
        released_at = datetime.now(timezone.utc) if visible else None
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, true)", (owner_sub,))
                cur.execute(
                    """
                    select unit_id::text
                    from public.course_modules
                    where id = %s
                      and course_id = %s
                    """,
                    (module_id, course_id),
                )
                module_row = cur.fetchone()
                if not module_row:
                    raise LookupError("module_not_found")
                unit_id = module_row[0]
                # Restrict to sections that belong to the module's unit to avoid cross-unit leakage.
                cur.execute(
                    """
                    select id::text
                    from public.unit_sections
                    where id = %s
                      and unit_id = %s
                    """,
                    (section_id, unit_id),
                )
                section_row = cur.fetchone()
                if not section_row:
                    raise LookupError("section_not_in_module")
                try:
                    cur.execute(
                        """
                        insert into public.module_section_releases (
                            course_module_id,
                            section_id,
                            visible,
                            released_at,
                            released_by
                        )
                        values (%s, %s, %s, %s, %s)
                        on conflict (course_module_id, section_id)
                        do update set
                            visible = excluded.visible,
                            released_at = excluded.released_at,
                            released_by = excluded.released_by
                        returning
                            course_module_id::text,
                            section_id::text,
                            visible,
                            to_char(released_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                            released_by
                        """,
                        (module_id, section_id, visible, released_at, owner_sub),
                    )
                except Exception as exc:
                    # Map typical RLS denials (e.g., policy violations) to PermissionError
                    # to ensure the web layer returns 403 rather than 500.
                    if getattr(exc, "sqlstate", None) in {"42501"}:  # insufficient_privilege
                        raise PermissionError("rls_denied")
                    # Fallback: re-raise for upstream handling
                    raise
                result = cur.fetchone()
                conn.commit()
        if not result:
            raise LookupError("visibility_update_failed")
        return {
            "course_module_id": result[0],
            "section_id": result[1],
            "visible": bool(result[2]),
            "released_at": _iso(result[3]) if result[3] is not None else None,
            "released_by": result[4],
        }

    def list_module_section_releases_owned(self, course_id: str, module_id: str, owner_sub: str) -> list[dict]:
        """List release records for sections within a course module owned by `owner_sub`.

        Security:
            - Sets `app.current_sub` to the owner for RLS.
            - Verifies that the module belongs to the given course and that the
              course is owned by `owner_sub`.
        """
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, true)", (owner_sub,))
                # Verify ownership by joining courses
                cur.execute(
                    """
                    select m.id::text
                      from public.course_modules m
                      join public.courses c on c.id = m.course_id
                     where m.id = %s
                       and m.course_id = %s
                       and c.teacher_id = coalesce(current_setting('app.current_sub', true), '')
                    """,
                    (module_id, course_id),
                )
                row = cur.fetchone()
                if not row:
                    raise LookupError("module_not_found")

                # Fetch release rows for the module
                cur.execute(
                    """
                    select course_module_id::text,
                           section_id::text,
                           visible,
                           to_char(released_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                           released_by
                      from public.module_section_releases
                     where course_module_id = %s
                     order by section_id asc
                    """,
                    (module_id,),
                )
                rows = cur.fetchall()
        result: list[dict] = []
        for r in rows:
            result.append(
                {
                    "course_module_id": r[0],
                    "section_id": r[1],
                    "visible": bool(r[2]),
                    "released_at": _iso(r[3]) if r[3] is not None else None,
                    "released_by": r[4],
                }
            )
        return result

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
