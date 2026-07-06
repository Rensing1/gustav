"""Postgres-backed repository for the Learning context."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional, Sequence
import json
import os
import re
from backend.learning import repo_course_unit_queries as _repo_course_unit_queries
from backend.learning import repo_history_worker_queries as _repo_history_worker_queries
from backend.learning import repo_modular_unit_queries as _repo_modular_unit_queries
from backend.learning import repo_submission_command_queries as _repo_submission_command_queries
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
        """Return the newest matching in-flight feedback submission, if any."""
        return _repo_submission_command_queries.find_matching_inflight_feedback_submission(
            cur,
            course_uuid=course_uuid,
            task_uuid=task_uuid,
            student_sub=student_sub,
            data=data,
        )

    # ------------------------------------------------------------------
    def create_submission(self, data: SubmissionInput) -> dict:
        """Persist a student submission after enforcing membership and attempts."""
        return _repo_submission_command_queries.create_submission(
            self,
            data,
            psycopg_module=psycopg,
            sql_module=sql,
            json_adapter=Json,
            json_dumps=json.dumps,
            running_under_pytest=_running_under_pytest,
            pytest_test_run_id=_pytest_test_run_id,
        )

    def finalize_latest_feedback_submission(
        self,
        *,
        student_sub: str,
        course_id: str,
        task_id: str,
        idempotency_key: str | None,
    ) -> dict:
        """Persist a final submission by copying the newest completed draft."""
        return _repo_submission_command_queries.finalize_latest_feedback_submission(
            self,
            psycopg_module=psycopg,
            json_adapter=Json,
            json_dumps=json.dumps,
            student_sub=student_sub,
            course_id=course_id,
            task_id=task_id,
            idempotency_key=idempotency_key,
        )

    def list_submissions(
        self,
        *,
        student_sub: str,
        course_id: str,
        task_id: str,
        limit: int,
        offset: int,
    ) -> List[dict]:
        """Fetch the caller's submission history for a task."""
        return _repo_history_worker_queries.list_submissions(
            self,
            psycopg_module=psycopg,
            student_sub=student_sub,
            course_id=course_id,
            task_id=task_id,
            limit=limit,
            offset=offset,
        )

    def get_task_kind_for_student(
        self,
        *,
        student_sub: str,
        course_id: str,
        task_id: str,
    ) -> str:
        """Return the backend task kind for a student-visible task."""
        return _repo_history_worker_queries.get_task_kind_for_student(
            self,
            psycopg_module=psycopg,
            student_sub=student_sub,
            course_id=course_id,
            task_id=task_id,
        )

    def _resolve_queue_table(self, cur) -> str:
        """Ensure the canonical worker queue exists before inserting jobs."""
        return _repo_history_worker_queries.resolve_queue_table(cur)

    # ------------------------------------------------------------------
    def mark_extracted(self, *, submission_id: str, page_keys: List[str]) -> None:
        """Set analysis_status to 'extracted' and persist page key metadata internally."""
        _repo_history_worker_queries.mark_extracted(
            self,
            psycopg_module=psycopg,
            json_adapter=Json,
            submission_id=submission_id,
            page_keys=page_keys,
        )
