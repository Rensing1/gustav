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

from functools import wraps
import sys
from typing import Any, List, Tuple, Optional, Dict, Sequence
import os
import re
import logging
from datetime import datetime
from urllib.parse import urlparse

from backend.teaching import repo_row_mappers as _repo_row_mappers
from backend.teaching import repo_live_queries as _repo_live_queries
from backend.teaching import repo_material_queries as _repo_material_queries
from backend.teaching import repo_member_queries as _repo_member_queries
from backend.teaching import repo_section_queries as _repo_section_queries
from backend.teaching import repo_unit_queries as _repo_unit_queries
from backend.teaching import repo_course_module_queries as _repo_course_module_queries
from backend.teaching import repo_concern_box_queries as _repo_concern_box_queries
from backend.teaching import repo_ai_usage_queries as _repo_ai_usage_queries
from backend.teaching import repo_task_queries as _repo_task_queries
from backend.teaching import repo_unit_module_queries as _repo_unit_module_queries
from backend.teaching.errors import TeachingRepositoryUnavailable

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

_DATABASE_OPERATIONAL_ERRORS = (psycopg.OperationalError,) if HAVE_PSYCOPG else ()

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


def _translate_database_failures(cls):
    """Translate connection failures at the Teaching repository boundary.

    DBTeachingRepo has many small public operations. Decorating those methods
    centrally keeps every driver error inside the adapter without leaking a
    PostgreSQL-specific exception into the web application.
    """

    for name, method in list(vars(cls).items()):
        if name.startswith("_") or not callable(method):
            continue

        @wraps(method)
        def guarded(*args, __method=method, **kwargs):
            try:
                return __method(*args, **kwargs)
            except _DATABASE_OPERATIONAL_ERRORS as exc:
                raise TeachingRepositoryUnavailable() from exc

        setattr(cls, name, guarded)
    return cls


@_translate_database_failures
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
                    with psycopg.connect(self._dsn, connect_timeout=3) as _conn:
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

    def check_readiness(self) -> None:
        """Verify that the required PostgreSQL database accepts connections.

        The short timeout keeps the public readiness endpoint responsive while
        Docker or Kubernetes waits for a separately managed Supabase stack.
        No application data is read and the limited application role remains
        subject to the same RLS configuration as normal repository calls.
        """

        with psycopg.connect(self._dsn, connect_timeout=3) as conn:
            with conn.cursor() as cur:
                cur.execute("select 1")
                cur.fetchone()

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
        return _repo_member_queries.list_courses_for_student(
            dsn=self._dsn,
            psycopg_module=psycopg,
            student_id=student_id,
            limit=limit,
            offset=offset,
        )

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
        return _repo_unit_queries.list_units_for_author(
            dsn=self._dsn,
            psycopg_module=psycopg,
            author_id=author_id,
            limit=limit,
            offset=offset,
        )

    def create_unit(self, *, title: str, summary: Optional[str], author_id: str, unit_type: Optional[str] = None) -> dict:
        return _repo_unit_queries.create_unit(
            dsn=self._dsn,
            psycopg_module=psycopg,
            title=title,
            summary=summary,
            author_id=author_id,
            unit_type=unit_type,
        )

    def update_unit_owned(self, unit_id: str, author_id: str, *, title=_UNSET, summary=_UNSET) -> Optional[dict]:
        return _repo_unit_queries.update_unit_owned(
            dsn=self._dsn,
            psycopg_module=psycopg,
            unit_id=unit_id,
            author_id=author_id,
            title=title,
            summary=summary,
        )

    def get_unit_for_author(self, unit_id: str, author_id: str) -> Optional[dict]:
        return _repo_unit_queries.get_unit_for_author(
            dsn=self._dsn,
            psycopg_module=psycopg,
            unit_id=unit_id,
            author_id=author_id,
        )

    def delete_unit_owned(self, unit_id: str, author_id: str) -> bool:
        return _repo_unit_queries.delete_unit_owned(
            dsn=self._dsn,
            psycopg_module=psycopg,
            unit_id=unit_id,
            author_id=author_id,
        )

    def unit_exists_for_author(self, unit_id: str, author_id: str) -> bool:
        return _repo_unit_queries.unit_exists_for_author(
            dsn=self._dsn,
            psycopg_module=psycopg,
            unit_id=unit_id,
            author_id=author_id,
        )

    def unit_exists(self, unit_id: str) -> Optional[bool]:
        return _repo_unit_queries.unit_exists(
            dsn=self._dsn,
            psycopg_module=psycopg,
            unit_id=unit_id,
        )

    def list_unit_phases_for_author(self, unit_id: str, author_id: str) -> List[dict]:
        return _repo_unit_module_queries.list_unit_phases_for_author(
            dsn=self._dsn,
            psycopg_module=psycopg,
            unit_id=unit_id,
            author_id=author_id,
        )

    def create_unit_phase(self, unit_id: str, title: str, author_id: str) -> dict:
        return _repo_unit_module_queries.create_unit_phase(
            dsn=self._dsn,
            psycopg_module=psycopg,
            unit_id=unit_id,
            title=title,
            author_id=author_id,
        )

    def update_unit_phase_title(self, unit_id: str, phase_id: str, title: str, author_id: str) -> Optional[dict]:
        return _repo_unit_module_queries.update_unit_phase_title(
            dsn=self._dsn,
            psycopg_module=psycopg,
            unit_id=unit_id,
            phase_id=phase_id,
            title=title,
            author_id=author_id,
        )

    def reorder_unit_phases_owned(self, unit_id: str, author_id: str, phase_ids: List[str]) -> List[dict]:
        return _repo_unit_module_queries.reorder_unit_phases_owned(
            dsn=self._dsn,
            psycopg_module=psycopg,
            unit_id=unit_id,
            author_id=author_id,
            phase_ids=phase_ids,
        )

    def list_unit_modules_for_author(self, *, unit_id: str, author_id: str) -> List[dict]:
        return _repo_unit_module_queries.list_unit_modules_for_author(
            dsn=self._dsn,
            psycopg_module=psycopg,
            unit_id=unit_id,
            author_id=author_id,
        )

    def get_unit_module_for_author(self, *, unit_id: str, module_id: str, author_id: str) -> Optional[dict]:
        return _repo_unit_module_queries.get_unit_module_for_author(
            dsn=self._dsn,
            psycopg_module=psycopg,
            unit_id=unit_id,
            module_id=module_id,
            author_id=author_id,
        )

    def list_unit_module_edges_for_author(self, *, unit_id: str, author_id: str) -> List[dict]:
        return _repo_unit_module_queries.list_unit_module_edges_for_author(
            dsn=self._dsn,
            psycopg_module=psycopg,
            unit_id=unit_id,
            author_id=author_id,
        )

    def create_unit_module_for_author(self, *, unit_id: str, phase_id: str, title: str, author_id: str) -> dict:
        return _repo_unit_module_queries.create_unit_module_for_author(
            dsn=self._dsn,
            psycopg_module=psycopg,
            unit_id=unit_id,
            phase_id=phase_id,
            title=title,
            author_id=author_id,
        )

    def create_unit_module_edge_for_author(
        self, *, unit_id: str, from_module_id: str, to_module_id: str, author_id: str
    ) -> dict:
        return _repo_unit_module_queries.create_unit_module_edge_for_author(
            dsn=self._dsn,
            psycopg_module=psycopg,
            unit_id=unit_id,
            from_module_id=from_module_id,
            to_module_id=to_module_id,
            author_id=author_id,
        )

    def delete_unit_module_edge_for_author(
        self, *, unit_id: str, from_module_id: str, to_module_id: str, author_id: str
    ) -> bool:
        return _repo_unit_module_queries.delete_unit_module_edge_for_author(
            dsn=self._dsn,
            psycopg_module=psycopg,
            unit_id=unit_id,
            from_module_id=from_module_id,
            to_module_id=to_module_id,
            author_id=author_id,
        )

    def reorder_unit_phase_modules_owned(
        self, *, unit_id: str, phase_id: str, author_id: str, module_ids: List[str]
    ) -> List[dict]:
        return _repo_unit_module_queries.reorder_unit_phase_modules_owned(
            dsn=self._dsn,
            psycopg_module=psycopg,
            unit_id=unit_id,
            phase_id=phase_id,
            author_id=author_id,
            module_ids=module_ids,
        )

    def update_unit_module_owned(
        self,
        *,
        unit_id: str,
        module_id: str,
        author_id: str,
        title=_UNSET,
        required_prereq_count=_UNSET,
    ) -> Optional[dict]:
        return _repo_unit_module_queries.update_unit_module_owned(
            dsn=self._dsn,
            psycopg_module=psycopg,
            unit_id=unit_id,
            module_id=module_id,
            author_id=author_id,
            title=title,
            required_prereq_count=required_prereq_count,
        )

    def update_unit_module_title(self, *, unit_id: str, module_id: str, title: str, author_id: str) -> Optional[dict]:
        return _repo_unit_module_queries.update_unit_module_title(
            dsn=self._dsn,
            psycopg_module=psycopg,
            unit_id=unit_id,
            module_id=module_id,
            title=title,
            author_id=author_id,
        )

    def delete_unit_module_for_author(self, *, unit_id: str, module_id: str, author_id: str) -> bool:
        return _repo_unit_module_queries.delete_unit_module_for_author(
            dsn=self._dsn,
            psycopg_module=psycopg,
            unit_id=unit_id,
            module_id=module_id,
            author_id=author_id,
        )

    def delete_unit_phase_for_author(self, *, unit_id: str, phase_id: str, author_id: str) -> bool:
        return _repo_unit_module_queries.delete_unit_phase_for_author(
            dsn=self._dsn,
            psycopg_module=psycopg,
            unit_id=unit_id,
            phase_id=phase_id,
            author_id=author_id,
        )

    def section_exists_for_author(self, unit_id: str, section_id: str, author_id: str) -> bool:
        return _repo_section_queries.section_exists_for_author(
            dsn=self._dsn,
            psycopg_module=psycopg,
            unit_id=unit_id,
            section_id=section_id,
            author_id=author_id,
        )

    def list_sections_for_author(self, unit_id: str, author_id: str) -> List[dict]:
        return _repo_section_queries.list_sections_for_author(
            dsn=self._dsn,
            psycopg_module=psycopg,
            unit_id=unit_id,
            author_id=author_id,
        )

    def create_section(self, unit_id: str, title: str, author_id: str) -> dict:
        return _repo_section_queries.create_section(
            dsn=self._dsn,
            psycopg_module=psycopg,
            unique_violation_cls=UniqueViolation,
            unit_id=unit_id,
            title=title,
            author_id=author_id,
        )

    def update_section_title(self, unit_id: str, section_id: str, title: str, author_id: str) -> Optional[dict]:
        return _repo_section_queries.update_section_title(
            dsn=self._dsn,
            psycopg_module=psycopg,
            unit_id=unit_id,
            section_id=section_id,
            title=title,
            author_id=author_id,
        )

    def delete_section(self, unit_id: str, section_id: str, author_id: str) -> bool:
        return _repo_section_queries.delete_section(
            dsn=self._dsn,
            psycopg_module=psycopg,
            unit_id=unit_id,
            section_id=section_id,
            author_id=author_id,
        )

    def reorder_unit_sections_owned(self, unit_id: str, author_id: str, section_ids: List[str]) -> List[dict]:
        return _repo_section_queries.reorder_unit_sections_owned(
            dsn=self._dsn,
            psycopg_module=psycopg,
            unit_id=unit_id,
            author_id=author_id,
            section_ids=section_ids,
        )

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
        return _repo_course_module_queries.list_course_modules_for_owner(
            dsn=self._dsn,
            psycopg_module=psycopg,
            course_id=course_id,
            owner_sub=owner_sub,
        )

    def list_course_units_for_owner(self, course_id: str, owner_sub: str) -> List[dict]:
        return _repo_course_module_queries.list_course_units_for_owner(
            dsn=self._dsn,
            psycopg_module=psycopg,
            course_id=course_id,
            owner_sub=owner_sub,
        )

    def course_has_member(self, course_id: str, owner_sub: str, student_sub: str) -> bool:
        return _repo_member_queries.course_has_member(
            dsn=self._dsn,
            psycopg_module=psycopg,
            course_id=course_id,
            owner_sub=owner_sub,
            student_sub=student_sub,
        )

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
        return _repo_course_module_queries.create_course_module_owned(
            dsn=self._dsn,
            psycopg_module=psycopg,
            unique_violation_cls=UniqueViolation,
            course_id=course_id,
            owner_sub=owner_sub,
            unit_id=unit_id,
            context_notes=context_notes,
        )

    def reorder_course_modules_owned(self, course_id: str, owner_sub: str, module_ids: List[str]) -> List[dict]:
        return _repo_course_module_queries.reorder_course_modules_owned(
            dsn=self._dsn,
            psycopg_module=psycopg,
            course_id=course_id,
            owner_sub=owner_sub,
            module_ids=module_ids,
        )

    def delete_course_module_owned(self, course_id: str, module_id: str, owner_sub: str) -> bool:
        return _repo_course_module_queries.delete_course_module_owned(
            dsn=self._dsn,
            psycopg_module=psycopg,
            course_id=course_id,
            module_id=module_id,
            owner_sub=owner_sub,
        )

    def set_module_section_visibility(
        self,
        course_id: str,
        module_id: str,
        section_id: str,
        owner_sub: str,
        visible: bool,
    ) -> dict:
        return _repo_course_module_queries.set_module_section_visibility(
            dsn=self._dsn,
            psycopg_module=psycopg,
            course_id=course_id,
            module_id=module_id,
            section_id=section_id,
            owner_sub=owner_sub,
            visible=visible,
        )

    def list_module_section_releases_owned(self, course_id: str, module_id: str, owner_sub: str) -> list[dict]:
        return _repo_course_module_queries.list_module_section_releases_owned(
            dsn=self._dsn,
            psycopg_module=psycopg,
            course_id=course_id,
            module_id=module_id,
            owner_sub=owner_sub,
        )

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
        return _repo_member_queries.list_members_for_owner(
            dsn=self._dsn,
            psycopg_module=psycopg,
            course_id=course_id,
            owner_sub=owner_sub,
            limit=limit,
            offset=offset,
        )

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
        return _repo_ai_usage_queries.list_ai_usage_events_for_owner(
            dsn=self._dsn,
            psycopg_module=psycopg,
            course_id=course_id,
            owner_sub=owner_sub,
            from_at=from_at,
            to_at=to_at,
            unit_id=unit_id,
            task_id=task_id,
            student_sub=student_sub,
        )

    def add_member_owned(self, course_id: str, owner_sub: str, student_id: str) -> bool:
        return _repo_member_queries.add_member_owned(
            dsn=self._dsn,
            psycopg_module=psycopg,
            course_id=course_id,
            owner_sub=owner_sub,
            student_id=student_id,
        )

    def remove_member_owned(self, course_id: str, owner_sub: str, student_id: str) -> None:
        return _repo_member_queries.remove_member_owned(
            dsn=self._dsn,
            psycopg_module=psycopg,
            service_dsn=self._service_dsn,
            service_fallback_allowed=self._service_fallback_allowed,
            logger=LOG,
            course_id=course_id,
            owner_sub=owner_sub,
            student_id=student_id,
        )

    def student_has_course(self, course_id: str, student_sub: str) -> bool:
        return _repo_member_queries.student_has_course(
            dsn=self._dsn,
            psycopg_module=psycopg,
            course_id=course_id,
            student_sub=student_sub,
        )

    def create_concern_box_entry(
        self,
        *,
        course_id: str,
        student_sub: str,
        message_text: str,
        anonymous: bool,
    ) -> dict[str, Any] | None:
        return _repo_concern_box_queries.create_concern_box_entry(
            dsn=self._dsn,
            psycopg_module=psycopg,
            course_id=course_id,
            student_sub=student_sub,
            message_text=message_text,
            anonymous=anonymous,
        )

    def list_concern_box_entries_for_teacher(self, owner_sub: str, scope: str) -> list[dict[str, Any]]:
        return _repo_concern_box_queries.list_concern_box_entries_for_teacher(
            dsn=self._dsn,
            psycopg_module=psycopg,
            owner_sub=owner_sub,
            scope=scope,
        )

    def archive_concern_box_entry_owned(self, entry_id: str, owner_sub: str) -> bool:
        return _repo_concern_box_queries.archive_concern_box_entry_owned(
            dsn=self._dsn,
            psycopg_module=psycopg,
            entry_id=entry_id,
            owner_sub=owner_sub,
        )

    def restore_concern_box_entry_owned(self, entry_id: str, owner_sub: str) -> bool:
        return _repo_concern_box_queries.restore_concern_box_entry_owned(
            dsn=self._dsn,
            psycopg_module=psycopg,
            entry_id=entry_id,
            owner_sub=owner_sub,
        )

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
        return _repo_member_queries.add_member(
            dsn=self._dsn,
            psycopg_module=psycopg,
            course_id=course_id,
            student_id=student_id,
        )

    def list_members(self, course_id: str, limit: int, offset: int) -> List[Tuple[str, str]]:
        return _repo_member_queries.list_members(
            dsn=self._dsn,
            psycopg_module=psycopg,
            course_id=course_id,
            limit=limit,
            offset=offset,
        )

    def remove_member(self, course_id: str, student_id: str) -> None:
        return _repo_member_queries.remove_member(
            dsn=self._dsn,
            psycopg_module=psycopg,
            course_id=course_id,
            student_id=student_id,
        )
