"""Postgres-backed repository for the Learning context."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, List, Optional, Sequence
import json
import os
import re
from uuid import UUID, uuid5

try:  # pragma: no cover -- optional dependency in some environments
    import psycopg
    from psycopg import Connection
    from psycopg import sql
    from psycopg.types.json import Json

    HAVE_PSYCOPG = True
except Exception:  # pragma: no cover
    psycopg = None  # type: ignore
    Json = None  # type: ignore
    Connection = Any  # type: ignore
    HAVE_PSYCOPG = False

_ERROR_MAX_LENGTH = 256
_SENSITIVE_TOKEN_PATTERN = re.compile(r"(?i)(secret|token|password|key)[-_a-z0-9]*\s*=\s*\S+")


def _sanitize_error_message(value: Optional[str]) -> Optional[str]:
    """Strip secrets and truncate lengthy adapter errors for safe exposure."""
    if not value:
        return None
    collapsed = " ".join(str(value).split())
    if not collapsed:
        return None
    scrubbed = _SENSITIVE_TOKEN_PATTERN.sub("[redacted]", collapsed)
    if len(scrubbed) > _ERROR_MAX_LENGTH:
        scrubbed = scrubbed[: _ERROR_MAX_LENGTH - 3].rstrip() + "..."
    return scrubbed


def _default_app_login_dsn() -> str:
    """Return the local dev DSN using the app login role (e.g. gustav_app).

    Why:
        The application role `gustav_limited` is NOLOGIN. Local development
        therefore uses an environment-specific login (created via
        `make db-login-user`) that inherits from `gustav_limited`.

    Behavior:
        - Falls back to APP_DB_USER/APP_DB_PASSWORD (defaults mirror .env.example).
        - Raises a helpful error when the user still points to `gustav_limited`.
    """
    host = os.getenv("TEST_DB_HOST", "127.0.0.1")
    port = os.getenv("TEST_DB_PORT", "54322")
    user = os.getenv("APP_DB_USER", "gustav_app")
    password = os.getenv("APP_DB_PASSWORD", "CHANGE_ME_DEV")
    if not user or user == "gustav_limited":
        raise RuntimeError(
            "APP_DB_USER must reference the environment-specific login role "
            "(e.g. gustav_app). Run `make db-login-user` to provision it."
        )
    return f"postgresql://{user}:{password}@{host}:{port}/postgres"


def _dsn() -> str:
    """Resolve the Postgres DSN with test-friendly precedence.

    Order of precedence (first non-empty wins):
      1) LEARNING_DATABASE_URL / LEARNING_DB_URL (context-specific overrides)
      2) RLS_TEST_DSN (pytest helper for RLS-aware DB access)
      3) DATABASE_URL (app-wide default from environment/conftest)
      4) Fallback app-login DSN pointing at the local Supabase (dev/test only)

    Rationale:
      Some tests (RLS, API contract) explicitly export RLS_TEST_DSN. Earlier our
      resolution ignored it which could lead to mismatches (e.g., pointing at a
      different host/port). Including it here aligns the Learning context with the
      rest of the test utilities and avoids spurious connection errors.
    """
    env = (os.getenv("GUSTAV_ENV", "dev") or "dev").lower()
    candidates = [
        os.getenv("LEARNING_DATABASE_URL"),
        os.getenv("LEARNING_DB_URL"),
        os.getenv("RLS_TEST_DSN"),
        os.getenv("DATABASE_URL"),
    ]
    # Only allow default limited DSN implicitly in non-prod environments (dev/test)
    if env != "prod":
        candidates.append(_default_app_login_dsn())
    for candidate in candidates:
        if candidate:
            return candidate
    raise RuntimeError("Database DSN unavailable for Learning repo")


@dataclass
class SubmissionInput:
    course_id: str
    task_id: str
    student_sub: str
    kind: str
    text_body: Optional[str]
    storage_key: Optional[str]
    mime_type: Optional[str]
    size_bytes: Optional[int]
    sha256: Optional[str]
    idempotency_key: Optional[str]


class DBLearningRepo:
    """Persistence adapter used by Learning use cases."""

    def __init__(self, dsn: Optional[str] = None) -> None:
        if not HAVE_PSYCOPG:
            raise RuntimeError("psycopg3 is required for DBLearningRepo")
        self._dsn = dsn or _dsn()
        # In test/E2E contexts we allow bypassing strict DSN verification to
        # avoid failing on import when the DB isn't reachable yet.
        def _truthy(name: str) -> bool:
            v = str(os.getenv(name, "")).lower()
            return v in ("1", "true", "yes", "on")

        allow_override = _truthy("ALLOW_SERVICE_DSN_FOR_TESTING") or _truthy("RUN_E2E") or _truthy("RUN_SUPABASE_E2E") or bool(os.getenv("PYTEST_CURRENT_TEST"))
        if not allow_override:
            user = self._dsn_username(self._dsn)
            if user != "gustav_limited":
                try:
                    # Attempt a fast connection to verify role membership. If the
                    # database is unavailable (e.g., during test collection), defer
                    # verification to the first actual use instead of failing import.
                    with psycopg.connect(self._dsn, connect_timeout=3) as _conn:  # type: ignore[arg-type]
                        with _conn.cursor() as _cur:
                            _cur.execute("select pg_has_role(current_user, 'gustav_limited', 'member')")
                            ok = bool((_cur.fetchone() or [False])[0])
                            if not ok:
                                raise RuntimeError(
                                    "LearningRepo requires a login that is IN ROLE gustav_limited (RLS)."
                                )
                except Exception as e:
                    # Defer verification when no connection can be established.
                    # This keeps module import lightweight for tests that skip DB.
                    msg = str(getattr(e, "__class__", type(e)).__name__)
                    if "OperationalError" in msg or "connection" in str(e).lower():
                        pass
                    else:
                        raise RuntimeError(
                            f"LearningRepo DSN verification failed: {e}. Ensure your DB user is IN ROLE gustav_limited."
                        )

    @staticmethod
    def _dsn_username(dsn: str) -> str:
        from urllib.parse import urlparse

        try:
            parsed = urlparse(dsn)
            if parsed.username:
                return parsed.username
        except Exception:
            pass
        match = re.match(r"^[a-z]+://(?P<u>[^:]+):?[^@]*@", dsn or "")
        return match.group("u") if match else ""

    def _set_current_sub(self, cur, sub: str) -> None:
        cur.execute("select set_config('app.current_sub', %s, true)", (sub,))

    # ------------------------------------------------------------------
    def list_courses_for_student(self, *, student_sub: str, limit: int, offset: int) -> List[dict]:
        """Return the student's courses with minimal fields, alphabetically.

        Security:
            Uses explicit membership join to avoid leaking teacher-owned courses
            in mixed-role scenarios. RLS remains active via gustav_limited and
            app.current_sub.
        """
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                self._set_current_sub(cur, student_sub)
                cur.execute(
                    """
                    select c.id::text, c.title, c.subject, c.grade_level, c.term
                      from public.courses c
                      join public.course_memberships m on m.course_id = c.id
                     where m.student_id = %s
                     order by c.title asc, c.id asc
                     offset %s
                     limit %s
                    """,
                    (student_sub, int(max(0, offset)), int(max(1, limit))),
                )
                rows = cur.fetchall()
        items: List[dict] = []
        for row in rows:
            items.append(
                {
                    "id": row[0],
                    "title": row[1],
                    "subject": row[2],
                    "grade_level": row[3],
                    "term": row[4],
                }
            )
        return items

    def list_units_for_student_course(self, *, student_sub: str, course_id: str) -> List[dict]:
        """Return units for the student's course ordered by module position.

        Raises LookupError when the course does not exist or the student is not
        a member (for 404 semantics in the API layer).
        """
        course_uuid = str(UUID(course_id))
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                self._set_current_sub(cur, student_sub)
                # Membership check for strict 404 semantics
                cur.execute(
                    "select exists(select 1 from public.course_memberships where course_id=%s and student_id=%s)",
                    (course_uuid, student_sub),
                )
                if not bool(cur.fetchone()[0]):
                    raise LookupError("not_member_or_missing")
                cur.execute(
                    """
                    select unit_id::text, title, summary, module_position
                      from public.get_course_units_for_student(%s, %s)
                    """,
                    (student_sub, course_uuid),
                )
                rows = cur.fetchall()
        result: List[dict] = []
        for row in rows:
            result.append(
                {
                    "unit": {
                        "id": row[0],
                        "title": row[1],
                        "summary": row[2],
                    },
                    "position": int(row[3]) if row[3] is not None else 1,
                }
            )
        return result

    # ------------------------------------------------------------------
    def list_released_sections(
        self,
        *,
        student_sub: str,
        course_id: str,
        include_materials: bool,
        include_tasks: bool,
        limit: int,
        offset: int,
    ) -> List[dict]:
        course_uuid = str(UUID(course_id))
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                # RLS: set caller identity for membership check and all subsequent helpers
                self._set_current_sub(cur, student_sub)
                cur.execute(
                    "select exists(select 1 from public.course_memberships where course_id=%s and student_id=%s)",
                    (course_uuid, student_sub),
                )
                if not bool(cur.fetchone()[0]):
                    raise PermissionError("not_course_member")

                self._set_current_sub(cur, student_sub)
                cur.execute(
                    """
                    select section_id::text,
                           section_title,
                           section_position,
                           unit_id::text,
                           course_module_id::text
                      from public.get_released_sections_for_student(%s, %s, %s, %s)
                    """,
                    (student_sub, course_uuid, int(limit), int(offset)),
                )
                rows = cur.fetchall()

            if not rows:
                raise LookupError("no_released_sections")

            sections: List[dict] = []
            for row in rows:
                section_id = row[0]
                unit_id = row[3]
                entry = {
                    "section": {
                        "id": section_id,
                        "title": row[1],
                        # Contract requires integer ≥ 1; fall back to 1 if DB position is NULL
                        "position": int(row[2]) if row[2] is not None else 1,
                        # Expose owning unit to allow UI grouping/filtering per unit page.
                        "unit_id": unit_id,
                    },
                    "materials": [],
                    "tasks": [],
                }
                if include_materials:
                    entry["materials"] = self._fetch_materials(conn, student_sub, course_uuid, section_id)
                if include_tasks:
                    entry["tasks"] = self._fetch_tasks(conn, student_sub, course_uuid, section_id)
                sections.append(entry)
            return sections

    def _fetch_materials(self, conn: Connection, student_sub: str, course_id: str, section_id: str) -> List[dict]:
        with conn.cursor() as cur:
            self._set_current_sub(cur, student_sub)
            cur.execute(
                """
                select id::text,
                       title,
                       kind,
                       body_md,
                       mime_type,
                       size_bytes,
                       filename_original,
                       storage_key,
                       sha256,
                       alt_text,
                       material_position,
                       created_at_iso,
                       updated_at_iso
                  from public.get_released_materials_for_student(%s, %s, %s)
                """,
                (student_sub, course_id, section_id),
            )
            rows = cur.fetchall()
        materials: List[dict] = []
        for row in rows:
            materials.append(
                {
                    "id": row[0],
                    "title": row[1],
                    "kind": row[2],
                    "body_md": row[3],
                    "mime_type": row[4],
                    "size_bytes": row[5],
                    "filename_original": row[6],
                    "storage_key": row[7],
                    "sha256": row[8],
                    "alt_text": row[9],
                    "position": int(row[10]) if row[10] is not None else None,
                    "created_at": row[11],
                    "updated_at": row[12],
                }
            )
        return materials

    def _fetch_tasks(self, conn: Connection, student_sub: str, course_id: str, section_id: str) -> List[dict]:
        with conn.cursor() as cur:
            self._set_current_sub(cur, student_sub)
            cur.execute(
                """
                select id::text,
                       instruction_md,
                       criteria,
                       hints_md,
                       due_at_iso,
                       max_attempts,
                       task_position,
                       created_at_iso,
                       updated_at_iso
                  from public.get_released_tasks_for_student(%s, %s, %s)
                """,
                (student_sub, course_id, section_id),
            )
            rows = cur.fetchall()
        tasks: List[dict] = []
        for row in rows:
            tasks.append(
                {
                    "id": row[0],
                    "instruction_md": row[1],
                    "criteria": list(row[2] or []),
                    "hints_md": row[3],
                    "due_at": row[4],
                    "max_attempts": row[5],
                    "position": int(row[6]) if row[6] is not None else None,
                    "created_at": row[7],
                    "updated_at": row[8],
                    "kind": "native",
                }
            )
        return tasks

    def list_released_sections_by_unit(
        self,
        *,
        student_sub: str,
        course_id: str,
        unit_id: str,
        include_materials: bool,
        include_tasks: bool,
        limit: int,
        offset: int,
    ) -> List[dict]:
        """List released sections for a specific unit (student scope).

        Security:
            Validates that the student is a member of the course and that the
            unit belongs to the course (via course_modules). Uses a dedicated
            SQL helper for efficient server-side filtering.
        """
        course_uuid = str(UUID(course_id))
        unit_uuid = str(UUID(unit_id))
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                self._set_current_sub(cur, student_sub)
                # Ensure membership exists
                cur.execute(
                    "select exists(select 1 from public.course_memberships where course_id=%s and student_id=%s)",
                    (course_uuid, student_sub),
                )
                if not bool(cur.fetchone()[0]):
                    raise PermissionError("not_course_member")

                # Verify that the unit belongs to the course from the student's perspective
                cur.execute(
                    """
                    select exists (
                             select 1
                               from public.get_course_units_for_student(%s, %s) t
                              where t.unit_id = %s
                           )
                    """,
                    (student_sub, course_uuid, unit_uuid),
                )
                if not bool(cur.fetchone()[0]):
                    raise LookupError("unit_not_in_course")

                # Fetch released sections for the unit (may be empty)
                cur.execute(
                    """
                    select section_id::text,
                           section_title,
                           section_position,
                           unit_id::text,
                           course_module_id::text
                      from public.get_released_sections_for_student_by_unit(%s, %s, %s, %s, %s)
                    """,
                    (student_sub, course_uuid, unit_uuid, int(limit), int(offset)),
                )
                rows = cur.fetchall()

            # Unit-scoped: return an empty list when no sections are released
            sections: List[dict] = []
            for row in rows:
                section_id = row[0]
                entry = {
                    "section": {
                        "id": section_id,
                        "title": row[1],
                        # Fallback to 1 if NULL to satisfy contract >= 1
                        "position": int(row[2]) if row[2] is not None else 1,
                        "unit_id": row[3],
                    },
                    "materials": [],
                    "tasks": [],
                }
                if include_materials:
                    entry["materials"] = self._fetch_materials(conn, student_sub, course_uuid, section_id)
                if include_tasks:
                    entry["tasks"] = self._fetch_tasks(conn, student_sub, course_uuid, section_id)
                sections.append(entry)
            return sections

    # ------------------------------------------------------------------
    def create_submission(self, data: SubmissionInput) -> dict:
        """Persist a student submission after enforcing membership and attempts.

        Why:
            Centralizes membership checks, release visibility, rubric retrieval
            and attempt counting within the persistence adapter so the use case
            stays framework-agnostic.

        Parameters:
            data: SubmissionInput containing course/task identifiers, caller
                  `student_sub`, payload kind and optional storage metadata.

        Behavior:
            - Verifies membership via course_memberships (RLS-aware).
            - Reuses existing row when an Idempotency-Key is supplied.
            - Fetches release metadata (max_attempts + rubric criteria) via
              `get_task_metadata_for_student`, which already scopes rows to
              the caller and visible sections.
            - Persists the submission and returns the stored record with stub
              analysis/feedback fields.

        Permissions:
            Caller must be the enrolled student and the section must be
            released. Database helper functions enforce this through RLS.
        """
        course_uuid = str(UUID(data.course_id))
        task_uuid = str(UUID(data.task_id))

        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                self._set_current_sub(cur, data.student_sub)
                cur.execute(
                    "select exists(select 1 from public.course_memberships where course_id=%s and student_id=%s)",
                    (course_uuid, data.student_sub),
                )
                if not bool(cur.fetchone()[0]):
                    raise PermissionError("not_course_member")

                # Normalize Idempotency-Key (guard against hidden whitespace/case quirks)
                norm_key = None
                if data.idempotency_key and isinstance(data.idempotency_key, str):
                    nk = data.idempotency_key.strip()
                    norm_key = nk if nk else None

                if norm_key:
                    cur.execute(
                        """
                        select id::text,
                               attempt_nr,
                               kind,
                               text_body,
                               mime_type,
                               size_bytes,
                               storage_key,
                               sha256,
                               analysis_status,
                               analysis_json,
                               feedback_md,
                               error_code,
                               coalesce(vision_attempts, 0),
                               vision_last_error,
                               to_char(feedback_last_attempt_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                               feedback_last_error,
                               to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                               to_char(completed_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
                          from public.learning_submissions
                         where course_id = %s::uuid
                           and task_id = %s::uuid
                           and student_sub = %s
                           and idempotency_key = %s
                        """,
                        (course_uuid, task_uuid, data.student_sub, norm_key),
                    )
                    existing = cur.fetchone()
                    if existing:
                        return self._row_to_submission(existing)

                cur.execute(
                    """
                    select task_id::text,
                           section_id::text,
                           unit_id::text,
                           max_attempts,
                           coalesce(criteria, array[]::text[])
                      from public.get_task_metadata_for_student(%s, %s, %s)
                    """,
                    (data.student_sub, course_uuid, task_uuid),
                )
                meta = cur.fetchone()
                if not meta:
                    raise LookupError("task_not_visible")
                max_attempts = meta[3]
                # Rubric criteria come from the helper (already filtered by RLS).
                raw_criteria = list(meta[4] or [])
                criteria = [str(entry).strip() for entry in raw_criteria if str(entry).strip()]

                cur.execute(
                    "select public.next_attempt_nr(%s, %s, %s)",
                    (course_uuid, task_uuid, data.student_sub),
                )
                attempt_nr = int(cur.fetchone()[0])
                if max_attempts is not None and attempt_nr > int(max_attempts):
                    raise ValueError("max_attempts_exceeded")

                try:
                    # Async path: record pending status and enqueue job. Idempotency is enforced
                    # via ON CONFLICT on (course_id, task_id, student_sub, idempotency_key).
                    # For stronger guarantees independent of index inference, when an
                    # Idempotency-Key is provided we derive a deterministic UUIDv5 for
                    # the primary key from (course_id, task_id, student_sub, key). This
                    # ensures duplicate retries inevitably collide on the primary key.
                    deterministic_id = None
                    if norm_key:
                        # UUID namespace chosen arbitrarily but constant.
                        deterministic_id = str(
                            uuid5(UUID("00000000-0000-0000-0000-000000000001"),
                                  f"{course_uuid}:{task_uuid}:{data.student_sub}:{norm_key}")
                        )

                    cur.execute(
                        """
                        insert into public.learning_submissions (
                            id,
                            course_id,
                            task_id,
                            student_sub,
                            kind,
                            text_body,
                            storage_key,
                            mime_type,
                            size_bytes,
                            sha256,
                            attempt_nr,
                            analysis_status,
                            analysis_json,
                            feedback_md,
                            error_code,
                            idempotency_key
                        )
                        values (coalesce(%s::uuid, gen_random_uuid()),
                                %s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, %s,
                                %s,
                                'pending', null, null, null, %s)
                        on conflict (course_id, task_id, student_sub, idempotency_key)
                        do nothing
                        returning id::text,
                                  attempt_nr,
                                  kind,
                                  text_body,
                                  mime_type,
                                  size_bytes,
                                  storage_key,
                                  sha256,
                                  analysis_status,
                                  analysis_json,
                                  feedback_md,
                                  error_code,
                                  coalesce(vision_attempts, 0),
                                  vision_last_error,
                                  to_char(feedback_last_attempt_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                                  feedback_last_error,
                                  to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                                  to_char(completed_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
                        """,
                        (
                            deterministic_id,
                            course_uuid,
                            task_uuid,
                            data.student_sub,
                            data.kind,
                            data.text_body,
                            data.storage_key,
                            data.mime_type,
                            data.size_bytes,
                            data.sha256,
                            attempt_nr,
                            norm_key,
                        ),
                    )
                    row = cur.fetchone()
                    if row is None and norm_key:
                        # Conflict occurred; fetch existing row by idempotency key
                        cur.execute(
                            """
                            select id::text,
                                   attempt_nr,
                                   kind,
                                   text_body,
                                   mime_type,
                                   size_bytes,
                                   storage_key,
                                   sha256,
                                   analysis_status,
                                   analysis_json,
                                   feedback_md,
                                   error_code,
                                   coalesce(vision_attempts, 0),
                                   vision_last_error,
                                   to_char(feedback_last_attempt_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                                   feedback_last_error,
                                   to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                                   to_char(completed_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
                              from public.learning_submissions
                             where course_id = %s::uuid and task_id = %s::uuid and student_sub = %s and idempotency_key = %s
                            """,
                            (course_uuid, task_uuid, data.student_sub, norm_key),
                        )
                        row = cur.fetchone()
                    submission_id = row[0]
                    # Enrich job payload with task instruction and optional hints for the Feedback adapter
                    instruction_md: str | None = None
                    hints_md: str | None = None
                    try:
                        section_id = str(meta[1])  # from get_task_metadata_for_student
                        cur.execute(
                            """
                            select id::text, instruction_md, hints_md
                              from public.get_released_tasks_for_student(%s, %s, %s)
                            """,
                            (data.student_sub, course_uuid, section_id),
                        )
                        rows_ctx = cur.fetchall() or []
                        for tid, instr, hints in rows_ctx:
                            if str(tid) == task_uuid:
                                instruction_md = instr
                                hints_md = hints
                                break
                    except Exception:
                        # Be tolerant: missing helper or columns shouldn't block submissions
                        instruction_md = None
                        hints_md = None

                    job_payload = {
                        "submission_id": submission_id,
                        "course_id": course_uuid,
                        "task_id": task_uuid,
                        "student_sub": data.student_sub,
                        "kind": data.kind,
                        "attempt_nr": attempt_nr,
                        "criteria": criteria,
                        "instruction_md": instruction_md,
                        "hints_md": hints_md,
                    }
                    queue_table = self._resolve_queue_table(cur)
                    if queue_table:
                        insert_sql = sql.SQL(
                            "insert into public.{} (submission_id, payload) values (%s::uuid, %s)"
                        ).format(sql.Identifier(queue_table))
                        cur.execute(
                            insert_sql,
                            (
                                submission_id,
                                Json(job_payload) if Json is not None else json.dumps(job_payload),
                            ),
                        )
                    conn.commit()
                except Exception as exc:
                    # If another in-flight request inserted with the same Idempotency-Key, reuse it
                    from psycopg import errors as _pg_errors  # type: ignore

                    if isinstance(exc, _pg_errors.UniqueViolation):
                        conn.rollback()
                        with conn.cursor() as cur2:
                            # Rollback clears transaction-scoped GUCs; restore RLS context before querying.
                            self._set_current_sub(cur2, data.student_sub)
                            cur2.execute(
                                """
                                select id::text,
                                       attempt_nr,
                                       kind,
                                       text_body,
                                       mime_type,
                                       size_bytes,
                                       storage_key,
                                       sha256,
                                       analysis_status,
                               analysis_json,
                               feedback_md,
                               error_code,
                               coalesce(vision_attempts, 0),
                               vision_last_error,
                               to_char(feedback_last_attempt_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                               feedback_last_error,
                               to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                               to_char(completed_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
                                  from public.learning_submissions
                                 where course_id = %s::uuid and task_id = %s::uuid and student_sub = %s and idempotency_key = %s
                                """,
                                (course_uuid, task_uuid, data.student_sub, norm_key),
                            )
                            existing = cur2.fetchone()
                        if existing:
                            row = existing
                        else:  # defensive: re-raise if we cannot recover
                            raise
                    else:
                        raise
        return self._row_to_submission(row)

    def list_submissions(
        self,
        *,
        student_sub: str,
        course_id: str,
        task_id: str,
        limit: int,
        offset: int,
    ) -> List[dict]:
        """Fetch the caller's submission history for a task.

        Intent:
            Encapsulate membership/visibility guards and stable ordering inside
            the persistence layer while keeping use cases framework-agnostic.

        Parameters:
            student_sub: Authenticated student's subject identifier.
            course_id: Course scope for the task, UUID string.
            task_id: Target task UUID.
            limit/offset: Pagination parameters (already clamped by use case).

        Permissions:
            Caller must be enrolled in the course and the section must be
            released; enforced via membership check and
            `get_task_metadata_for_student`.
        """
        course_uuid = str(UUID(course_id))
        task_uuid = str(UUID(task_id))

        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                self._set_current_sub(cur, student_sub)
                cur.execute(
                    "select exists(select 1 from public.course_memberships where course_id=%s and student_id=%s)",
                    (course_uuid, student_sub),
                )
                if not bool(cur.fetchone()[0]):
                    raise PermissionError("not_course_member")

                cur.execute(
                    """
                    select task_id::text
                      from public.get_task_metadata_for_student(%s, %s, %s)
                    """,
                    (student_sub, course_uuid, task_uuid),
                )
                visible = cur.fetchone()
                if not visible:
                    raise LookupError("task_not_visible")

                cur.execute(
                    """
                    select id::text,
                           attempt_nr,
                           kind,
                           text_body,
                           mime_type,
                           size_bytes,
                           storage_key,
                           sha256,
                           analysis_status,
                           analysis_json,
                           feedback_md,
                           error_code,
                           coalesce(vision_attempts, 0),
                           vision_last_error,
                           to_char(feedback_last_attempt_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                           feedback_last_error,
                           to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                           to_char(completed_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
                      from public.learning_submissions
                     where course_id = %s
                       and task_id = %s
                       and student_sub = %s
                     order by created_at desc, attempt_nr desc
                     limit %s offset %s
                    """,
                    (course_uuid, task_uuid, student_sub, int(limit), int(offset)),
                )
                rows = cur.fetchall()

        return [self._row_to_submission(row) for row in rows]

    def _resolve_queue_table(self, cur) -> Optional[str]:
        """Return the available queue table name (new or legacy), if any."""
        candidates = ("learning_submission_jobs", "learning_submission_ocr_jobs")
        for name in candidates:
            cur.execute("select to_regclass(%s)", (f"public.{name}",))
            reg = cur.fetchone()
            if reg and reg[0]:
                return name
        return None

    @staticmethod
    def _render_feedback(kind: str, attempt: int) -> str:
        if kind == "text":
            return f"Attempt {attempt}: Thanks for your explanation."
        if kind == "file":
            return f"Attempt {attempt}: PDF submission received."
        return f"Attempt {attempt}: Image submission received."

    def _build_analysis_payload(
        self,
        *,
        kind: str,
        text_body: Optional[str],
        storage_key: Optional[str],
        sha256: Optional[str],
        criteria: Sequence[str],
    ) -> dict:
        """Produce the synchronous analysis stub used until ML integration.

        Why:
            MVP returns immediate formative feedback to help Lernende reflektieren,
            bevor echte Modelle (OCR, Scoring) angeschlossen werden. Wir liefern
            deterministische, leicht nachvollziehbare Inhalte:
            - text: Originaltext (getrimmt)
            - image: "OCR placeholder for <basename|hash>"
            - file (PDF): "PDF text placeholder for <basename|hash>"

        Security:
            Keine Dateiinhalte werden zurückgegeben; nur Platzhaltertexte.
        """
        if kind == "text":
            text = (text_body or "").strip()
        elif kind == "file":
            # MVP: show placeholder that mimics extracted PDF text for history
            text = self._pdf_text_stub(storage_key, sha256)
        else:
            text = self._image_text_stub(storage_key, sha256)
        length = len(text)
        scores = self._build_scores(criteria, length)
        return {
            "text": text,
            "length": length,
            "scores": scores,
        }

    def _build_scores(self, criteria: Sequence[str], text_length: int) -> List[dict]:
        """Generate rubric-style scores with deterministic, easy-to-read values."""
        names = [c for c in criteria if c]
        if not names:
            names = ["Submission"]
        # Simple heuristic: longer answers receive slightly higher stub scores.
        base_score = 6 if text_length < 20 else 8
        scores: List[dict] = []
        for index, criterion in enumerate(names):
            score = min(10, base_score + min(index, 2))
            scores.append(
                {
                    "criterion": criterion,
                    "score": score,
                    "explanation": "Stubbed analysis until machine learning is integrated.",
                }
            )
        return scores

    @staticmethod
    def _image_text_stub(storage_key: Optional[str], sha256: Optional[str]) -> str:
        """Derive a deterministic textual placeholder for OCR output."""
        if storage_key:
            token = storage_key.split("/")[-1]
        elif sha256:
            token = sha256[:12]
        else:
            token = "image"
        return f"OCR placeholder for {token}"

    @staticmethod
    def _pdf_text_stub(storage_key: Optional[str], sha256: Optional[str]) -> str:
        """Produce a stable placeholder for PDF-derived text.

        Intention: In der Historie zeigen wir den extrahierten Text (später OCR),
        jetzt ein Platzhalter mit Dateinamen/Hash für Lernzwecke.
        """
        if storage_key:
            token = storage_key.split("/")[-1]
        elif sha256:
            token = sha256[:12]
        else:
            token = "document.pdf"
        return f"PDF text placeholder for {token}"

    @staticmethod
    def _row_to_submission(row: Iterable[Any]) -> dict:
        """Map a DB row to an API submission dict with safe fallbacks.

        Why:
            Only completed submissions expose `analysis_json`. Historical rows
            may still miss optional fields, so for completed states we
            synthesize a minimal payload to keep learner history readable.
        """
        (
            submission_id,
            attempt_nr,
            kind,
            text_body,
            mime_type,
            size_bytes,
            storage_key,
            sha256,
            status,
            analysis_raw,
            feedback_md,
            error_code,
            vision_attempts,
            vision_last_error,
            feedback_last_attempt_at,
            feedback_last_error,
            created_at,
            completed_at,
        ) = list(row)
        if status != "completed":
            analysis_payload = None
        else:
            analysis_payload = analysis_raw
            if isinstance(analysis_payload, str):
                try:
                    analysis_payload = json.loads(analysis_payload)
                except Exception:  # pragma: no cover - defensive
                    pass
            # Synthesize fallback analysis text when missing/empty
            if not isinstance(analysis_payload, dict):
                analysis_payload = {}
            existing_text = str(
                (analysis_payload.get("text") if isinstance(analysis_payload, dict) else "") or ""
            )
            if not existing_text.strip():
                if kind == "text":
                    analysis_payload["text"] = (text_body or "").strip()
                elif kind == "file":
                    analysis_payload["text"] = DBLearningRepo._pdf_text_stub(storage_key, sha256)
                else:
                    analysis_payload["text"] = DBLearningRepo._image_text_stub(storage_key, sha256)
        telemetry_attempts = int(vision_attempts or 0)
        return {
            "id": submission_id,
            "attempt_nr": int(attempt_nr),
            "kind": kind,
            "text_body": text_body,
            "mime_type": mime_type,
            "size_bytes": size_bytes,
            "storage_key": storage_key,
            "sha256": sha256,
            "analysis_status": status,
            "analysis_json": analysis_payload,
            "feedback": feedback_md if status != "pending" else None,
            "error_code": error_code,
            "vision_attempts": telemetry_attempts,
            "vision_last_error": _sanitize_error_message(vision_last_error),
            "feedback_last_attempt_at": feedback_last_attempt_at,
            "feedback_last_error": _sanitize_error_message(feedback_last_error),
            # created_at/completed_at already returned as ISO strings
            "created_at": created_at,
            "completed_at": completed_at,
        }

    # ------------------------------------------------------------------
    def mark_extracted(self, *, submission_id: str, page_keys: List[str]) -> None:
        """Set analysis_status to 'extracted' and persist page key metadata internally.

        Why:
            After rendering a PDF to page images, we record their storage keys
            to enable downstream OCR/vision steps. The artifacts remain private
            (`internal_metadata`) so the public API stays schema-compliant.

        Behavior:
            - Updates only the targeted submission id.
            - Sets `analysis_status = 'extracted'`.
            - Stores `page_keys` inside `internal_metadata` while keeping
              `analysis_json` null until feedback is generated.

        Permissions:
            The repo executes with the limited application role under RLS. The
            caller must only pass submission ids that belong to the current
            student/flow per surrounding use case.
        """
        if not submission_id:
            raise ValueError("submission_id is required")
        with psycopg.connect(self._dsn) as conn:  # type: ignore[arg-type]
            with conn.cursor() as cur:
                # We do not change completed_at here; 'extracted' is intermediate
                cur.execute(
                    """
                    update public.learning_submissions
                       set analysis_status = 'extracted',
                           analysis_json = null,
                           internal_metadata = coalesce(internal_metadata, '{}'::jsonb)
                                              || jsonb_build_object('page_keys', %s::jsonb)
                 where id = %s::uuid
                    returning id
                    """,
                    (Json(list(page_keys)), str(UUID(submission_id))),
                )
                updated = cur.fetchone()
                if not updated:
                    raise LookupError("submission_not_found")
            conn.commit()
