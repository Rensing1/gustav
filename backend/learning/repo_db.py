"""Postgres-backed repository for the Learning context."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, List, Optional
import os
import re
from uuid import UUID

try:  # pragma: no cover -- optional dependency in some environments
    import psycopg

    HAVE_PSYCOPG = True
except Exception:  # pragma: no cover
    psycopg = None  # type: ignore
    HAVE_PSYCOPG = False


def _default_limited_dsn() -> str:
    host = os.getenv("TEST_DB_HOST", "127.0.0.1")
    port = os.getenv("TEST_DB_PORT", "54322")
    return f"postgresql://gustav_limited:gustav-limited@{host}:{port}/postgres"


def _dsn() -> str:
    for candidate in (
        os.getenv("LEARNING_DATABASE_URL"),
        os.getenv("LEARNING_DB_URL"),
        os.getenv("DATABASE_URL"),
        _default_limited_dsn(),
    ):
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
        user = self._dsn_username(self._dsn)
        allow_override = str(os.getenv("ALLOW_SERVICE_DSN_FOR_TESTING", "")).lower() == "true"
        if user != "gustav_limited" and not allow_override:
            raise RuntimeError("LearningRepo requires gustav_limited DSN")

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
            entry = {
                "section": {
                    "id": section_id,
                    "title": row[1],
                    "position": int(row[2]) if row[2] is not None else None,
                },
                "materials": [],
                "tasks": [],
            }
            if include_materials:
                entry["materials"] = self._fetch_materials(student_sub, course_uuid, section_id)
            if include_tasks:
                entry["tasks"] = self._fetch_tasks(student_sub, course_uuid, section_id)
            sections.append(entry)
        return sections

    def _fetch_materials(self, student_sub: str, course_id: str, section_id: str) -> List[dict]:
        with psycopg.connect(self._dsn) as conn:
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

    def _fetch_tasks(self, student_sub: str, course_id: str, section_id: str) -> List[dict]:
        with psycopg.connect(self._dsn) as conn:
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

    # ------------------------------------------------------------------
    def create_submission(self, data: SubmissionInput) -> dict:
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

                if data.idempotency_key:
                    cur.execute(
                        """
                        select id::text,
                               attempt_nr,
                               kind,
                               text_body,
                               mime_type,
                               size_bytes,
                               sha256,
                               analysis_status,
                               analysis_json,
                               feedback_md,
                               error_code,
                               to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                               to_char(completed_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
                          from public.learning_submissions
                         where course_id = %s
                           and task_id = %s
                           and student_sub = %s
                           and idempotency_key = %s
                        """,
                        (course_uuid, task_uuid, data.student_sub, data.idempotency_key),
                    )
                    existing = cur.fetchone()
                    if existing:
                        return self._row_to_submission(existing)

                cur.execute(
                    """
                    select task_id::text,
                           section_id::text,
                           unit_id::text,
                           max_attempts
                      from public.get_task_metadata_for_student(%s, %s, %s)
                    """,
                    (data.student_sub, course_uuid, task_uuid),
                )
                meta = cur.fetchone()
                if not meta:
                    raise LookupError("task_not_visible")
                max_attempts = meta[3]

                cur.execute(
                    "select public.next_attempt_nr(%s, %s, %s)",
                    (course_uuid, task_uuid, data.student_sub),
                )
                attempt_nr = int(cur.fetchone()[0])
                if max_attempts is not None and attempt_nr > int(max_attempts):
                    raise ValueError("max_attempts_exceeded")

                feedback_md = self._render_feedback(data.kind, attempt_nr)

                cur.execute(
                    """
                    insert into public.learning_submissions (
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
                    values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            'completed', null, %s, null, %s)
                    returning id::text,
                              attempt_nr,
                              kind,
                              text_body,
                              mime_type,
                              size_bytes,
                              sha256,
                              analysis_status,
                              analysis_json,
                              feedback_md,
                              error_code,
                              to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                              to_char(completed_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
                    """,
                    (
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
                        feedback_md,
                        data.idempotency_key,
                    ),
                )
                row = cur.fetchone()
                conn.commit()
        return self._row_to_submission(row)

    @staticmethod
    def _render_feedback(kind: str, attempt: int) -> str:
        if kind == "text":
            return f"Attempt {attempt}: Good job!"
        return f"Attempt {attempt}: Image received."

    @staticmethod
    def _row_to_submission(row: Iterable[Any]) -> dict:
        return {
            "id": row[0],
            "attempt_nr": int(row[1]),
            "kind": row[2],
            "text_body": row[3],
            "mime_type": row[4],
            "size_bytes": row[5],
            "sha256": row[6],
            "analysis_status": row[7],
            "analysis_json": row[8],
            "feedback_md": row[9],
            "error_code": row[10],
            "created_at": row[11],
            "completed_at": row[12],
        }
