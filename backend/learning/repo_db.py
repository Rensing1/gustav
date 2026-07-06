"""Postgres-backed repository for the Learning context."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional, Sequence
import json
import os
import re
from uuid import UUID, uuid5
from backend.learning import repo_course_unit_queries as _repo_course_unit_queries
from backend.learning import repo_modular_unit_queries as _repo_modular_unit_queries
from backend.learning import repo_submission_summary_queries as _repo_submission_summary_queries
from backend.learning.repo_submission_mapping import (
    build_analysis_payload as _build_analysis_payload,
    build_scores as _build_scores,
    image_text_stub as _image_text_stub,
    pdf_text_stub as _pdf_text_stub,
    render_feedback as _render_feedback,
    row_to_submission as _row_to_submission,
    sanitize_error_message as _sanitize_error_message,  # noqa: F401
)
from backend.learning.submission_kind_policy import validate_task_submission_kind

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

def _validate_task_submission_kind(*, task_kind: str, submission_kind: str, mime_type: str | None) -> None:
    """Backward-compatible wrapper for the shared Learning policy."""
    validate_task_submission_kind(
        task_kind=task_kind,
        submission_kind=submission_kind,
        mime_type=mime_type,
    )


def _running_under_pytest() -> bool:
    """Return True when running under pytest (including test collection).

    Why:
        Unit tests run the FastAPI app in-process (ASGITransport) against the
        same local Postgres that docker services use. If a local docker
        `learning-worker` is running in parallel, it can consume queue jobs
        created by tests and mutate DB state asynchronously, making tests flaky.
    """
    import sys

    if os.getenv("PYTEST_CURRENT_TEST"):
        return True
    if any(name == "pytest" or name.startswith("pytest.") for name in sys.modules):
        return True
    if any(name == "_pytest" or name.startswith("_pytest.") for name in sys.modules):
        return True
    if any("pytest" in (arg or "").lower() for arg in sys.argv):
        return True
    return False


def _pytest_test_run_id() -> str | None:
    """Return the same sanitized test-run id that DB test cleanup uses."""

    explicit = (os.getenv("GUSTAV_TEST_RUN_ID") or "").strip()
    if explicit:
        return explicit
    current = (os.getenv("PYTEST_CURRENT_TEST") or "").strip()
    if current:
        return re.sub(r"[^A-Za-z0-9_.:-]+", "-", current)[:180]
    return None


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
    # Only allow the default dev DSN implicitly in non-prod-like environments.
    if env not in {"prod", "production", "stage", "staging"}:
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
    intent: str
    kind: str
    text_body: Optional[str]
    storage_key: Optional[str]
    mime_type: Optional[str]
    size_bytes: Optional[int]
    sha256: Optional[str]
    score_raw: Optional[int]
    score_max: Optional[int]
    idempotency_key: Optional[str]


class DBLearningRepo:
    """Persistence adapter used by Learning use cases."""

    _render_feedback = staticmethod(_render_feedback)
    _build_analysis_payload = staticmethod(_build_analysis_payload)
    _build_scores = staticmethod(_build_scores)
    _image_text_stub = staticmethod(_image_text_stub)
    _pdf_text_stub = staticmethod(_pdf_text_stub)
    _row_to_submission = staticmethod(_row_to_submission)

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

    def _set_current_course_id(self, cur, course_id: str) -> None:
        """Set course context for course-scoped student RLS checks.

        Why:
            Modular unit access is course-scoped (unlock state depends on the
            course). For now we use the course id as *context* for RLS checks
            in `student_can_access_section(...)` via `app.current_course_id`.
        """
        cur.execute("select set_config('app.current_course_id', %s, true)", (course_id,))

    def _task_submission_summary_map(
        self,
        conn: Connection,
        *,
        student_sub: str,
        course_id: str,
        task_ids: Sequence[str],
    ) -> dict[str, dict[str, Any]]:
        """Return lightweight latest-submission metadata per task for learner UI.

        Why:
            The learner task cards need stable CTA/status hints before the full
            history for a task is loaded. We keep this summary intentionally
            small and derive it from the student's own submissions only.
        """
        return _repo_submission_summary_queries.task_submission_summary_map(
            conn,
            student_sub=student_sub,
            course_id=course_id,
            task_ids=task_ids,
            set_current_sub=self._set_current_sub,
            set_current_course_id=self._set_current_course_id,
        )

    # ------------------------------------------------------------------
    def list_courses_for_student(self, *, student_sub: str, limit: int, offset: int) -> List[dict]:
        """Return the student's courses with minimal fields, alphabetically.

        Security:
            Uses explicit membership join to avoid leaking teacher-owned courses
            in mixed-role scenarios. RLS remains active via gustav_limited and
            app.current_sub.
        """
        return _repo_course_unit_queries.list_courses_for_student(
            dsn=self._dsn,
            psycopg_module=psycopg,
            student_sub=student_sub,
            limit=limit,
            offset=offset,
        )

    def list_units_for_student_course(self, *, student_sub: str, course_id: str) -> List[dict]:
        """Return units for the student's course ordered by module position.

        Raises LookupError when the course does not exist or the student is not
        a member (for 404 semantics in the API layer).
        """
        return _repo_course_unit_queries.list_units_for_student_course(
            dsn=self._dsn,
            psycopg_module=psycopg,
            student_sub=student_sub,
            course_id=course_id,
        )

    # ------------------------------------------------------------------
    def get_modular_unit_graph(self, *, student_sub: str, course_id: str, unit_id: str) -> dict:
        """Return a modular unit graph payload (phases/modules/edges) for a student."""
        return _repo_modular_unit_queries.get_modular_unit_graph(
            self,
            psycopg_module=psycopg,
            student_sub=student_sub,
            course_id=course_id,
            unit_id=unit_id,
        )

    def _fetch_modular_unit_module_states(
        self,
        *,
        cur,
        student_sub: str,
        course_uuid: str,
        unit_uuid: str,
    ) -> dict[str, dict]:
        """Fetch per-module unlock states from the single SQL source of truth."""
        return _repo_modular_unit_queries.fetch_modular_unit_module_states(
            cur=cur,
            student_sub=student_sub,
            course_uuid=course_uuid,
            unit_uuid=unit_uuid,
        )

    def _is_modular_section_open_or_done(
        self,
        *,
        cur,
        course_uuid: str,
        student_sub: str,
        unit_uuid: str,
        section_uuid: str,
    ) -> bool:
        """Return True if a modular section's module is open/done for the student."""
        return _repo_modular_unit_queries.is_modular_section_open_or_done(
            self,
            cur=cur,
            course_uuid=course_uuid,
            student_sub=student_sub,
            unit_uuid=unit_uuid,
            section_uuid=section_uuid,
        )

    def get_modular_module_content(
        self,
        *,
        student_sub: str,
        course_id: str,
        unit_id: str,
        module_id: str,
        include_materials: bool,
        include_tasks: bool,
    ) -> dict:
        """Return module content for modular units (materials/tasks) when accessible."""
        return _repo_modular_unit_queries.get_modular_module_content(
            self,
            psycopg_module=psycopg,
            student_sub=student_sub,
            course_id=course_id,
            unit_id=unit_id,
            module_id=module_id,
            include_materials=include_materials,
            include_tasks=include_tasks,
        )

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
        return _repo_modular_unit_queries.list_released_sections(
            self,
            psycopg_module=psycopg,
            student_sub=student_sub,
            course_id=course_id,
            include_materials=include_materials,
            include_tasks=include_tasks,
            limit=limit,
            offset=offset,
        )

    def _fetch_materials(self, conn: Connection, student_sub: str, course_id: str, section_id: str) -> List[dict]:
        return _repo_modular_unit_queries.fetch_materials(self, conn, student_sub, course_id, section_id)

    def _fetch_tasks(self, conn: Connection, student_sub: str, course_id: str, section_id: str) -> List[dict]:
        return _repo_modular_unit_queries.fetch_tasks(self, conn, student_sub, course_id, section_id)

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
        """List released sections for a specific unit (student scope)."""
        return _repo_modular_unit_queries.list_released_sections_by_unit(
            self,
            psycopg_module=psycopg,
            student_sub=student_sub,
            course_id=course_id,
            unit_id=unit_id,
            include_materials=include_materials,
            include_tasks=include_tasks,
            limit=limit,
            offset=offset,
        )

    def is_h5p_content_released_for_student(self, *, student_sub: str, course_id: str, content_id: str) -> bool:
        """Return True when the student may access this H5P content in the course."""
        return _repo_modular_unit_queries.is_h5p_content_released_for_student(
            self,
            psycopg_module=psycopg,
            student_sub=student_sub,
            course_id=course_id,
            content_id=content_id,
        )

    def _find_matching_inflight_feedback_submission(
        self,
        cur: Any,
        *,
        course_uuid: str,
        task_uuid: str,
        student_sub: str,
        data: SubmissionInput,
    ) -> Any | None:
        """Return the newest matching in-flight feedback submission, if any.

        Why:
            The learner UI already disables the feedback button locally, but
            accidental double-clicks or parallel retries can still reach the
            backend with different idempotency keys. Reusing the active
            feedback submission prevents duplicate worker runs without blocking
            a deliberate re-run after completion.
        """
        if data.intent != "feedback" or data.kind == "h5p":
            return None

        base_query = """
            select id::text,
                   attempt_nr,
                   intent,
                   kind,
                   score_raw,
                   score_max,
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
               and intent = 'feedback'
               and (
                    analysis_status in ('pending', 'extracted')
                    or error_code in ('vision_retrying', 'feedback_retrying')
               )
        """

        if data.kind == "text":
            text_body = str(data.text_body or "").strip()
            if not text_body:
                return None
            cur.execute(
                base_query
                + """
                   and kind = 'text'
                   and btrim(coalesce(text_body, '')) = %s
                 order by created_at desc, attempt_nr desc
                 limit 1
                """,
                (course_uuid, task_uuid, student_sub, text_body),
            )
            return cur.fetchone()

        if data.kind not in {"image", "file"}:
            return None

        mime_type = str(data.mime_type or "").strip().lower()
        sha256 = str(data.sha256 or "").strip().lower()
        if not mime_type or not sha256 or data.size_bytes is None:
            return None

        cur.execute(
            base_query
            + """
               and kind = %s
               and coalesce(mime_type, '') = %s
               and coalesce(sha256, '') = %s
               and coalesce(size_bytes, -1) = %s
             order by created_at desc, attempt_nr desc
             limit 1
            """,
            (course_uuid, task_uuid, student_sub, data.kind, mime_type, sha256, int(data.size_bytes)),
        )
        return cur.fetchone()

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
                # Course-scoped RLS context: required for modular units where
                # section/task visibility depends on the current course.
                self._set_current_course_id(cur, course_uuid)
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
                               intent,
                               kind,
                               score_raw,
                               score_max,
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
                           kind,
                           h5p_content_id,
                           max_attempts,
                           coalesce(criteria, array[]::text[])
                      from public.get_task_metadata_for_student(%s, %s, %s)
                    """,
                    (data.student_sub, course_uuid, task_uuid),
                )
                meta = cur.fetchone()
                if not meta:
                    raise LookupError("task_not_visible")
                section_uuid = str(UUID(meta[1]))
                unit_uuid = str(UUID(meta[2]))
                if not self._is_modular_section_open_or_done(
                    cur=cur,
                    course_uuid=course_uuid,
                    student_sub=data.student_sub,
                    unit_uuid=unit_uuid,
                    section_uuid=section_uuid,
                ):
                    raise LookupError("task_not_visible")
                task_kind = str(meta[3] or "native")
                max_attempts = meta[5]
                # Rubric criteria come from the helper (already filtered by RLS).
                raw_criteria = list(meta[6] or [])
                criteria = [str(entry).strip() for entry in raw_criteria if str(entry).strip()]

                # Guard against mixing task types and submission types.
                # This prevents students from spoofing a different submission kind.
                _validate_task_submission_kind(
                    task_kind=task_kind,
                    submission_kind=data.kind,
                    mime_type=data.mime_type,
                )
                if task_kind == "h5p" and (data.score_raw is None or data.score_max is None):
                    raise ValueError("invalid_h5p_payload")

                cur.execute(
                    "select public.next_attempt_nr(%s, %s, %s)",
                    (course_uuid, task_uuid, data.student_sub),
                )
                attempt_nr = int(cur.fetchone()[0])
                existing_feedback = self._find_matching_inflight_feedback_submission(
                    cur,
                    course_uuid=course_uuid,
                    task_uuid=task_uuid,
                    student_sub=data.student_sub,
                    data=data,
                )
                if existing_feedback:
                    return self._row_to_submission(existing_feedback)
                # H5P attempts are not limited at the GUSTAV DB layer (H5P can enforce its own limits).
                # Native feedback runs are stored as submissions, but only final submissions
                # consume the teacher-defined attempt limit.
                if task_kind != "h5p" and max_attempts is not None and data.intent == "submit":
                    cur.execute(
                        """
                        select count(*)
                          from public.learning_submissions
                         where course_id = %s::uuid
                           and task_id = %s::uuid
                           and student_sub = %s
                           and intent = 'submit'
                        """,
                        (course_uuid, task_uuid, data.student_sub),
                    )
                    final_attempt_count = int(cur.fetchone()[0] or 0)
                    if final_attempt_count >= int(max_attempts):
                        raise ValueError("max_attempts_exceeded")

                try:
                    analysis_mode = "text_direct"
                    if data.kind in ("image", "file"):
                        analysis_mode = "visual_direct" if task_kind in {"native", "visual"} else "ocr_text"

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

                    if data.kind == "h5p":
                        cur.execute(
                            """
                            insert into public.learning_submissions (
                                id,
                                course_id,
                                task_id,
                                section_id,
                                student_sub,
                                intent,
                                kind,
                                score_raw,
                                score_max,
                                attempt_nr,
                                analysis_status,
                                analysis_json,
                                feedback_md,
                                error_code,
                                idempotency_key,
                                completed_at
                            )
                            values (
                                    coalesce(%s::uuid, gen_random_uuid()),
                                    %s::uuid,
                                    %s::uuid,
                                    %s::uuid,
                                    %s,
                                    %s,
                                    %s,
                                    %s,
                                    %s,
                                    %s,
                                    'completed',
                                    null,
                                    null,
                                    null,
                                    %s,
                                    now()
                            )
                            on conflict (course_id, task_id, student_sub, idempotency_key)
                            do nothing
                            returning id::text,
                                      attempt_nr,
                                      intent,
                                      kind,
                                      score_raw,
                                      score_max,
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
                                section_uuid,
                                data.student_sub,
                                data.intent,
                                data.kind,
                                int(data.score_raw),
                                int(data.score_max),
                                attempt_nr,
                                norm_key,
                            ),
                        )
                    else:
                        cur.execute(
                            """
                            insert into public.learning_submissions (
                                id,
                                course_id,
                                task_id,
                                section_id,
                                student_sub,
                                intent,
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
                                idempotency_key,
                                internal_metadata
                            )
                            values (
                                    coalesce(%s::uuid, gen_random_uuid()),
                                    %s::uuid,
                                    %s::uuid,
                                    %s::uuid,
                                    %s,
                                    %s,
                                    %s,
                                    %s,
                                    %s,
                                    %s,
                                    %s,
                                    %s,
                                    %s,
                                    'pending',
                                    null,
                                    null,
                                    null,
                                    %s,
                                    jsonb_build_object('analysis_mode', %s::text)
                            )
                            on conflict (course_id, task_id, student_sub, idempotency_key)
                            do nothing
                            returning id::text,
                                      attempt_nr,
                                      intent,
                                      kind,
                                      score_raw,
                                      score_max,
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
                                section_uuid,
                                data.student_sub,
                                data.intent,
                                data.kind,
                                data.text_body,
                                data.storage_key,
                                data.mime_type,
                                data.size_bytes,
                                data.sha256,
                                attempt_nr,
                                norm_key,
                                analysis_mode,
                            ),
                        )
                    row = cur.fetchone()
                    if row is None and norm_key:
                        # Conflict occurred; fetch existing row by idempotency key
                        cur.execute(
                            """
                            select id::text,
                                   attempt_nr,
                                   intent,
                                   kind,
                                   score_raw,
                                   score_max,
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
                    if data.kind == "h5p":
                        conn.commit()
                        return self._row_to_submission(row)
                    submission_id = row[0]
                    # Enrich job payload with the visible task instruction.
                    #
                    # Why:
                    #   Visual-native uploads skip OCR and go straight into the
                    #   feedback model. The queue payload must therefore carry
                    #   the student-visible task instruction even for modular
                    #   units. `get_released_tasks_for_student(...)` is section-
                    #   shaped and can miss the concrete task here, so we read
                    #   the already-authorized task row directly.
                    instruction_md: str | None = None
                    try:
                        cur.execute(
                            """
                            select instruction_md
                              from public.unit_tasks
                             where id = %s::uuid
                            """,
                            (task_uuid,),
                        )
                        row_ctx = cur.fetchone()
                        if row_ctx:
                            instruction_md = row_ctx[0]
                    except Exception:
                        # Be tolerant: missing context must not block submissions.
                        instruction_md = None

                    job_payload = {
                        "submission_id": submission_id,
                        "course_id": course_uuid,
                        "task_id": task_uuid,
                        "task_kind": task_kind,
                        "student_sub": data.student_sub,
                        "intent": data.intent,
                        "kind": data.kind,
                        "attempt_nr": attempt_nr,
                        "criteria": criteria,
                        "instruction_md": instruction_md,
                        "analysis_mode": analysis_mode,
                    }
                    if _running_under_pytest():
                        # Tag jobs created by in-process tests so a local docker worker
                        # can be configured to ignore them (avoid race conditions).
                        job_payload["_gustav_source"] = "pytest"
                        test_run_id = _pytest_test_run_id()
                        if test_run_id:
                            job_payload["_gustav_test_run_id"] = test_run_id
                    queue_table = self._resolve_queue_table(cur)
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
                                       intent,
                                       kind,
                                       score_raw,
                                       score_max,
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

    def finalize_latest_feedback_submission(
        self,
        *,
        student_sub: str,
        course_id: str,
        task_id: str,
        idempotency_key: str | None,
    ) -> dict:
        """Persist a final submission by copying the newest completed draft.

        Why:
            The student-facing UX distinguishes between a feedback draft and a
            formal submission. Finalizing must therefore reuse the most recent
            completed draft instead of enqueueing a second analysis run.
        """
        course_uuid = str(UUID(course_id))
        task_uuid = str(UUID(task_id))

        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                self._set_current_sub(cur, student_sub)
                self._set_current_course_id(cur, course_uuid)
                cur.execute(
                    "select exists(select 1 from public.course_memberships where course_id=%s and student_id=%s)",
                    (course_uuid, student_sub),
                )
                if not bool(cur.fetchone()[0]):
                    raise PermissionError("not_course_member")

                norm_key = None
                if idempotency_key and isinstance(idempotency_key, str):
                    candidate = idempotency_key.strip()
                    norm_key = candidate if candidate else None

                if norm_key:
                    cur.execute(
                        """
                        select id::text,
                               attempt_nr,
                               intent,
                               kind,
                               score_raw,
                               score_max,
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
                           and intent = 'submit'
                           and idempotency_key = %s
                        """,
                        (course_uuid, task_uuid, student_sub, norm_key),
                    )
                    existing = cur.fetchone()
                    if existing:
                        return self._row_to_submission(existing)

                cur.execute(
                    """
                    select task_id::text,
                           section_id::text,
                           unit_id::text,
                           kind,
                           h5p_content_id,
                           max_attempts
                      from public.get_task_metadata_for_student(%s, %s, %s)
                    """,
                    (student_sub, course_uuid, task_uuid),
                )
                meta = cur.fetchone()
                if not meta:
                    raise LookupError("task_not_visible")
                section_uuid = str(UUID(meta[1]))
                unit_uuid = str(UUID(meta[2]))
                if not self._is_modular_section_open_or_done(
                    cur=cur,
                    course_uuid=course_uuid,
                    student_sub=student_sub,
                    unit_uuid=unit_uuid,
                    section_uuid=section_uuid,
                ):
                    raise LookupError("task_not_visible")

                task_kind = str(meta[3] or "native")
                max_attempts = meta[5]
                if task_kind == "h5p":
                    raise ValueError("invalid_input")

                if max_attempts is not None:
                    cur.execute(
                        """
                        select count(*)
                          from public.learning_submissions
                         where course_id = %s::uuid
                           and task_id = %s::uuid
                           and student_sub = %s
                           and intent = 'submit'
                        """,
                        (course_uuid, task_uuid, student_sub),
                    )
                    if int(cur.fetchone()[0] or 0) >= int(max_attempts):
                        raise ValueError("max_attempts_exceeded")

                cur.execute(
                    """
                    select kind,
                           score_raw,
                           score_max,
                           text_body,
                           mime_type,
                           size_bytes,
                           storage_key,
                           sha256,
                           analysis_json,
                           feedback_md,
                           coalesce(vision_attempts, 0),
                           vision_last_error,
                           feedback_last_attempt_at,
                           feedback_last_error,
                           analysis_status
                      from public.learning_submissions
                     where course_id = %s::uuid
                       and task_id = %s::uuid
                       and student_sub = %s
                       and intent = 'feedback'
                     order by created_at desc, attempt_nr desc
                     limit 1
                    """,
                    (course_uuid, task_uuid, student_sub),
                )
                latest_draft = cur.fetchone()
                if not latest_draft:
                    raise LookupError("draft_missing")
                if str(latest_draft[14] or "") != "completed":
                    raise RuntimeError("draft_not_ready")

                cur.execute(
                    "select public.next_attempt_nr(%s, %s, %s)",
                    (course_uuid, task_uuid, student_sub),
                )
                attempt_nr = int(cur.fetchone()[0])

                deterministic_id = None
                if norm_key:
                    deterministic_id = str(
                        uuid5(
                            UUID("00000000-0000-0000-0000-000000000002"),
                            f"{course_uuid}:{task_uuid}:{student_sub}:{norm_key}",
                        )
                    )

                cur.execute(
                    """
                    insert into public.learning_submissions (
                        id,
                        course_id,
                        task_id,
                        section_id,
                        student_sub,
                        intent,
                        kind,
                        score_raw,
                        score_max,
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
                        vision_attempts,
                        vision_last_error,
                        feedback_last_attempt_at,
                        feedback_last_error,
                        idempotency_key,
                        completed_at
                    )
                    values (
                        coalesce(%s::uuid, gen_random_uuid()),
                        %s::uuid,
                        %s::uuid,
                        %s::uuid,
                        %s,
                        'submit',
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        'completed',
                        %s::jsonb,
                        %s,
                        null,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        now()
                    )
                    on conflict (course_id, task_id, student_sub, idempotency_key)
                    do nothing
                    returning id::text,
                              attempt_nr,
                              intent,
                              kind,
                              score_raw,
                              score_max,
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
                        section_uuid,
                        student_sub,
                        latest_draft[0],
                        latest_draft[1],
                        latest_draft[2],
                        latest_draft[3],
                        latest_draft[6],
                        latest_draft[4],
                        latest_draft[5],
                        latest_draft[7],
                        attempt_nr,
                        Json(latest_draft[8]) if Json is not None else json.dumps(latest_draft[8]),
                        latest_draft[9],
                        latest_draft[10],
                        latest_draft[11],
                        latest_draft[12],
                        latest_draft[13],
                        norm_key,
                    ),
                )
                row = cur.fetchone()
                if row is None and norm_key:
                    cur.execute(
                        """
                        select id::text,
                               attempt_nr,
                               intent,
                               kind,
                               score_raw,
                               score_max,
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
                           and intent = 'submit'
                           and idempotency_key = %s
                        """,
                        (course_uuid, task_uuid, student_sub, norm_key),
                    )
                    row = cur.fetchone()
                conn.commit()

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
                self._set_current_course_id(cur, course_uuid)
                cur.execute(
                    "select exists(select 1 from public.course_memberships where course_id=%s and student_id=%s)",
                    (course_uuid, student_sub),
                )
                if not bool(cur.fetchone()[0]):
                    raise PermissionError("not_course_member")

                cur.execute(
                    """
                    select task_id::text,
                           section_id::text,
                           unit_id::text
                      from public.get_task_metadata_for_student(%s, %s, %s)
                    """,
                    (student_sub, course_uuid, task_uuid),
                )
                meta = cur.fetchone()
                if not meta:
                    raise LookupError("task_not_visible")
                section_uuid = str(UUID(meta[1]))
                unit_uuid = str(UUID(meta[2]))
                if not self._is_modular_section_open_or_done(
                    cur=cur,
                    course_uuid=course_uuid,
                    student_sub=student_sub,
                    unit_uuid=unit_uuid,
                    section_uuid=section_uuid,
                ):
                    raise LookupError("task_not_visible")

                cur.execute(
                    """
                    select id::text,
                           attempt_nr,
                           intent,
                           kind,
                           score_raw,
                           score_max,
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

    def get_task_kind_for_student(
        self,
        *,
        student_sub: str,
        course_id: str,
        task_id: str,
    ) -> str:
        """Return the backend task kind for a student-visible task.

        Intent:
            Provide a minimal, framework-free way for web adapters to make
            task-kind decisions (e.g., upload allowlists) without duplicating
            SQL helpers across layers.

        Security:
            Enforces course membership and released visibility using the same
            DB guards as submissions/listing paths (RLS + helpers).
        """
        course_uuid = str(UUID(course_id))
        task_uuid = str(UUID(task_id))
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                self._set_current_sub(cur, student_sub)
                self._set_current_course_id(cur, course_uuid)
                cur.execute(
                    "select exists(select 1 from public.course_memberships where course_id=%s and student_id=%s)",
                    (course_uuid, student_sub),
                )
                if not bool(cur.fetchone()[0]):
                    raise PermissionError("not_course_member")
                cur.execute(
                    """
                    select task_id::text,
                           section_id::text,
                           unit_id::text,
                           kind
                      from public.get_task_metadata_for_student(%s, %s, %s)
                    """,
                    (student_sub, course_uuid, task_uuid),
                )
                meta = cur.fetchone()
                if not meta:
                    raise LookupError("task_not_visible")
                section_uuid = str(UUID(meta[1]))
                unit_uuid = str(UUID(meta[2]))
                if not self._is_modular_section_open_or_done(
                    cur=cur,
                    course_uuid=course_uuid,
                    student_sub=student_sub,
                    unit_uuid=unit_uuid,
                    section_uuid=section_uuid,
                ):
                    raise LookupError("task_not_visible")
                kind = str(meta[3] or "native").strip() or "native"
        return kind

    def _resolve_queue_table(self, cur) -> str:
        """
        Ensure the canonical worker queue exists before inserting jobs.

        Parameters:
            cur: Open psycopg cursor operating under `gustav_limited`. The caller
                 already set `app.current_sub`, so we only assert schema state here.

        Behavior:
            - Checks `to_regclass('public.learning_submission_jobs')`.
            - Returns the canonical table name when present, otherwise aborts with a
              descriptive runtime error so API callers see a 500 instead of silently
              failing to enqueue submissions.

        Permissions:
            Requires SELECT on `pg_catalog.pg_class`, included in the default privileges
            of the application role.
        """
        cur.execute("select to_regclass('public.learning_submission_jobs')")
        reg = cur.fetchone()
        if reg and reg[0]:
            return "learning_submission_jobs"
        raise RuntimeError("Queue table public.learning_submission_jobs missing; run migrations.")

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
