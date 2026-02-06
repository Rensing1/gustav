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
_SENSITIVE_TOKEN_PATTERN = re.compile(r"(?i)(secret|token|password|key)[-_a-z0-9]*\s*[:=]\s*\S+")
_FILESYSTEM_PATH_PATTERN = re.compile(r"(?:[A-Za-z]:\\[^\s]+|/[^\s]+)")


def _sanitize_error_message(value: Optional[str]) -> Optional[str]:
    """Strip secrets and truncate lengthy adapter errors for safe exposure."""
    if not value:
        return None
    collapsed = " ".join(str(value).split())
    if not collapsed:
        return None
    scrubbed = _SENSITIVE_TOKEN_PATTERN.sub("[redacted]", collapsed)
    scrubbed = _FILESYSTEM_PATH_PATTERN.sub("[path]", scrubbed)
    if len(scrubbed) > _ERROR_MAX_LENGTH:
        scrubbed = scrubbed[: _ERROR_MAX_LENGTH - 3].rstrip() + "..."
    return scrubbed


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
                    select unit_id::text, title, summary, unit_type, module_position
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
                        "unit_type": row[3],
                    },
                    "position": int(row[4]) if row[4] is not None else 1,
                }
            )
        return result

    # ------------------------------------------------------------------
    def get_modular_unit_graph(self, *, student_sub: str, course_id: str, unit_id: str) -> dict:
        """Return a modular unit graph payload (phases/modules/edges) for a student.

        Notes:
            Unlock/done logic is computed purely from:
            - graph metadata (`unit_modules`, `unit_phases`, `unit_module_edges`)
            - safe per-section counts (`unit_sections.tasks_total/materials_count`)
            - the student's own submissions (`learning_submissions.section_id`)

            This avoids joining `unit_tasks` for locked modules, which would
            leak content details under RLS.
        """

        course_uuid = str(UUID(course_id))
        unit_uuid = str(UUID(unit_id))
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                # RLS context
                self._set_current_sub(cur, student_sub)
                self._set_current_course_id(cur, course_uuid)

                # Course membership + unit-in-course guard (404 semantics)
                cur.execute(
                    "select exists(select 1 from public.course_memberships where course_id=%s and student_id=%s)",
                    (course_uuid, student_sub),
                )
                if not bool(cur.fetchone()[0]):
                    raise LookupError("not_course_member")
                cur.execute(
                    "select exists(select 1 from public.course_modules where course_id=%s and unit_id=%s)",
                    (course_uuid, unit_uuid),
                )
                if not bool(cur.fetchone()[0]):
                    raise LookupError("unit_not_in_course")

                cur.execute(
                    "select id::text, title, unit_type from public.units where id = %s",
                    (unit_uuid,),
                )
                unit_row = cur.fetchone()
                if not unit_row:
                    raise LookupError("unit_not_found")
                unit_type = str(unit_row[2] or "").strip().lower()
                if unit_type != "modular":
                    raise ValueError("invalid_unit_type")

                cur.execute(
                    """
                    select id::text, title, position
                    from public.unit_phases
                    where unit_id = %s
                    order by position asc, id asc
                    """,
                    (unit_uuid,),
                )
                phases = [{"id": r[0], "title": r[1], "position": int(r[2])} for r in (cur.fetchall() or [])]

                cur.execute(
                    """
                    select um.id::text,
                           um.section_id::text,
                           us.title,
                           um.phase_id::text,
                           p.position as phase_position,
                           um.position_in_phase,
                           um.required_prereq_count,
                           us.tasks_total,
                           us.materials_count
                      from public.unit_modules um
                      join public.unit_sections us on us.id = um.section_id
                      join public.unit_phases p on p.id = um.phase_id
                     where um.unit_id = %s
                     order by p.position asc, um.position_in_phase asc, um.id asc
                    """,
                    (unit_uuid,),
                )
                modules_raw: list[dict] = []
                for r in (cur.fetchall() or []):
                    modules_raw.append(
                        {
                            "id": r[0],
                            "section_id": r[1],
                            "title": r[2],
                            "phase_id": r[3],
                            "phase_position": int(r[4] or 1),
                            "position_in_phase": int(r[5] or 1),
                            "required_prereq_count": int(r[6] or 0),
                            "tasks_total": int(r[7] or 0),
                            "materials_count": int(r[8] or 0),
                        }
                    )

                cur.execute(
                    """
                    select from_module_id::text, to_module_id::text
                    from public.unit_module_edges
                    where unit_id = %s
                    order by from_module_id asc, to_module_id asc
                    """,
                    (unit_uuid,),
                )
                edges = [{"from": r[0], "to": r[1]} for r in (cur.fetchall() or [])]

                # Aggregate tasks_done per module-section from the student's submissions.
                section_ids = [m["section_id"] for m in modules_raw]
                tasks_done_by_section: dict[str, int] = {}
                if section_ids:
                    cur.execute(
                        """
                        select section_id::text,
                               count(distinct task_id)::int as tasks_done
                          from public.learning_submissions
                         where course_id = %s::uuid
                           and student_sub = %s
                           and section_id = any(%s::uuid[])
                           and (kind <> 'h5p' or score_raw = score_max)
                         group by section_id
                        """,
                        (course_uuid, student_sub, section_ids),
                    )
                    tasks_done_by_section = {r[0]: int(r[1] or 0) for r in (cur.fetchall() or [])}

                module_state = self._compute_modular_unit_module_states(
                    ordered_modules=modules_raw,
                    edges=edges,
                    tasks_done_by_section=tasks_done_by_section,
                )

                modules: list[dict] = []
                for m in modules_raw:
                    s = module_state.get(m["id"], {})
                    modules.append(
                        {
                            "id": m["id"],
                            "title": m["title"],
                            "phase_id": m["phase_id"],
                            "position_in_phase": int(m["position_in_phase"]),
                            "required_prereq_count": int(m["required_prereq_count"]),
                            "prereq_done": int(s.get("prereq_done") or 0),
                            "prereq_required": int(s.get("prereq_required") or 0),
                            "tasks_done": int(s.get("tasks_done") or 0),
                            "tasks_total": int(m["tasks_total"]),
                            "materials_count": int(m["materials_count"]),
                            "status": str(s.get("status") or "locked"),
                        }
                    )

        return {
            "unit": {"id": unit_row[0], "title": unit_row[1], "unit_type": unit_type},
            "phases": phases,
            "modules": modules,
            "edges": edges,
        }

    @staticmethod
    def _compute_modular_unit_module_states(
        *,
        ordered_modules: list[dict],
        edges: list[dict],
        tasks_done_by_section: dict[str, int],
    ) -> dict[str, dict]:
        """Compute unlocked/done/status for a modular unit.

        Why:
            We want one deterministic implementation of the unlock algorithm,
            shared by:
            - the graph endpoint (advance organizer)
            - the module content endpoint (locked -> 404)

        Important:
            The DB enforces an acyclic graph via triggers:
            - same phase: only left -> right edges
            - cross phase: only earlier -> later phase edges
            Therefore, iterating modules in (phase.position, position_in_phase)
            order is a valid topological order.
        """
        incoming: dict[str, list[str]] = {m["id"]: [] for m in ordered_modules}
        for e in edges:
            to_id = str(e.get("to") or "")
            from_id = str(e.get("from") or "")
            if to_id in incoming:
                incoming[to_id].append(from_id)

        state: dict[str, dict] = {}
        for m in ordered_modules:
            module_id = m["id"]
            section_id = m["section_id"]
            tasks_total = int(m.get("tasks_total") or 0)
            required_prereq_count = int(m.get("required_prereq_count") or 0)

            incoming_ids = incoming.get(module_id, [])
            prereq_required = min(max(required_prereq_count, 0), len(incoming_ids))
            prereq_done = sum(1 for from_id in incoming_ids if bool(state.get(from_id, {}).get("done")))
            unlocked = prereq_required == 0 or prereq_done >= prereq_required

            raw_tasks_done = int(tasks_done_by_section.get(section_id, 0))
            tasks_done = min(raw_tasks_done, tasks_total) if tasks_total > 0 else 0
            done = bool(unlocked and (tasks_total == 0 or tasks_done >= tasks_total))
            status = "done" if done else ("open" if unlocked else "locked")

            state[module_id] = {
                "unlocked": unlocked,
                "done": done,
                "status": status,
                "prereq_required": prereq_required,
                "prereq_done": prereq_done,
                "tasks_done": tasks_done,
            }
        return state

    def _is_modular_section_open_or_done(
        self,
        *,
        cur,
        course_uuid: str,
        student_sub: str,
        unit_uuid: str,
        section_uuid: str,
    ) -> bool:
        """Return True if a modular section's module is open/done for the student.

        Why:
            For modular units, we must not accept submissions for tasks in locked
            modules (even if a client knows the task_id). Otherwise students could
            bypass the intended progression by submitting to hidden tasks.

        Notes:
            - For linear units this helper is not used (releases are checked elsewhere).
            - This runs under RLS with `app.current_sub` and `app.current_course_id`
              already set by the caller.
        """
        cur.execute(
            """
            select um.id::text
              from public.unit_modules um
              join public.units u on u.id = um.unit_id
             where um.unit_id = %s::uuid
               and um.section_id = %s::uuid
               and u.unit_type = 'modular'
             limit 1
            """,
            (unit_uuid, section_uuid),
        )
        row = cur.fetchone()
        if not row:
            return True  # not a modular module-section mapping
        module_id = str(row[0])

        cur.execute(
            """
            select um.id::text,
                   um.section_id::text,
                   um.required_prereq_count,
                   us.tasks_total,
                   p.position as phase_position,
                   um.position_in_phase
              from public.unit_modules um
              join public.unit_sections us on us.id = um.section_id
              join public.unit_phases p on p.id = um.phase_id
             where um.unit_id = %s::uuid
             order by p.position asc, um.position_in_phase asc, um.id asc
            """,
            (unit_uuid,),
        )
        modules_raw = [
            {
                "id": r[0],
                "section_id": r[1],
                "required_prereq_count": int(r[2] or 0),
                "tasks_total": int(r[3] or 0),
                "phase_position": int(r[4] or 1),
                "position_in_phase": int(r[5] or 1),
            }
            for r in (cur.fetchall() or [])
        ]
        if not modules_raw:
            return False

        cur.execute(
            """
            select from_module_id::text, to_module_id::text
            from public.unit_module_edges
            where unit_id = %s
            order by from_module_id asc, to_module_id asc
            """,
            (unit_uuid,),
        )
        edges = [{"from": r[0], "to": r[1]} for r in (cur.fetchall() or [])]

        section_ids = [m["section_id"] for m in modules_raw]
        tasks_done_by_section: dict[str, int] = {}
        if section_ids:
            cur.execute(
                """
                select section_id::text,
                       count(distinct task_id)::int as tasks_done
                  from public.learning_submissions
                 where course_id = %s::uuid
                   and student_sub = %s
                   and section_id = any(%s::uuid[])
                   and (kind <> 'h5p' or score_raw = score_max)
                 group by section_id
                """,
                (course_uuid, student_sub, section_ids),
            )
            tasks_done_by_section = {r[0]: int(r[1] or 0) for r in (cur.fetchall() or [])}

        module_state = self._compute_modular_unit_module_states(
            ordered_modules=modules_raw,
            edges=edges,
            tasks_done_by_section=tasks_done_by_section,
        )
        status = str((module_state.get(module_id) or {}).get("status") or "")
        return status in {"open", "done"}

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
        course_uuid = str(UUID(course_id))
        unit_uuid = str(UUID(unit_id))
        module_uuid = str(UUID(module_id))
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                # RLS context
                self._set_current_sub(cur, student_sub)
                self._set_current_course_id(cur, course_uuid)

                # Course membership + unit-in-course guard (404 semantics)
                cur.execute(
                    "select exists(select 1 from public.course_memberships where course_id=%s and student_id=%s)",
                    (course_uuid, student_sub),
                )
                if not bool(cur.fetchone()[0]):
                    raise LookupError("not_course_member")
                cur.execute(
                    "select exists(select 1 from public.course_modules where course_id=%s and unit_id=%s)",
                    (course_uuid, unit_uuid),
                )
                if not bool(cur.fetchone()[0]):
                    raise LookupError("unit_not_in_course")

                # Defense-in-depth: route already enforces modular-only, but keep
                # the repo method safe when called directly.
                cur.execute("select unit_type from public.units where id = %s", (unit_uuid,))
                unit_row = cur.fetchone()
                if not unit_row:
                    raise LookupError("unit_not_found")
                unit_type = str(unit_row[0] or "").strip().lower()
                if unit_type != "modular":
                    raise ValueError("invalid_unit_type")

                cur.execute(
                    """
                    select um.id::text,
                           um.section_id::text,
                           us.title,
                           um.unit_id::text,
                           um.phase_id::text,
                           um.position_in_phase
                      from public.unit_modules um
                      join public.unit_sections us on us.id = um.section_id
                     where um.id = %s
                       and um.unit_id = %s
                    """,
                    (module_uuid, unit_uuid),
                )
                row = cur.fetchone()
                if not row:
                    raise LookupError("module_not_found")

                # Locked modules are intentionally indistinguishable from missing modules.
                # This prevents enumeration via guessed module_ids.
                cur.execute(
                    """
                    select um.id::text,
                           um.section_id::text,
                           um.required_prereq_count,
                           us.tasks_total,
                           p.position as phase_position,
                           um.position_in_phase
                      from public.unit_modules um
                      join public.unit_sections us on us.id = um.section_id
                      join public.unit_phases p on p.id = um.phase_id
                     where um.unit_id = %s
                     order by p.position asc, um.position_in_phase asc, um.id asc
                    """,
                    (unit_uuid,),
                )
                modules_raw = [
                    {
                        "id": r[0],
                        "section_id": r[1],
                        "required_prereq_count": int(r[2] or 0),
                        "tasks_total": int(r[3] or 0),
                        "phase_position": int(r[4] or 1),
                        "position_in_phase": int(r[5] or 1),
                    }
                    for r in (cur.fetchall() or [])
                ]
                cur.execute(
                    """
                    select from_module_id::text, to_module_id::text
                    from public.unit_module_edges
                    where unit_id = %s
                    order by from_module_id asc, to_module_id asc
                    """,
                    (unit_uuid,),
                )
                edges = [{"from": r[0], "to": r[1]} for r in (cur.fetchall() or [])]

                section_ids = [m["section_id"] for m in modules_raw]
                tasks_done_by_section: dict[str, int] = {}
                if section_ids:
                    cur.execute(
                        """
                        select section_id::text,
                               count(distinct task_id)::int as tasks_done
                          from public.learning_submissions
                         where course_id = %s::uuid
                           and student_sub = %s
                           and section_id = any(%s::uuid[])
                           and (kind <> 'h5p' or score_raw = score_max)
                         group by section_id
                        """,
                        (course_uuid, student_sub, section_ids),
                    )
                    tasks_done_by_section = {r[0]: int(r[1] or 0) for r in (cur.fetchall() or [])}

                module_state = self._compute_modular_unit_module_states(
                    ordered_modules=modules_raw,
                    edges=edges,
                    tasks_done_by_section=tasks_done_by_section,
                )
                # Fail closed: all state lookups use canonical UUID strings.
                status = str((module_state.get(module_uuid) or {}).get("status") or "locked")
                if status == "locked":
                    raise LookupError("module_locked")

                section_id = row[1]
                module = {
                    "id": row[0],
                    "title": row[2],
                    "unit_id": row[3],
                    "phase_id": row[4],
                    "position_in_phase": int(row[5] or 1),
                }

                materials: list[dict] = []
                tasks: list[dict] = []
                if include_materials:
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
                               position,
                               to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                               to_char(updated_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
                          from public.unit_materials
                         where section_id = %s::uuid
                         order by position asc, id asc
                        """,
                        (section_id,),
                    )
                    for r in (cur.fetchall() or []):
                        materials.append(
                            {
                                "id": r[0],
                                "title": r[1],
                                "kind": r[2],
                                "body_md": r[3],
                                "mime_type": r[4],
                                "size_bytes": r[5],
                                "filename_original": r[6],
                                "storage_key": r[7],
                                "sha256": r[8],
                                "alt_text": r[9],
                                "position": int(r[10]) if r[10] is not None else None,
                                "created_at": r[11],
                                "updated_at": r[12],
                            }
                        )

                if include_tasks:
                    cur.execute(
                        """
                        select id::text,
                               instruction_md,
                               criteria,
                               case
                                 when due_at is null then null
                                 else to_char(due_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
                               end as due_at_iso,
                               max_attempts,
                               kind,
                               h5p_content_id,
                               h5p_display_options,
                               position,
                               to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                               to_char(updated_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
                          from public.unit_tasks
                         where section_id = %s::uuid
                         order by position asc, id asc
                        """,
                        (section_id,),
                    )
                    for r in (cur.fetchall() or []):
                        kind = str(r[5] or "native")
                        h5p_content_id = r[6]
                        h5p_display_options = r[7]
                        display_options = h5p_display_options if isinstance(h5p_display_options, dict) else {}
                        h5p = None
                        visual = None
                        if kind == "h5p":
                            h5p = {
                                "content_id": (str(h5p_content_id) if h5p_content_id is not None else None),
                                "display_options": display_options,
                            }
                        elif kind == "visual":
                            visual = {}
                        tasks.append(
                            {
                                "id": r[0],
                                "instruction_md": r[1],
                                "criteria": list(r[2] or []),
                                "due_at": r[3],
                                "max_attempts": r[4],
                                "kind": kind,
                                "h5p": h5p,
                                "visual": visual,
                                "position": int(r[8]) if r[8] is not None else None,
                                "created_at": r[9],
                                "updated_at": r[10],
                            }
                        )

        return {"module": module, "materials": materials, "tasks": tasks}

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
                       due_at_iso,
                       max_attempts,
                       kind,
                       h5p_content_id,
                       h5p_display_options,
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
            kind = str(row[5] or "native")
            h5p_content_id = row[6]
            h5p_display_options = row[7]
            display_options = h5p_display_options if isinstance(h5p_display_options, dict) else {}
            h5p = None
            visual = None
            if kind == "h5p":
                h5p = {"content_id": (str(h5p_content_id) if h5p_content_id is not None else None), "display_options": display_options}
            elif kind == "visual":
                visual = {}
            tasks.append(
                {
                    "id": row[0],
                    "instruction_md": row[1],
                    "criteria": list(row[2] or []),
                    "due_at": row[3],
                    "max_attempts": row[4],
                    "kind": kind,
                    "h5p": h5p,
                    "visual": visual,
                    "position": int(row[8]) if row[8] is not None else None,
                    "created_at": row[9],
                    "updated_at": row[10],
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

    def is_h5p_content_released_for_student(self, *, student_sub: str, course_id: str, content_id: str) -> bool:
        """Return True when the student may access this H5P content in the course.

        Why:
            The H5P sidecar needs a small, fail-closed authorization check to
            prevent enumeration of all released tasks/IDs and to avoid fragile
            pagination in the browser-facing service.

        Security:
            - Enforces membership via course_memberships.
            - Enforces release visibility via module_section_releases.visible.
            - Restricts to `unit_tasks.kind='h5p'` and matching `h5p_content_id`.
            - Runs under gustav_limited with `app.current_sub` set.
        """
        course_uuid = str(UUID(course_id))
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                self._set_current_sub(cur, student_sub)
                # Course-scoped context is required for modular unit access checks
                # (student_can_access_section uses app.current_course_id).
                self._set_current_course_id(cur, course_uuid)

                # Fail-closed: unauthenticated or non-member callers must not be able
                # to probe which H5P content IDs exist.
                cur.execute(
                    "select exists(select 1 from public.course_memberships where course_id=%s and student_id=%s)",
                    (course_uuid, student_sub),
                )
                if not bool((cur.fetchone() or [False])[0]):
                    return False

                # A content_id can theoretically be reused across tasks/units.
                # Allow access if ANY matching H5P task is accessible in this course.
                cur.execute(
                    """
                    select t.unit_id::text,
                           t.section_id::text,
                           u.unit_type,
                           m.id::text as course_module_id
                      from public.course_modules m
                      join public.unit_tasks t on t.unit_id = m.unit_id
                      join public.units u on u.id = t.unit_id
                     where m.course_id = %s::uuid
                       and t.kind = 'h5p'
                       and t.h5p_content_id = %s
                    """,
                    (course_uuid, str(content_id)),
                )
                candidates = cur.fetchall() or []
                if not candidates:
                    return False

                for unit_id, section_id, unit_type, course_module_id in candidates:
                    norm_type = str(unit_type or "").strip().lower()
                    if norm_type == "linear":
                        cur.execute(
                            """
                            select exists(
                                     select 1
                                       from public.module_section_releases r
                                      where r.course_module_id = %s::uuid
                                        and r.section_id = %s::uuid
                                        and coalesce(r.visible, false) = true
                                   )
                            """,
                            (course_module_id, section_id),
                        )
                        if bool((cur.fetchone() or [False])[0]):
                            return True
                    elif norm_type == "modular":
                        # Compute unlock state from graph + student's submissions.
                        cur.execute(
                            "select id::text from public.unit_modules where unit_id=%s::uuid and section_id=%s::uuid",
                            (unit_id, section_id),
                        )
                        module_row = cur.fetchone()
                        if not module_row:
                            continue
                        module_id = str(module_row[0])

                        cur.execute(
                            """
                            select um.id::text,
                                   um.section_id::text,
                                   um.required_prereq_count,
                                   us.tasks_total,
                                   p.position as phase_position,
                                   um.position_in_phase
                              from public.unit_modules um
                              join public.unit_sections us on us.id = um.section_id
                              join public.unit_phases p on p.id = um.phase_id
                             where um.unit_id = %s::uuid
                             order by p.position asc, um.position_in_phase asc, um.id asc
                            """,
                            (unit_id,),
                        )
                        modules_raw = [
                            {
                                "id": r[0],
                                "section_id": r[1],
                                "required_prereq_count": int(r[2] or 0),
                                "tasks_total": int(r[3] or 0),
                                "phase_position": int(r[4] or 1),
                                "position_in_phase": int(r[5] or 1),
                            }
                            for r in (cur.fetchall() or [])
                        ]
                        cur.execute(
                            """
                            select from_module_id::text, to_module_id::text
                            from public.unit_module_edges
                            where unit_id = %s::uuid
                            order by from_module_id asc, to_module_id asc
                            """,
                            (unit_id,),
                        )
                        edges = [{"from": r[0], "to": r[1]} for r in (cur.fetchall() or [])]

                        section_ids = [m["section_id"] for m in modules_raw]
                        tasks_done_by_section: dict[str, int] = {}
                        if section_ids:
                            cur.execute(
                                """
                                select section_id::text,
                                       count(distinct task_id)::int as tasks_done
                                  from public.learning_submissions
                                 where course_id = %s::uuid
                                   and student_sub = %s
                                   and section_id = any(%s::uuid[])
                                   and (kind <> 'h5p' or score_raw = score_max)
                                 group by section_id
                                """,
                                (course_uuid, student_sub, section_ids),
                            )
                            tasks_done_by_section = {r[0]: int(r[1] or 0) for r in (cur.fetchall() or [])}

                        module_state = self._compute_modular_unit_module_states(
                            ordered_modules=modules_raw,
                            edges=edges,
                            tasks_done_by_section=tasks_done_by_section,
                        )
                        status = str((module_state.get(module_id) or {}).get("status") or "")
                        if status in {"open", "done"}:
                            return True

                return False

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
                if task_kind == "h5p":
                    if data.kind != "h5p":
                        raise ValueError("invalid_input")
                    if data.score_raw is None or data.score_max is None:
                        raise ValueError("invalid_h5p_payload")
                elif task_kind == "visual":
                    # Visual tasks are upload-only. Text or H5P payloads are rejected.
                    if data.kind not in ("image", "file"):
                        raise ValueError("invalid_input")
                else:
                    if data.kind == "h5p":
                        raise ValueError("invalid_h5p_payload")

                cur.execute(
                    "select public.next_attempt_nr(%s, %s, %s)",
                    (course_uuid, task_uuid, data.student_sub),
                )
                attempt_nr = int(cur.fetchone()[0])
                # H5P attempts are not limited at the GUSTAV DB layer (H5P can enforce its own limits).
                if task_kind != "h5p" and max_attempts is not None and attempt_nr > int(max_attempts):
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

                    if data.kind == "h5p":
                        cur.execute(
                            """
                            insert into public.learning_submissions (
                                id,
                                course_id,
                                task_id,
                                section_id,
                                student_sub,
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
                                    'pending',
                                    null,
                                    null,
                                    null,
                                    %s
                            )
                            on conflict (course_id, task_id, student_sub, idempotency_key)
                            do nothing
                            returning id::text,
                                      attempt_nr,
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
                    # Enrich job payload with task instruction for the Feedback adapter.
                    instruction_md: str | None = None
                    try:
                        section_id = str(meta[1])  # from get_task_metadata_for_student
                        cur.execute(
                            """
                            select id::text, instruction_md
                              from public.get_released_tasks_for_student(%s, %s, %s)
                            """,
                            (data.student_sub, course_uuid, section_id),
                        )
                        rows_ctx = cur.fetchall() or []
                        for tid, instr in rows_ctx:
                            if str(tid) == task_uuid:
                                instruction_md = instr
                                break
                    except Exception:
                        # Be tolerant: missing helper or columns shouldn't block submissions
                        instruction_md = None

                    job_payload = {
                        "submission_id": submission_id,
                        "course_id": course_uuid,
                        "task_id": task_uuid,
                        "task_kind": task_kind,
                        "student_sub": data.student_sub,
                        "kind": data.kind,
                        "attempt_nr": attempt_nr,
                        "criteria": criteria,
                        "instruction_md": instruction_md,
                    }
                    if _running_under_pytest():
                        # Tag jobs created by in-process tests so a local docker worker
                        # can be configured to ignore them (avoid race conditions).
                        job_payload["_gustav_source"] = "pytest"
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
            score_raw,
            score_max,
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
        if kind == "h5p":
            analysis_payload = None
        elif status != "completed":
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
            "score_raw": score_raw,
            "score_max": score_max,
            "text_body": text_body,
            "mime_type": mime_type,
            "size_bytes": size_bytes,
            "storage_key": storage_key,
            "sha256": sha256,
            "analysis_status": status,
            "analysis_json": analysis_payload,
            # Expose feedback only after analysis is fully completed.
            "feedback_md": feedback_md if status == "completed" else None,
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
