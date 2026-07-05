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

import sys
from typing import Any, List, Tuple, Optional, Dict, Sequence
import os
import re
import logging
from datetime import datetime, timezone
from urllib.parse import urlparse
from uuid import UUID

from backend.teaching import repo_row_mappers as _repo_row_mappers
from backend.teaching import repo_live_queries as _repo_live_queries
from backend.teaching import repo_material_queries as _repo_material_queries
from backend.teaching import repo_task_queries as _repo_task_queries

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
    try:
        from psycopg.types.json import Json  # type: ignore
    except Exception:  # pragma: no cover - optional dependency
        Json = None  # type: ignore

LOG = logging.getLogger(__name__)
_TASK_COLUMNS_SQL = _repo_row_mappers.TASK_COLUMNS_SQL
_task_row_to_dict = _repo_row_mappers.task_row_to_dict
_compute_average_score_from_analysis = _repo_row_mappers.compute_average_score_from_analysis
_MATERIAL_COLUMNS_SQL = _repo_row_mappers.MATERIAL_COLUMNS_SQL
_material_row_to_dict = _repo_row_mappers.material_row_to_dict


def _default_app_login_dsn() -> str:
    """Supabase-local fallback DSN that uses the env-specific login role."""

    host = os.getenv("TEST_DB_HOST", "127.0.0.1")
    port = os.getenv("TEST_DB_PORT", "54322")
    user = os.getenv("APP_DB_USER", "gustav_app")
    password = os.getenv("APP_DB_PASSWORD", "CHANGE_ME_DEV")
    if not user or user == "gustav_limited":
        raise RuntimeError(
            "APP_DB_USER must refer to the login role that is IN ROLE gustav_limited "
            "(e.g. gustav_app). Run `make db-login-user` to provision it."
        )
    return f"postgresql://{user}:{password}@{host}:{port}/postgres"


def _dsn() -> str:
    """Resolve the DSN for DB access with env-aware fallbacks."""
    env = (os.getenv("GUSTAV_ENV", "dev") or "dev").lower()
    candidates = [
        os.getenv("TEACHING_DATABASE_URL"),
        os.getenv("TEACHING_DB_URL"),
        os.getenv("RLS_TEST_DSN"),
        os.getenv("DATABASE_URL"),
        os.getenv("SUPABASE_DB_URL"),
    ]
    if env not in {"prod", "production", "stage", "staging"}:
        candidates.append(_default_app_login_dsn())
    for dsn in candidates:
        if dsn:
            return dsn
    raise RuntimeError("Database DSN unavailable for DBTeachingRepo")


def _iso(ts) -> str:
    # Expect timestamptz; convert to ISO string via SQL or fetch as text
    # We fetch via to_char at query time for predictability across drivers.
    return str(ts)


def _safe_int(value: object) -> int | None:
    try:
        return int(value)
    except Exception:
        return None

_UNSET = object()


def _is_unset(value: object) -> bool:
    """Return True for this module's sentinel or a reloaded materials sentinel."""

    if value is _UNSET:
        return True
    if type(value) is object:
        return True
    for module_name in ("backend.teaching.services.materials",):
        module = sys.modules.get(module_name)
        if module is not None and value is getattr(module, "_UNSET", None):
            return True
    return False

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
        # Optional elevated DSN for guarded fallbacks in tests/local dev
        # Prefer explicit test/prod service DSNs; fall back to sessions DSN often present in docker-compose
        self._service_dsn = (
            os.getenv("RLS_TEST_SERVICE_DSN")
            or os.getenv("SERVICE_ROLE_DSN")
            or os.getenv("SESSION_TEST_DSN")
            or os.getenv("SESSION_DATABASE_URL")
        )
        # Enforce limited-role semantics by default. Allow override explicitly for dev/tests.
        allow_override = str(os.getenv("ALLOW_SERVICE_DSN_FOR_TESTING", "")).lower() == "true"
        if not allow_override:
            # If the username is not literally the limited role, verify role membership at runtime.
            user = self._dsn_username(self._dsn)
            if user != "gustav_limited":
                try:
                    import psycopg  # type: ignore
                    with psycopg.connect(self._dsn) as _conn:
                        with _conn.cursor() as _cur:
                            _cur.execute("select pg_has_role(current_user, 'gustav_limited', 'member')")
                            ok = bool((_cur.fetchone() or [False])[0])
                            if not ok:
                                raise RuntimeError(
                                    "TeachingRepo requires a login that is IN ROLE gustav_limited (RLS)."
                                )
                except Exception as e:
                    # Re-raise with a clear message to aid developer setup
                    raise RuntimeError(
                        f"TeachingRepo DSN verification failed: {e}. Ensure your DB user is IN ROLE gustav_limited."
                    )

    @staticmethod
    def _service_fallback_allowed() -> bool:
        """Return True iff a service-role fallback is explicitly allowed in a non-prod env.

        Rules:
            - Requires ALLOW_SERVICE_DSN_FOR_TESTING=true
            - And environment must be test/dev/local (GUSTAV_ENV in {test, dev, development, local, ci})
              or running under pytest (PYTEST_CURRENT_TEST present).
        """
        allow_flag = (os.getenv("ALLOW_SERVICE_DSN_FOR_TESTING", "").lower() == "true")
        if not allow_flag:
            return False
        env = (os.getenv("GUSTAV_ENV", "").strip().lower())
        if env in {"test", "dev", "development", "local", "ci"}:
            return True
        # Heuristic for test context
        if os.getenv("PYTEST_CURRENT_TEST"):
            return True
        return False

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
                           unit_type,
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
                "unit_type": r[1],
                "title": r[2],
                "summary": r[3],
                "author_id": r[4],
                "created_at": r[5],
                "updated_at": r[6],
            }
            for r in rows
        ]

    def create_unit(self, *, title: str, summary: Optional[str], author_id: str, unit_type: Optional[str] = None) -> dict:
        """
        Persist a unit for the given author.

        Behavior:
            - Enforces simple validation (non-empty title, summary length).
            - Sets RLS context so only the author can mutate the row.
        """
        norm_type = (unit_type or "linear").strip().lower()
        if norm_type not in {"linear", "modular"}:
            raise ValueError("invalid_unit_type")
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
                    insert into public.units (unit_type, title, summary, author_id)
                    values (%s, %s, %s, %s)
                    returning id::text,
                              unit_type,
                              title,
                              summary,
                              author_id,
                              to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                              to_char(updated_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
                    """,
                    (norm_type, title, summary, author_id),
                )
                row = cur.fetchone()
                # Modular units require at least one phase. Create a default Phase 1
                # to keep the API usable even before a dedicated phase editor exists.
                if row and norm_type == "modular":
                    cur.execute(
                        """
                        insert into public.unit_phases (unit_id, title, position)
                        values (%s::uuid, %s, %s)
                        """,
                        (row[0], "Phase 1", 1),
                    )
                conn.commit()
        return {
            "id": row[0],
            "unit_type": row[1],
            "title": row[2],
            "summary": row[3],
            "author_id": row[4],
            "created_at": row[5],
            "updated_at": row[6],
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
                                 unit_type,
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
                                 unit_type,
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
            "unit_type": row[1],
            "title": row[2],
            "summary": row[3],
            "author_id": row[4],
            "created_at": row[5],
            "updated_at": row[6],
        }

    def get_unit_for_author(self, unit_id: str, author_id: str) -> Optional[dict]:
        """Fetch a unit enforcing author ownership through RLS."""
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
                cur.execute(
                    """
                    select id::text,
                           unit_type,
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
            "unit_type": row[1],
            "title": row[2],
            "summary": row[3],
            "author_id": row[4],
            "created_at": row[5],
            "updated_at": row[6],
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

    # --- Unit phases (modular units) -----------------------------------------

    def list_unit_phases_for_author(self, unit_id: str, author_id: str) -> List[dict]:
        """List phases of a modular unit authored by the caller."""
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
                cur.execute("select unit_type from public.units where id = %s and author_id = %s", (unit_id, author_id))
                unit_row = cur.fetchone()
                if not unit_row:
                    raise PermissionError("unit_not_found_or_not_owned")
                unit_type = str(unit_row[0] or "linear").strip().lower()
                if unit_type != "modular":
                    raise ValueError("invalid_unit_type")
                cur.execute(
                    """
                    select id::text,
                           unit_id::text,
                           title,
                           position,
                           to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                           to_char(updated_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
                      from public.unit_phases
                     where unit_id = %s
                     order by position asc, id asc
                    """,
                    (unit_id,),
                )
                rows = cur.fetchall() or []
        return [
            {
                "id": r[0],
                "unit_id": r[1],
                "title": r[2],
                "position": int(r[3] or 1),
                "created_at": r[4],
                "updated_at": r[5],
            }
            for r in rows
        ]

    def create_unit_phase(self, unit_id: str, title: str, author_id: str) -> dict:
        """Create a new phase at the next position within a modular unit."""
        title = (title or "").strip()
        if not title or len(title) > 200:
            raise ValueError("invalid_title")
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
                cur.execute(
                    "select unit_type from public.units where id = %s and author_id = %s for update",
                    (unit_id, author_id),
                )
                unit_row = cur.fetchone()
                if not unit_row:
                    raise PermissionError("unit_not_found_or_not_owned")
                unit_type = str(unit_row[0] or "linear").strip().lower()
                if unit_type != "modular":
                    raise ValueError("invalid_unit_type")
                cur.execute("select coalesce(max(position), 0) + 1 from public.unit_phases where unit_id = %s", (unit_id,))
                next_pos = int(cur.fetchone()[0])
                cur.execute(
                    """
                    insert into public.unit_phases (unit_id, title, position)
                    values (%s::uuid, %s, %s)
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
            "position": int(row[3] or 1),
            "created_at": row[4],
            "updated_at": row[5],
        }

    def update_unit_phase_title(self, unit_id: str, phase_id: str, title: str, author_id: str) -> Optional[dict]:
        """Rename a phase within a modular unit authored by the caller."""
        if title is None:
            raise ValueError("invalid_title")
        t = (title or "").strip()
        if not t or len(t) > 200:
            raise ValueError("invalid_title")
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
                cur.execute("select unit_type from public.units where id = %s and author_id = %s", (unit_id, author_id))
                unit_row = cur.fetchone()
                if not unit_row:
                    raise PermissionError("unit_not_found_or_not_owned")
                unit_type = str(unit_row[0] or "linear").strip().lower()
                if unit_type != "modular":
                    raise ValueError("invalid_unit_type")
                cur.execute(
                    """
                    update public.unit_phases
                    set title = %s
                    where id = %s and unit_id = %s
                    returning id::text,
                              unit_id::text,
                              title,
                              position,
                              to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                              to_char(updated_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
                    """,
                    (t, phase_id, unit_id),
                )
                row = cur.fetchone()
                if not row:
                    return None
                conn.commit()
        return {
            "id": row[0],
            "unit_id": row[1],
            "title": row[2],
            "position": int(row[3] or 1),
            "created_at": row[4],
            "updated_at": row[5],
        }

    def reorder_unit_phases_owned(self, unit_id: str, author_id: str, phase_ids: List[str]) -> List[dict]:
        """Atomically reorder phases for a modular unit the author owns."""
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
                cur.execute("select unit_type from public.units where id = %s and author_id = %s", (unit_id, author_id))
                unit_row = cur.fetchone()
                if not unit_row:
                    raise PermissionError("unit_not_found_or_not_owned")
                unit_type = str(unit_row[0] or "linear").strip().lower()
                if unit_type != "modular":
                    raise ValueError("invalid_unit_type")

                cur.execute(
                    """
                    select id::text
                    from public.unit_phases
                    where unit_id = %s
                    order by position asc, id
                    """,
                    (unit_id,),
                )
                existing = [row[0] for row in (cur.fetchall() or [])]
                if not existing:
                    raise ValueError("phase_mismatch")
                existing_set = set(existing)
                submitted_set = set(phase_ids)
                if submitted_set != existing_set or len(phase_ids) != len(existing):
                    extra = submitted_set - existing_set
                    if extra:
                        cur.execute("select count(*) from public.unit_phases where id = any(%s)", (list(extra),))
                        c = cur.fetchone()
                        if c and int(c[0]) > 0:
                            raise LookupError("phase_not_in_unit")
                    raise ValueError("phase_mismatch")

                cur.execute("set constraints unit_phases_unit_id_position_key deferred")
                orderings = list(range(1, len(phase_ids) + 1))
                cur.execute(
                    """
                    with new_order as (
                      select pid, ord from unnest(%s::uuid[], %s::int[]) as t(pid, ord)
                    )
                    update public.unit_phases p
                    set position = n.ord
                    from new_order n
                    where p.id = n.pid
                      and p.unit_id = %s
                    """,
                    (phase_ids, orderings, unit_id),
                )
                cur.execute(
                    """
                    select id::text,
                           unit_id::text,
                           title,
                           position,
                           to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                           to_char(updated_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
                      from public.unit_phases
                     where unit_id = %s
                     order by position asc, id asc
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
                "position": int(r[3] or 1),
                "created_at": r[4],
                "updated_at": r[5],
            }
            for r in rows
        ]

    # --- Unit modules (modular units; Option B) ------------------------------

    def list_unit_modules_for_author(self, *, unit_id: str, author_id: str) -> List[dict]:
        """List modules (module_id) for a modular unit authored by the caller.

        Option B:
            Modules are graph nodes stored in `public.unit_modules` (module_id),
            and map 1:1 to a content container `public.unit_sections` via
            `unit_modules.section_id`.
        """
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
                cur.execute("select unit_type from public.units where id = %s and author_id = %s", (unit_id, author_id))
                unit_row = cur.fetchone()
                if not unit_row:
                    raise PermissionError("unit_not_found_or_not_owned")
                unit_type = str(unit_row[0] or "linear").strip().lower()
                if unit_type != "modular":
                    raise ValueError("invalid_unit_type")
                cur.execute(
                    """
                    select um.id::text,
                           um.unit_id::text,
                           um.section_id::text,
                           um.phase_id::text,
                           um.position_in_phase,
                           um.required_prereq_count,
                           s.title
                      from public.unit_modules um
                      join public.unit_sections s on s.id = um.section_id
                      join public.unit_phases p on p.id = um.phase_id
                     where um.unit_id = %s
                     order by p.position asc, um.position_in_phase asc, um.id asc
                    """,
                    (unit_id,),
                )
                rows = cur.fetchall() or []
        return [
            {
                "id": r[0],
                "unit_id": r[1],
                "section_id": r[2],
                "phase_id": r[3],
                "position_in_phase": int(r[4] or 1),
                "required_prereq_count": int(r[5] or 0),
                "title": r[6],
            }
            for r in rows
        ]

    def get_unit_module_for_author(self, *, unit_id: str, module_id: str, author_id: str) -> Optional[dict]:
        """Resolve module metadata for a modular unit authored by the caller.

        Returns:
            Dict with keys: id (module_id), unit_id, section_id, phase_id, title.
            None when the module is not visible to the caller.
        """
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
                cur.execute("select unit_type from public.units where id = %s and author_id = %s", (unit_id, author_id))
                unit_row = cur.fetchone()
                if not unit_row:
                    raise PermissionError("unit_not_found_or_not_owned")
                unit_type = str(unit_row[0] or "linear").strip().lower()
                if unit_type != "modular":
                    raise ValueError("invalid_unit_type")
                cur.execute(
                    """
                    select um.id::text,
                           um.unit_id::text,
                           um.section_id::text,
                           um.phase_id::text,
                           um.position_in_phase,
                           um.required_prereq_count,
                           s.title
                      from public.unit_modules um
                      join public.unit_sections s on s.id = um.section_id
                     where um.unit_id = %s
                       and um.id = %s::uuid
                    """,
                    (unit_id, module_id),
                )
                row = cur.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "unit_id": row[1],
            "section_id": row[2],
            "phase_id": row[3],
            "position_in_phase": int(row[4] or 1),
            "required_prereq_count": int(row[5] or 0),
            "title": row[6],
        }

    def list_unit_module_edges_for_author(self, *, unit_id: str, author_id: str) -> List[dict]:
        """List dependency edges for a modular unit authored by the caller.

        Returns:
            List of dicts: { "from": <module_id>, "to": <module_id> }.

        Security:
            Activates RLS by setting `app.current_sub = author_id`.
        """
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
                cur.execute("select unit_type from public.units where id = %s and author_id = %s", (unit_id, author_id))
                unit_row = cur.fetchone()
                if not unit_row:
                    raise PermissionError("unit_not_found_or_not_owned")
                unit_type = str(unit_row[0] or "linear").strip().lower()
                if unit_type != "modular":
                    raise ValueError("invalid_unit_type")
                cur.execute(
                    """
                    select from_module_id::text, to_module_id::text
                      from public.unit_module_edges
                     where unit_id = %s::uuid
                     order by from_module_id asc, to_module_id asc
                    """,
                    (unit_id,),
                )
                rows = cur.fetchall() or []
        return [{"from": r[0], "to": r[1]} for r in rows]

    def create_unit_module_for_author(self, *, unit_id: str, phase_id: str, title: str, author_id: str) -> dict:
        """Create a module in the given phase (Option B).

        Option B:
            A module is a graph node (`public.unit_modules.id`) that maps 1:1
            to a content container (`public.unit_sections.id`) via
            `unit_modules.section_id`.

        Behavior:
            - Validates unit ownership and that the unit is modular.
            - Validates the phase belongs to the unit.
            - Creates a new `unit_sections` row (append position within unit).
            - Creates the `unit_modules` row in the given phase (append within phase).

        Returns:
            Dict with module_id + backing section_id:
            {id, unit_id, section_id, phase_id, position_in_phase, required_prereq_count, title}
        """
        t = (title or "").strip()
        if not t or len(t) > 200:
            raise ValueError("invalid_title")

        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
                cur.execute(
                    "select unit_type from public.units where id = %s and author_id = %s for update",
                    (unit_id, author_id),
                )
                unit_row = cur.fetchone()
                if not unit_row:
                    raise PermissionError("unit_not_found_or_not_owned")
                unit_type = str(unit_row[0] or "linear").strip().lower()
                if unit_type != "modular":
                    raise ValueError("invalid_unit_type")

                cur.execute(
                    "select 1 from public.unit_phases where id = %s::uuid and unit_id = %s::uuid",
                    (phase_id, unit_id),
                )
                if not cur.fetchone():
                    raise LookupError("phase_not_found")

                # Append a backing section to keep existing content tables intact.
                cur.execute("select coalesce(max(position), 0) + 1 from public.unit_sections where unit_id = %s", (unit_id,))
                next_section_pos = int(cur.fetchone()[0])
                cur.execute(
                    """
                    insert into public.unit_sections (unit_id, title, position)
                    values (%s::uuid, %s, %s)
                    returning id::text
                    """,
                    (unit_id, t, next_section_pos),
                )
                section_id = (cur.fetchone() or [None])[0]
                if not section_id:
                    raise RuntimeError("unit_sections insert returned no id")

                # Append module within the target phase.
                cur.execute(
                    """
                    select coalesce(max(position_in_phase), 0) + 1
                    from public.unit_modules
                    where phase_id = %s::uuid
                    """,
                    (phase_id,),
                )
                next_pos_in_phase = int(cur.fetchone()[0])
                cur.execute(
                    """
                    insert into public.unit_modules (unit_id, section_id, phase_id, position_in_phase)
                    values (%s::uuid, %s::uuid, %s::uuid, %s)
                    returning id::text, required_prereq_count
                    """,
                    (unit_id, section_id, phase_id, next_pos_in_phase),
                )
                module_row = cur.fetchone()
                if not module_row:
                    raise RuntimeError("unit_modules insert returned no row")
                module_id, required_prereq_count = module_row[0], int(module_row[1] or 0)
                conn.commit()
        return {
            "id": module_id,
            "unit_id": unit_id,
            "section_id": section_id,
            "phase_id": phase_id,
            "position_in_phase": next_pos_in_phase,
            "required_prereq_count": required_prereq_count,
            "title": t,
        }

    def create_unit_module_edge_for_author(
        self, *, unit_id: str, from_module_id: str, to_module_id: str, author_id: str
    ) -> dict:
        """Create a directed dependency edge `from -> to` (author only).

        Option 1 (k-of-n default):
            `unit_modules.required_prereq_count` stores the configured `k`.

            When the stored `k` equals the current number of incoming edges `n`
            (k==n), we treat the module as being in "auto" mode and keep `k`
            synced to `n` as edges are added/removed.

            This yields a sensible default (new module with 0 edges => k==0),
            while still allowing manual overrides (set k to a different value).
        """
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
                cur.execute("select unit_type from public.units where id = %s and author_id = %s", (unit_id, author_id))
                unit_row = cur.fetchone()
                if not unit_row:
                    raise PermissionError("unit_not_found_or_not_owned")
                unit_type = str(unit_row[0] or "linear").strip().lower()
                if unit_type != "modular":
                    raise ValueError("invalid_unit_type")

                # Lock the target module row so concurrent edge edits serialize.
                cur.execute(
                    """
                    select required_prereq_count
                      from public.unit_modules
                     where unit_id = %s::uuid
                       and id = %s::uuid
                     for update
                    """,
                    (unit_id, to_module_id),
                )
                mod_row = cur.fetchone()
                current_k = int((mod_row or [0])[0] or 0)

                # Capture current incoming edge count (n) before inserting.
                cur.execute(
                    """
                    select count(*)
                      from public.unit_module_edges
                     where unit_id = %s::uuid
                       and to_module_id = %s::uuid
                    """,
                    (unit_id, to_module_id),
                )
                old_n = int((cur.fetchone() or [0])[0] or 0)

                cur.execute(
                    """
                    insert into public.unit_module_edges (unit_id, from_module_id, to_module_id)
                    values (%s::uuid, %s::uuid, %s::uuid)
                    returning from_module_id::text, to_module_id::text
                    """,
                    (unit_id, from_module_id, to_module_id),
                )
                row = cur.fetchone()
                if not row:
                    raise RuntimeError("unit_module_edges insert returned no row")

                # Auto mode: when k==n, keep k in sync with n.
                if current_k == old_n:
                    new_n = old_n + 1
                    cur.execute(
                        """
                        update public.unit_modules
                           set required_prereq_count = %s
                         where unit_id = %s::uuid
                           and id = %s::uuid
                        """,
                        (new_n, unit_id, to_module_id),
                    )

                conn.commit()
        return {"from": row[0], "to": row[1]}

    def delete_unit_module_edge_for_author(
        self, *, unit_id: str, from_module_id: str, to_module_id: str, author_id: str
    ) -> bool:
        """Delete a directed dependency edge `from -> to` (author only)."""
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
                cur.execute("select unit_type from public.units where id = %s and author_id = %s", (unit_id, author_id))
                unit_row = cur.fetchone()
                if not unit_row:
                    raise PermissionError("unit_not_found_or_not_owned")
                unit_type = str(unit_row[0] or "linear").strip().lower()
                if unit_type != "modular":
                    raise ValueError("invalid_unit_type")

                # Lock the target module row so edge + k updates remain consistent.
                cur.execute(
                    """
                    select required_prereq_count
                      from public.unit_modules
                     where unit_id = %s::uuid
                       and id = %s::uuid
                     for update
                    """,
                    (unit_id, to_module_id),
                )
                mod_row = cur.fetchone()
                current_k = int((mod_row or [0])[0] or 0)

                cur.execute(
                    """
                    select count(*)
                      from public.unit_module_edges
                     where unit_id = %s::uuid
                       and to_module_id = %s::uuid
                    """,
                    (unit_id, to_module_id),
                )
                old_n = int((cur.fetchone() or [0])[0] or 0)

                cur.execute(
                    """
                    delete from public.unit_module_edges
                    where unit_id = %s::uuid
                      and from_module_id = %s::uuid
                      and to_module_id = %s::uuid
                    """,
                    (unit_id, from_module_id, to_module_id),
                )
                deleted = int(cur.rowcount or 0)

                if deleted > 0 and current_k == old_n:
                    new_n = max(old_n - 1, 0)
                    cur.execute(
                        """
                        update public.unit_modules
                           set required_prereq_count = %s
                         where unit_id = %s::uuid
                           and id = %s::uuid
                        """,
                        (new_n, unit_id, to_module_id),
                    )

                conn.commit()
        return deleted > 0


    def reorder_unit_phase_modules_owned(
        self, *, unit_id: str, phase_id: str, author_id: str, module_ids: List[str]
    ) -> List[dict]:
        """Reorder (and move) modules within a phase (author only).

        Semantics:
            - The provided `module_ids` define the desired top-to-bottom order
              for the target phase.
            - Modules listed that currently live in another phase are moved
              into the target phase.
            - Modules already in the target phase but not mentioned are
              appended afterwards (stable order).
            - All affected phases are compacted to positions 1..n.

        Safety:
            A DB constraint trigger validates that existing edges remain valid
            after the move/reorder. Violations raise CHECK VIOLATION at commit.
        """
        if not module_ids:
            raise ValueError("empty_module_ids")
        if len(module_ids) != len(set(module_ids)):
            raise ValueError("duplicate_module_ids")

        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
                cur.execute("select unit_type from public.units where id = %s and author_id = %s", (unit_id, author_id))
                unit_row = cur.fetchone()
                if not unit_row:
                    raise PermissionError("unit_not_found_or_not_owned")
                unit_type = str(unit_row[0] or "linear").strip().lower()
                if unit_type != "modular":
                    raise ValueError("invalid_unit_type")

                cur.execute("select 1 from public.unit_phases where id = %s::uuid and unit_id = %s::uuid", (phase_id, unit_id))
                if not cur.fetchone():
                    raise LookupError("phase_not_found")

                # Resolve current phase placement for all requested modules.
                cur.execute(
                    """
                    select um.id::text, um.phase_id::text
                      from public.unit_modules um
                     where um.unit_id = %s::uuid
                       and um.id = any(%s::uuid[])
                    """,
                    (unit_id, module_ids),
                )
                rows = cur.fetchall() or []
                if len(rows) != len(module_ids):
                    raise LookupError("module_not_in_unit")
                original_phase_by_module = {r[0]: r[1] for r in rows}
                desired_set = set(module_ids)

                # Append existing modules in the target phase that are not mentioned.
                cur.execute(
                    """
                    select um.id::text
                      from public.unit_modules um
                      join public.unit_phases p on p.id = um.phase_id
                     where um.unit_id = %s::uuid
                       and um.phase_id = %s::uuid
                     order by um.position_in_phase asc, um.id asc
                    """,
                    (unit_id, phase_id),
                )
                existing_in_phase = [r[0] for r in (cur.fetchall() or [])]
                extras = [mid for mid in existing_in_phase if mid not in desired_set]
                full_order = list(module_ids) + extras

                # Deferrable unique constraint enables transactional reorder updates.
                cur.execute("set constraints unit_modules_phase_id_position_in_phase_key deferred")
                orderings = list(range(1, len(full_order) + 1))
                cur.execute(
                    """
                    with new_order as (
                      select mid, ord
                        from unnest(%s::uuid[], %s::int[]) as t(mid, ord)
                    )
                    update public.unit_modules um
                       set phase_id = %s::uuid,
                           position_in_phase = n.ord
                      from new_order n
                     where um.unit_id = %s::uuid
                       and um.id = n.mid
                    """,
                    (full_order, orderings, phase_id, unit_id),
                )

                # Compact phases that lost moved modules (keep stable relative order).
                moved_from_phases = sorted(
                    {original_phase_by_module[mid] for mid in module_ids if original_phase_by_module.get(mid) != phase_id}
                )
                for src_phase_id in moved_from_phases:
                    cur.execute(
                        """
                        select um.id::text
                          from public.unit_modules um
                         where um.unit_id = %s::uuid
                           and um.phase_id = %s::uuid
                         order by um.position_in_phase asc, um.id asc
                        """,
                        (unit_id, src_phase_id),
                    )
                    remaining = [r[0] for r in (cur.fetchall() or [])]
                    if not remaining:
                        continue
                    orderings = list(range(1, len(remaining) + 1))
                    cur.execute(
                        """
                        with new_order as (
                          select mid, ord
                            from unnest(%s::uuid[], %s::int[]) as t(mid, ord)
                        )
                        update public.unit_modules um
                           set position_in_phase = n.ord
                          from new_order n
                         where um.unit_id = %s::uuid
                           and um.id = n.mid
                        """,
                        (remaining, orderings, unit_id),
                    )

                # Return the updated module list for the target phase.
                cur.execute(
                    """
                    select um.id::text,
                           um.unit_id::text,
                           um.section_id::text,
                           um.phase_id::text,
                           um.position_in_phase,
                           um.required_prereq_count,
                           s.title
                      from public.unit_modules um
                      join public.unit_sections s on s.id = um.section_id
                     where um.unit_id = %s::uuid
                       and um.phase_id = %s::uuid
                     order by um.position_in_phase asc, um.id asc
                    """,
                    (unit_id, phase_id),
                )
                out_rows = cur.fetchall() or []
                conn.commit()
        return [
            {
                "id": r[0],
                "unit_id": r[1],
                "section_id": r[2],
                "phase_id": r[3],
                "position_in_phase": int(r[4] or 1),
                "required_prereq_count": int(r[5] or 0),
                "title": r[6],
            }
            for r in out_rows
        ]

    def update_unit_module_owned(
        self,
        *,
        unit_id: str,
        module_id: str,
        author_id: str,
        title=_UNSET,
        required_prereq_count=_UNSET,
    ) -> Optional[dict]:
        """Update module settings inside a modular unit (author only).

        Option B:
            The visible module title lives on the backing section row
            (`public.unit_sections.title`). The unlock setting
            `required_prereq_count` lives on `public.unit_modules`.

        Parameters:
            unit_id: Modular unit id.
            module_id: Unit module id (graph node).
            author_id: Caller sub; must own the unit.
            title: New title (1..200) or `_UNSET` to keep current title.
            required_prereq_count: New k (>= 0) or `_UNSET` to keep current value.

        Returns:
            Updated module dict (including section_id for internal wiring) or
            None when the module is not visible to the caller.
        """
        if title is _UNSET and required_prereq_count is _UNSET:
            raise ValueError("empty_payload")

        t: str | None = None
        if title is not _UNSET:
            t = (title or "").strip()
            if not t or len(t) > 200:
                raise ValueError("invalid_title")

        k: int | None = None
        if required_prereq_count is not _UNSET:
            if required_prereq_count is None or isinstance(required_prereq_count, bool) or not isinstance(required_prereq_count, int):
                raise ValueError("invalid_required_prereq_count")
            k = int(required_prereq_count)
            if k < 0:
                raise ValueError("invalid_required_prereq_count")

        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
                cur.execute("select unit_type from public.units where id = %s and author_id = %s", (unit_id, author_id))
                unit_row = cur.fetchone()
                if not unit_row:
                    raise PermissionError("unit_not_found_or_not_owned")
                unit_type = str(unit_row[0] or "linear").strip().lower()
                if unit_type != "modular":
                    raise ValueError("invalid_unit_type")

                cur.execute(
                    """
                    select um.section_id::text,
                           um.phase_id::text,
                           um.position_in_phase,
                           um.required_prereq_count,
                           s.title
                      from public.unit_modules um
                      join public.unit_sections s on s.id = um.section_id
                     where um.unit_id = %s::uuid
                       and um.id = %s::uuid
                     for update
                    """,
                    (unit_id, module_id),
                )
                row = cur.fetchone()
                if not row:
                    return None

                section_id = row[0]
                phase_id = row[1]
                pos_in_phase = int(row[2] or 1)
                current_k = int(row[3] or 0)
                current_title = str(row[4] or "")

                if t is not None:
                    cur.execute(
                        """
                        update public.unit_sections
                        set title = %s
                        where id = %s::uuid
                          and unit_id = %s::uuid
                        """,
                        (t, section_id, unit_id),
                    )
                    current_title = t

                if k is not None:
                    cur.execute(
                        """
                        update public.unit_modules
                        set required_prereq_count = %s
                        where unit_id = %s::uuid
                          and id = %s::uuid
                        """,
                        (k, unit_id, module_id),
                    )
                    current_k = k

                conn.commit()
        return {
            "id": module_id,
            "unit_id": unit_id,
            "section_id": section_id,
            "phase_id": phase_id,
            "position_in_phase": pos_in_phase,
            "required_prereq_count": current_k,
            "title": current_title,
        }

    def update_unit_module_title(self, *, unit_id: str, module_id: str, title: str, author_id: str) -> Optional[dict]:
        """Rename a module inside a modular unit (author only).

        Option B:
            The visible module title is stored on the backing section row
            (`public.unit_sections.title`). This method updates that title.

        Returns:
            Updated module dict (including section_id for internal wiring) or
            None when the module is not visible to the caller.
        """
        t = (title or "").strip()
        if not t or len(t) > 200:
            raise ValueError("invalid_title")

        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
                cur.execute("select unit_type from public.units where id = %s and author_id = %s", (unit_id, author_id))
                unit_row = cur.fetchone()
                if not unit_row:
                    raise PermissionError("unit_not_found_or_not_owned")
                unit_type = str(unit_row[0] or "linear").strip().lower()
                if unit_type != "modular":
                    raise ValueError("invalid_unit_type")

                cur.execute(
                    """
                    select um.section_id::text,
                           um.phase_id::text,
                           um.position_in_phase,
                           um.required_prereq_count
                      from public.unit_modules um
                     where um.unit_id = %s::uuid
                       and um.id = %s::uuid
                     for update
                    """,
                    (unit_id, module_id),
                )
                row = cur.fetchone()
                if not row:
                    return None
                section_id, phase_id, pos_in_phase, req_prereq = row[0], row[1], int(row[2] or 1), int(row[3] or 0)

                cur.execute(
                    """
                    update public.unit_sections
                    set title = %s
                    where id = %s::uuid
                      and unit_id = %s::uuid
                    """,
                    (t, section_id, unit_id),
                )
                conn.commit()
        return {
            "id": module_id,
            "unit_id": unit_id,
            "section_id": section_id,
            "phase_id": phase_id,
            "position_in_phase": pos_in_phase,
            "required_prereq_count": req_prereq,
            "title": t,
        }

    def _clamp_required_prereq_count_to_incoming(
        self,
        *,
        cur,
        unit_id: str,
        target_module_ids: list[str],
    ) -> None:
        """Clamp k-of-n setting to current incoming edge count for target modules.

        Why:
            Module/phase deletions remove edges via FK cascades. When a removed
            prerequisite was part of a target module's incoming set, the target
            `required_prereq_count` must be reduced to remain in the valid range
            `0..incoming_count`.
        """
        module_ids = sorted({mid for mid in (target_module_ids or []) if mid})
        if not module_ids:
            return
        cur.execute(
            """
            with incoming as (
              select um.id as module_id,
                     coalesce((
                       select count(*)
                       from public.unit_module_edges e
                       where e.unit_id = um.unit_id
                         and e.to_module_id = um.id
                     ), 0)::int as incoming_count
              from public.unit_modules um
              where um.unit_id = %s::uuid
                and um.id = any(%s::uuid[])
            )
            update public.unit_modules um
            set required_prereq_count = least(um.required_prereq_count, incoming.incoming_count)
            from incoming
            where um.unit_id = %s::uuid
              and um.id = incoming.module_id
              and um.required_prereq_count > incoming.incoming_count
            """,
            (unit_id, module_ids, unit_id),
        )

    def delete_unit_module_for_author(self, *, unit_id: str, module_id: str, author_id: str) -> bool:
        """Delete a module and its backing content (author only).

        Option B:
            Deletes the backing section row, which cascades to:
              - unit_modules (via FK on unit_modules.section_id)
              - unit_tasks/unit_materials etc. (section-owned content)
              - unit_module_edges (via FK on from/to module ids)

        Additionally resequences remaining modules within the affected phase to
        keep positions contiguous (1..n) for stable edge validation and UX.
        """
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
                cur.execute("select unit_type from public.units where id = %s and author_id = %s", (unit_id, author_id))
                unit_row = cur.fetchone()
                if not unit_row:
                    raise PermissionError("unit_not_found_or_not_owned")
                unit_type = str(unit_row[0] or "linear").strip().lower()
                if unit_type != "modular":
                    raise ValueError("invalid_unit_type")

                cur.execute(
                    """
                    select distinct to_module_id::text
                    from public.unit_module_edges
                    where unit_id = %s::uuid
                      and from_module_id = %s::uuid
                    """,
                    (unit_id, module_id),
                )
                affected_targets = [r[0] for r in (cur.fetchall() or []) if r and r[0]]

                cur.execute(
                    """
                    select um.section_id::text, um.phase_id::text
                    from public.unit_modules um
                    where um.unit_id = %s::uuid
                      and um.id = %s::uuid
                    for update
                    """,
                    (unit_id, module_id),
                )
                row = cur.fetchone()
                if not row:
                    return False
                section_id, phase_id = row[0], row[1]

                cur.execute(
                    """
                    delete from public.unit_sections
                    where id = %s::uuid
                      and unit_id = %s::uuid
                    """,
                    (section_id, unit_id),
                )
                if int(cur.rowcount or 0) == 0:
                    return False

                # Keep section positions contiguous (used by linear units; harmless for modular).
                cur.execute(
                    """
                    with ordered as (
                      select id, row_number() over (order by position asc, id) as rn
                      from public.unit_sections
                      where unit_id = %s::uuid
                    )
                    update public.unit_sections u
                    set position = o.rn
                    from ordered o
                    where u.id = o.id
                    """,
                    (unit_id,),
                )

                # Resequence remaining modules in the phase (important for edge direction checks).
                cur.execute("set constraints unit_modules_phase_id_position_in_phase_key deferred")
                cur.execute(
                    """
                    with ordered as (
                      select id, row_number() over (order by position_in_phase asc, id) as rn
                      from public.unit_modules
                      where unit_id = %s::uuid
                        and phase_id = %s::uuid
                    )
                    update public.unit_modules um
                    set position_in_phase = o.rn
                    from ordered o
                    where um.id = o.id
                    """,
                    (unit_id, phase_id),
                )

                self._clamp_required_prereq_count_to_incoming(
                    cur=cur,
                    unit_id=unit_id,
                    target_module_ids=affected_targets,
                )

                conn.commit()
                return True

    def delete_unit_phase_for_author(self, *, unit_id: str, phase_id: str, author_id: str) -> bool:
        """Delete a phase and all contained modules/edges/content (author only).

        Why:
            Teachers need to restructure a modular unit quickly. Deleting a
            phase should remove all its modules and their content to avoid
            orphaned sections (Option B).

        Behavior:
            - Deletes backing sections for all modules in the phase.
            - Deletes the phase row.
            - Resequences remaining phase positions to keep them contiguous.
        """
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, true)", (author_id,))
                cur.execute(
                    "select unit_type from public.units where id = %s and author_id = %s for update",
                    (unit_id, author_id),
                )
                unit_row = cur.fetchone()
                if not unit_row:
                    raise PermissionError("unit_not_found_or_not_owned")
                unit_type = str(unit_row[0] or "linear").strip().lower()
                if unit_type != "modular":
                    raise ValueError("invalid_unit_type")

                cur.execute(
                    """
                    select id::text
                    from public.unit_phases
                    where id = %s::uuid
                      and unit_id = %s::uuid
                    for update
                    """,
                    (phase_id, unit_id),
                )
                phase_row = cur.fetchone()
                if not phase_row:
                    return False

                cur.execute(
                    """
                    select um.id::text,
                           um.section_id::text
                    from public.unit_modules um
                    where um.unit_id = %s::uuid
                      and um.phase_id = %s::uuid
                    """,
                    (unit_id, phase_id),
                )
                rows = cur.fetchall() or []
                module_ids = [r[0] for r in rows if r and r[0]]
                section_ids = [r[1] for r in rows if len(r) > 1 and r[1]]

                affected_targets: list[str] = []
                if module_ids:
                    cur.execute(
                        """
                        select distinct to_module_id::text
                        from public.unit_module_edges
                        where unit_id = %s::uuid
                          and from_module_id = any(%s::uuid[])
                        """,
                        (unit_id, module_ids),
                    )
                    affected_targets = [r[0] for r in (cur.fetchall() or []) if r and r[0]]

                if section_ids:
                    cur.execute(
                        """
                        delete from public.unit_sections
                        where unit_id = %s::uuid
                          and id = any(%s::uuid[])
                        """,
                        (unit_id, section_ids),
                    )
                    # Resequence section positions (linear-only, but keeps unit tidy).
                    cur.execute(
                        """
                        with ordered as (
                          select id, row_number() over (order by position asc, id) as rn
                          from public.unit_sections
                          where unit_id = %s::uuid
                        )
                        update public.unit_sections u
                        set position = o.rn
                        from ordered o
                        where u.id = o.id
                        """,
                        (unit_id,),
                    )

                cur.execute(
                    """
                    delete from public.unit_phases
                    where id = %s::uuid
                      and unit_id = %s::uuid
                    """,
                    (phase_id, unit_id),
                )
                if int(cur.rowcount or 0) == 0:
                    return False

                # Resequence remaining phases to keep (unit_id, position) contiguous.
                cur.execute("set constraints unit_phases_unit_id_position_key deferred")
                cur.execute(
                    """
                    with ordered as (
                      select id, row_number() over (order by position asc, id) as rn
                      from public.unit_phases
                      where unit_id = %s::uuid
                    )
                    update public.unit_phases p
                    set position = o.rn
                    from ordered o
                    where p.id = o.id
                    """,
                    (unit_id,),
                )

                self._clamp_required_prereq_count_to_incoming(
                    cur=cur,
                    unit_id=unit_id,
                    target_module_ids=affected_targets,
                )
                conn.commit()
                return True

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
                cur.execute("select id::text, unit_type from public.units where id = %s for update", (unit_id,))
                unit_row = cur.fetchone()
                if not unit_row:
                    raise PermissionError("unit_not_found_or_not_owned")
                unit_type = str(unit_row[1] or "linear").strip().lower()
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

                # Option B: modular units create a 1:1 module record with its own UUID.
                if unit_type == "modular":
                    cur.execute(
                        """
                        select id::text
                        from public.unit_phases
                        where unit_id = %s::uuid
                        order by position asc, id asc
                        limit 1
                        for update
                        """,
                        (unit_id,),
                    )
                    phase_row = cur.fetchone()
                    if not phase_row:
                        # Defensive self-healing: keep modular section creation
                        # available even if all phases were deleted earlier.
                        cur.execute(
                            """
                            insert into public.unit_phases (unit_id, title, position)
                            values (%s::uuid, %s, %s)
                            returning id::text
                            """,
                            (unit_id, "Phase 1", 1),
                        )
                        created_phase_row = cur.fetchone()
                        phase_id = (created_phase_row or [None])[0]
                        if not phase_id:
                            raise RuntimeError("modular_unit_missing_phase")
                    else:
                        phase_id = phase_row[0]
                    cur.execute(
                        """
                        select coalesce(max(position_in_phase), 0) + 1
                        from public.unit_modules
                        where phase_id = %s::uuid
                        """,
                        (phase_id,),
                    )
                    next_pos_in_phase = int(cur.fetchone()[0])
                    cur.execute(
                        """
                        insert into public.unit_modules (unit_id, section_id, phase_id, position_in_phase)
                        values (%s::uuid, %s::uuid, %s::uuid, %s)
                        """,
                        (unit_id, row[0], phase_id, next_pos_in_phase),
                    )
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
    # --- Section materials -----------------------------------------------------
    def list_materials_for_section_owned(self, unit_id: str, section_id: str, author_id: str) -> List[dict]:
        return _repo_material_queries.list_materials_for_section_owned(
            dsn=self._dsn,
            psycopg_module=psycopg,
            unit_id=unit_id,
            section_id=section_id,
            author_id=author_id,
        )

    def create_markdown_material(self, unit_id: str, section_id: str, author_id: str, *, title: str, body_md: str) -> dict:
        return _repo_material_queries.create_markdown_material(
            dsn=self._dsn,
            psycopg_module=psycopg,
            unique_violation_cls=UniqueViolation,
            unit_id=unit_id,
            section_id=section_id,
            author_id=author_id,
            title=title,
            body_md=body_md,
        )

    def get_material_owned(self, unit_id: str, section_id: str, material_id: str, author_id: str) -> Optional[dict]:
        return _repo_material_queries.get_material_owned(
            dsn=self._dsn,
            psycopg_module=psycopg,
            unit_id=unit_id,
            section_id=section_id,
            material_id=material_id,
            author_id=author_id,
        )

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
        return _repo_material_queries.update_material(
            dsn=self._dsn,
            psycopg_module=psycopg,
            unit_id=unit_id,
            section_id=section_id,
            material_id=material_id,
            author_id=author_id,
            title=title,
            body_md=body_md,
            alt_text=alt_text,
        )

    def delete_material(self, unit_id: str, section_id: str, material_id: str, author_id: str) -> bool:
        return _repo_material_queries.delete_material(
            dsn=self._dsn,
            psycopg_module=psycopg,
            unit_id=unit_id,
            section_id=section_id,
            material_id=material_id,
            author_id=author_id,
        )

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
        return _repo_material_queries.create_file_upload_intent(
            dsn=self._dsn,
            psycopg_module=psycopg,
            unit_id=unit_id,
            section_id=section_id,
            author_id=author_id,
            intent_id=intent_id,
            material_id=material_id,
            storage_key=storage_key,
            filename=filename,
            mime_type=mime_type,
            size_bytes=size_bytes,
            expires_at=expires_at,
        )

    def get_upload_intent_owned(
        self,
        intent_id: str,
        unit_id: str,
        section_id: str,
        author_id: str,
    ) -> Optional[Dict[str, Any]]:
        return _repo_material_queries.get_upload_intent_owned(
            dsn=self._dsn,
            psycopg_module=psycopg,
            intent_id=intent_id,
            unit_id=unit_id,
            section_id=section_id,
            author_id=author_id,
        )

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
        return _repo_material_queries.finalize_upload_intent_create_material(
            dsn=self._dsn,
            psycopg_module=psycopg,
            intent_id=intent_id,
            unit_id=unit_id,
            section_id=section_id,
            author_id=author_id,
            title=title,
            alt_text=alt_text,
            sha256=sha256,
        )

    def reorder_section_materials(
        self,
        unit_id: str,
        section_id: str,
        author_id: str,
        material_ids: List[str],
    ) -> List[dict]:
        return _repo_material_queries.reorder_section_materials(
            dsn=self._dsn,
            psycopg_module=psycopg,
            unit_id=unit_id,
            section_id=section_id,
            author_id=author_id,
            material_ids=material_ids,
        )

    # --- Section tasks --------------------------------------------------------
    def list_tasks_for_section_owned(self, unit_id: str, section_id: str, author_id: str) -> List[dict]:
        return _repo_task_queries.list_tasks_for_section_owned(
            dsn=self._dsn,
            psycopg_module=psycopg,
            unit_id=unit_id,
            section_id=section_id,
            author_id=author_id,
        )

    def create_task(
        self,
        unit_id: str,
        section_id: str,
        author_id: str,
        *,
        instruction_md: str,
        criteria: List[str],
        teacher_context_md: str | None,
        due_at,
        max_attempts: int | None,
        kind: str,
        h5p_content_id: str | None,
        h5p_display_options: dict[str, Any],
    ) -> dict:
        return _repo_task_queries.create_task(
            dsn=self._dsn,
            psycopg_module=psycopg,
            json_adapter=Json,
            unit_id=unit_id,
            section_id=section_id,
            author_id=author_id,
            instruction_md=instruction_md,
            criteria=criteria,
            teacher_context_md=teacher_context_md,
            due_at=due_at,
            max_attempts=max_attempts,
            kind=kind,
            h5p_content_id=h5p_content_id,
            h5p_display_options=h5p_display_options,
        )

    def update_task(
        self,
        unit_id: str,
        section_id: str,
        task_id: str,
        author_id: str,
        *,
        instruction_md=_UNSET,
        criteria=_UNSET,
        teacher_context_md=_UNSET,
        due_at=_UNSET,
        max_attempts=_UNSET,
        kind=_UNSET,
        h5p_content_id=_UNSET,
        h5p_display_options=_UNSET,
    ) -> Optional[dict]:
        return _repo_task_queries.update_task(
            dsn=self._dsn,
            psycopg_module=psycopg,
            json_adapter=Json,
            unit_id=unit_id,
            section_id=section_id,
            task_id=task_id,
            author_id=author_id,
            instruction_md=instruction_md,
            criteria=criteria,
            teacher_context_md=teacher_context_md,
            due_at=due_at,
            max_attempts=max_attempts,
            kind=kind,
            h5p_content_id=h5p_content_id,
            h5p_display_options=h5p_display_options,
        )

    def delete_task(self, unit_id: str, section_id: str, task_id: str, author_id: str) -> bool:
        return _repo_task_queries.delete_task(
            dsn=self._dsn,
            psycopg_module=psycopg,
            unit_id=unit_id,
            section_id=section_id,
            task_id=task_id,
            author_id=author_id,
        )

    def reorder_section_tasks(
        self,
        unit_id: str,
        section_id: str,
        author_id: str,
        task_ids: List[str],
    ) -> List[dict]:
        return _repo_task_queries.reorder_section_tasks(
            dsn=self._dsn,
            psycopg_module=psycopg,
            unit_id=unit_id,
            section_id=section_id,
            author_id=author_id,
            task_ids=task_ids,
        )

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

    def list_course_units_for_owner(self, course_id: str, owner_sub: str) -> List[dict]:
        """Return attached units for a course owned by `owner_sub`.

        Why:
            The teacher student-overview needs a course-scoped unit list that is
            independent from author-only repository methods. Ordering follows the
            course-module order seen by teachers in the UI.
        """
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, true)", (owner_sub,))
                cur.execute(
                    """
                    select u.id::text,
                           u.title,
                           m.position
                      from public.course_modules m
                      join public.courses c
                        on c.id = m.course_id
                      join public.units u
                        on u.id = m.unit_id
                     where m.course_id = %s
                       and c.teacher_id = coalesce(current_setting('app.current_sub', true), '')
                     order by m.position asc, m.id
                    """,
                    (course_id,),
                )
                rows = cur.fetchall() or []
        return [
            {
                "id": r[0],
                "title": r[1],
                "position": int(r[2]) if r[2] is not None else 0,
            }
            for r in rows
        ]

    def course_has_member(self, course_id: str, owner_sub: str, student_sub: str) -> bool:
        """Check membership using the existing owner-scoped roster helper."""
        page_size = 50
        offset = 0
        while True:
            page = self.list_members_for_owner(course_id, owner_sub, limit=page_size, offset=offset)
            if not page:
                return False
            if any(str(member_sub) == str(student_sub) for member_sub, _joined_at in page):
                return True
            if len(page) < page_size:
                return False
            offset += page_size

    def list_tasks_for_course_unit_owner(self, course_id: str, unit_id: str, owner_sub: str) -> List[dict]:
        return _repo_task_queries.list_tasks_for_course_unit_owner(
            dsn=self._dsn,
            psycopg_module=psycopg,
            course_id=course_id,
            unit_id=unit_id,
            owner_sub=owner_sub,
        )

    def list_tasks_for_course_units_owner(
        self,
        course_id: str,
        unit_ids: Sequence[str],
        owner_sub: str,
    ) -> List[dict]:
        return _repo_task_queries.list_tasks_for_course_units_owner(
            dsn=self._dsn,
            psycopg_module=psycopg,
            course_id=course_id,
            unit_ids=unit_ids,
            owner_sub=owner_sub,
        )

    def list_latest_submission_aggregates_for_owner(
        self,
        *,
        course_id: str,
        owner_sub: str,
        student_sub: str,
        unit_ids: Sequence[str],
    ) -> List[dict]:
        return _repo_task_queries.list_latest_submission_aggregates_for_owner(
            dsn=self._dsn,
            psycopg_module=psycopg,
            course_id=course_id,
            owner_sub=owner_sub,
            student_sub=student_sub,
            unit_ids=unit_ids,
        )

    def list_unit_latest_submission_aggregates_for_owner(
        self,
        *,
        course_id: str,
        unit_id: str,
        owner_sub: str,
        student_subs: Sequence[str],
    ) -> List[dict]:
        return _repo_live_queries.list_unit_latest_submission_aggregates_for_owner(
            dsn=self._dsn,
            psycopg_module=psycopg,
            course_id=course_id,
            unit_id=unit_id,
            owner_sub=owner_sub,
            student_subs=student_subs,
        )

    def list_unit_live_helper_rows(
        self,
        *,
        owner_sub: str,
        course_id: str,
        unit_id: str,
        updated_since_dt: datetime | None,
        limit: int,
        offset: int,
    ) -> list[dict[str, Any]]:
        return _repo_live_queries.list_unit_live_helper_rows(
            dsn=self._dsn,
            psycopg_module=psycopg,
            owner_sub=owner_sub,
            course_id=course_id,
            unit_id=unit_id,
            updated_since_dt=updated_since_dt,
            limit=limit,
            offset=offset,
        )

    def list_unit_live_submission_state_by_task(
        self,
        *,
        owner_sub: str,
        course_id: str,
        task_ids_by_student: dict[str, list[str]],
    ) -> dict[tuple[str, str], dict[str, Any]]:
        return _repo_live_queries.list_unit_live_submission_state_by_task(
            dsn=self._dsn,
            psycopg_module=psycopg,
            owner_sub=owner_sub,
            course_id=course_id,
            task_ids_by_student=task_ids_by_student,
        )

    def list_unit_live_average_scores_by_submission_id(
        self,
        *,
        owner_sub: str,
        submission_ids_by_student: dict[str, list[str]],
    ) -> dict[str, float | None]:
        return _repo_live_queries.list_unit_live_average_scores_by_submission_id(
            dsn=self._dsn,
            psycopg_module=psycopg,
            owner_sub=owner_sub,
            submission_ids_by_student=submission_ids_by_student,
        )

    def list_unit_live_summary_fallback_rows(
        self,
        *,
        owner_sub: str,
        course_id: str,
        task_ids: list[str],
        member_subs: list[str],
    ) -> list[tuple[str, str, str]]:
        return _repo_live_queries.list_unit_live_summary_fallback_rows(
            dsn=self._dsn,
            psycopg_module=psycopg,
            owner_sub=owner_sub,
            course_id=course_id,
            task_ids=task_ids,
            member_subs=member_subs,
        )

    def list_unit_live_task_ids_for_student(
        self,
        *,
        owner_sub: str,
        course_id: str,
        student_sub: str,
        task_ids: list[str],
    ) -> list[tuple[str, str]]:
        return _repo_live_queries.list_unit_live_task_ids_for_student(
            dsn=self._dsn,
            psycopg_module=psycopg,
            owner_sub=owner_sub,
            course_id=course_id,
            student_sub=student_sub,
            task_ids=task_ids,
        )

    def list_unit_live_latest_changed_at_by_pairs(
        self,
        *,
        owner_sub: str,
        course_id: str,
        task_ids_by_student: dict[str, list[str]],
    ) -> dict[tuple[str, str], Any]:
        return _repo_live_queries.list_unit_live_latest_changed_at_by_pairs(
            dsn=self._dsn,
            psycopg_module=psycopg,
            owner_sub=owner_sub,
            course_id=course_id,
            task_ids_by_student=task_ids_by_student,
        )

    def list_unit_live_delta_fallback_rows(
        self,
        *,
        owner_sub: str,
        course_id: str,
        changed_since: datetime,
        limit: int,
        offset: int,
    ) -> list[tuple[str, str, Any]]:
        return _repo_live_queries.list_unit_live_delta_fallback_rows(
            dsn=self._dsn,
            psycopg_module=psycopg,
            owner_sub=owner_sub,
            course_id=course_id,
            changed_since=changed_since,
            limit=limit,
            offset=offset,
        )

    def get_statement_timestamp(self, owner_sub: str) -> str | None:
        return _repo_live_queries.get_statement_timestamp(
            dsn=self._dsn,
            psycopg_module=psycopg,
            owner_sub=owner_sub,
        )

    def list_submission_pairs_for_students(
        self,
        *,
        owner_sub: str,
        course_id: str,
        student_subs: list[str],
        task_ids: list[str],
    ) -> set[tuple[str, str]]:
        """Return submission pairs for all provided students and tasks."""
        if not student_subs or not task_ids:
            return set()

        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, true)", (owner_sub,))
                cur.execute(
                    """
                    select distinct student_sub::text, task_id::text
                      from public.learning_submissions
                     where course_id = %s
                       and student_sub = any(%s)
                       and task_id = any(%s)
                    """,
                    (course_id, student_subs, task_ids),
                )
                return {(str(raw_student_sub), str(raw_task_id)) for raw_student_sub, raw_task_id in (cur.fetchall() or [])}


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

    def list_ai_usage_events_for_owner(
        self,
        *,
        course_id: str,
        owner_sub: str,
        from_at: datetime | None = None,
        to_at: datetime | None = None,
        unit_id: str | None = None,
        task_id: str | None = None,
        student_sub: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return owner-scoped AI usage event rows for course aggregation.

        Why:
            The API read-model needs flexible grouping, but no SECURITY DEFINER
            aggregate helper. This method sets `app.current_sub` and reads the
            RLS-protected event table directly.

        Security:
            Caller must be the course owner. SQL repeats the owner guard and
            RLS enforces the same boundary on `ai_usage_events`.
        """
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, true)", (owner_sub,))
                cur.execute(
                    """
                    select e.student_sub,
                           e.model,
                           e.stage,
                           e.modality,
                           e.call_kind,
                           e.usage_known,
                           e.input_tokens,
                           e.output_tokens,
                           e.total_tokens
                      from public.ai_usage_events e
                      join public.courses c on c.id = e.course_id
                     where e.course_id = %s::uuid
                       and c.teacher_id = coalesce(current_setting('app.current_sub', true), '')
                       and (%s::timestamptz is null or e.occurred_at >= %s::timestamptz)
                       and (%s::timestamptz is null or e.occurred_at < %s::timestamptz)
                       and (%s::text is null or e.unit_id::text = %s::text)
                       and (%s::text is null or e.task_id::text = %s::text)
                       and (%s::text is null or e.student_sub = %s::text)
                     order by e.occurred_at asc, e.id asc
                    """,
                    (
                        course_id,
                        from_at,
                        from_at,
                        to_at,
                        to_at,
                        unit_id,
                        unit_id,
                        task_id,
                        task_id,
                        student_sub,
                        student_sub,
                    ),
                )
                rows = cur.fetchall() or []
        return [
            {
                "student_sub": r[0],
                "model": r[1],
                "stage": r[2],
                "modality": r[3],
                "call_kind": r[4],
                "usage_known": bool(r[5]),
                "input_tokens": r[6],
                "output_tokens": r[7],
                "total_tokens": r[8],
            }
            for r in rows
        ]

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
        """Remove a membership for a course owned by `owner_sub`.

        Why:
            Teachers must be able to unenroll students from their own courses.
            Under RLS, deletion is allowed only when `app.current_sub` matches
            the course owner. Some environments may still block the delete
            (e.g., drifted policies). To keep UX reliable while preserving
            security, we try under the limited role first. If RLS blocks the
            row (policy drift), we invoke a SECURITY DEFINER helper that
            verifies ownership and performs the delete without relying on RLS.
            As a last resort in dev/test, we fall back to a service-role DSN
            only when configured and only after ownership was verified by the
            route.

        Parameters:
            course_id: Target course UUID (text accepted by psycopg parameter).
            owner_sub: Subject identifier of the teacher (OIDC `sub`).
            student_id: Subject identifier of the student to remove.

        Security:
            - First attempt uses the limited-role DSN (RLS enforced).
            - Secondary fallback uses SECURITY DEFINER helper
              `public.remove_course_membership(owner, course, student)`.
            - Optional final fallback uses `SERVICE_ROLE_DSN` (or test variant) to
              execute the delete when RLS prevents it, but the route has
              already verified ownership via a SECURITY DEFINER helper.
        """
        affected = 0
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, true)", (owner_sub,))
                cur.execute(
                    "delete from public.course_memberships where course_id = %s and student_id = %s",
                    (course_id, student_id),
                )
                affected = cur.rowcount or 0
                if affected == 0:
                    # Attempt SECURITY DEFINER helper (ownership already verified by route)
                    try:
                        cur.execute(
                            "select public.remove_course_membership(%s, %s, %s)",
                            (owner_sub, course_id, student_id),
                        )
                        affected = 1  # treat as success when helper executes without error
                    except Exception:
                        affected = 0
                conn.commit()
        # Final fallback (dev/test only): allow service-role DSN when explicitly enabled.
        if affected == 0 and self._service_dsn:
            if not self._service_fallback_allowed():
                # Deny fallback in prod/stage even if the flag is set; log once per call-site.
                LOG.warning(
                    "Service-DSN fallback blocked (env not allowed). Set GUSTAV_ENV in {dev,test,local} to enable for testing."
                )
                return
            # Explicitly allowed in test/dev; log to make audits easier.
            LOG.warning("Using service-DSN fallback for membership delete (test/dev only)")
            try:
                with psycopg.connect(self._service_dsn) as conn2:  # type: ignore[arg-type]
                    with conn2.cursor() as cur2:
                        cur2.execute(
                            "delete from public.course_memberships where course_id = %s and student_id = %s",
                            (course_id, student_id),
                        )
                        conn2.commit()
            except Exception:
                # Intentionally swallow errors in the test-only branch
                pass

    def student_has_course(self, course_id: str, student_sub: str) -> bool:
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, true)", (student_sub,))
                cur.execute(
                    """
                    select exists (
                      select 1
                        from public.course_memberships
                       where course_id = %s
                         and student_id = %s
                    )
                    """,
                    (course_id, student_sub),
                )
                row = cur.fetchone()
        return bool((row or [False])[0])

    def create_concern_box_entry(
        self,
        *,
        course_id: str,
        student_sub: str,
        message_text: str,
        anonymous: bool,
    ) -> dict[str, Any] | None:
        text = (message_text or "").strip()
        if not text:
            raise ValueError("invalid_message_text")
        try:
            with psycopg.connect(self._dsn) as conn:
                with conn.cursor() as cur:
                    cur.execute("select set_config('app.current_sub', %s, true)", (student_sub,))
                    cur.execute(
                        """
                        select id::text,
                               to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
                          from public.create_concern_box_entry(%s, %s::uuid, %s, %s)
                        """,
                        (student_sub, course_id, text, bool(anonymous)),
                    )
                    row = cur.fetchone()
                    conn.commit()
        except Exception:
            return None
        if row is None:
            return None
        return {"id": row[0], "created_at": row[1]}

    def list_concern_box_entries_for_teacher(self, owner_sub: str, scope: str) -> list[dict[str, Any]]:
        archived = scope == "archived"
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, true)", (owner_sub,))
                cur.execute(
                    """
                    select e.id::text,
                           e.course_id::text,
                           c.title,
                           e.student_sub,
                           e.message_text,
                           e.anonymous,
                           to_char(e.created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                           case
                             when e.archived_at is null then null
                             else to_char(e.archived_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
                           end
                      from public.concern_box_entries e
                      join public.courses c on c.id = e.course_id
                     where (e.archived_at is null) = %s
                     order by e.created_at desc, e.id desc
                    """,
                    (not archived,),
                )
                rows = cur.fetchall() or []
        return [
            {
                "id": row[0],
                "course_id": row[1],
                "course_title": row[2],
                "student_sub": row[3],
                "message_text": row[4],
                "anonymous": bool(row[5]),
                "created_at": row[6],
                "archived_at": row[7],
            }
            for row in rows
        ]

    def archive_concern_box_entry_owned(self, entry_id: str, owner_sub: str) -> bool:
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, true)", (owner_sub,))
                cur.execute(
                    """
                    update public.concern_box_entries
                       set archived_at = now(),
                           archived_by = %s
                     where id = %s::uuid
                    """,
                    (owner_sub, entry_id),
                )
                updated = (cur.rowcount or 0) == 1
                conn.commit()
        return updated

    def restore_concern_box_entry_owned(self, entry_id: str, owner_sub: str) -> bool:
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, true)", (owner_sub,))
                cur.execute(
                    """
                    update public.concern_box_entries
                       set archived_at = null,
                           archived_by = null
                     where id = %s::uuid
                    """,
                    (entry_id,),
                )
                updated = (cur.rowcount or 0) == 1
                conn.commit()
        return updated

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
