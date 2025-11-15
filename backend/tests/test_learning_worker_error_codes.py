"""
Regression tests for worker SQL helpers accepting the new `input_*` error codes.

We exercise the `learning_worker_update_failed` function directly against the
database to ensure it no longer rejects preprocessing failures such as
`input_corrupt` or `input_too_large`. The tests run only when a service-role
DSN is available (same requirement as the other worker SQL integration tests).
"""
from __future__ import annotations

import os
import uuid

import pytest

from backend.tests.utils.db import require_db_or_skip as _require_db_or_skip

pytest.importorskip("psycopg")
import psycopg  # type: ignore  # noqa: E402


def _service_dsn() -> str:
    return os.getenv("SERVICE_ROLE_DSN") or os.getenv("RLS_TEST_SERVICE_DSN") or ""


def _seed_pending_submission() -> str:
    """Insert a minimal pending PDF submission via SQL (service DSN)."""
    _require_db_or_skip()
    service_dsn = _service_dsn()
    if not service_dsn:
        pytest.skip("SERVICE_ROLE_DSN or RLS_TEST_SERVICE_DSN required for worker SQL test")

    teacher_sub = f"teacher-{uuid.uuid4()}"
    student_sub = f"student-{uuid.uuid4()}"
    submission_id = uuid.uuid4()
    storage_key = f"submissions/{uuid.uuid4()}/{uuid.uuid4()}/{student_sub}/orig/sample.pdf"

    with psycopg.connect(service_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, false)", (teacher_sub,))
            cur.execute(
                "insert into public.courses (title, teacher_id) values (%s, %s) returning id",
                ("Worker SQL Course", teacher_sub),
            )
            course_id = cur.fetchone()[0]
            cur.execute(
                "insert into public.units (title, author_id) values (%s, %s) returning id",
                ("Unit", teacher_sub),
            )
            unit_id = cur.fetchone()[0]
            cur.execute(
                "insert into public.unit_sections (unit_id, title, position) values (%s, %s, %s) returning id",
                (unit_id, "Section", 1),
            )
            section_id = cur.fetchone()[0]
            cur.execute(
                """
                insert into public.unit_tasks (unit_id, section_id, instruction_md, position)
                values (%s, %s, %s, %s) returning id
                """,
                (unit_id, section_id, "Analyse das PDF", 1),
            )
            task_id = cur.fetchone()[0]
            cur.execute(
                "insert into public.course_memberships (course_id, student_id, role) values (%s, %s, 'student')",
                (course_id, student_sub),
            )
            cur.execute("select set_config('app.current_sub', %s, false)", (student_sub,))
            cur.execute(
                """
                insert into public.learning_submissions (
                    id, course_id, task_id, student_sub, kind,
                    storage_key, mime_type, size_bytes, sha256, attempt_nr,
                    analysis_status, analysis_json, text_body, feedback_md, error_code
                ) values (
                    %s::uuid, %s::uuid, %s::uuid, %s, 'file',
                    %s, 'application/pdf', 4096, %s, 1,
                    'pending', null, null, null, null
                )
                """,
                (
                    str(submission_id),
                    str(course_id),
                    str(task_id),
                    student_sub,
                    storage_key,
                    "a" * 64,
                ),
            )
        conn.commit()

    return str(submission_id)


@pytest.mark.anyio
@pytest.mark.parametrize("error_code", ["input_corrupt", "input_unsupported", "input_too_large"])
async def test_worker_update_failed_accepts_input_error_codes(error_code: str) -> None:
    """Worker helper should accept preprocessing error codes and persist them verbatim."""
    submission_id = _seed_pending_submission()
    dsn = _service_dsn()
    if not dsn:
        pytest.skip("SERVICE_ROLE_DSN required for worker error code regression test")

    failure_msg = f"guard for {error_code}"

    with psycopg.connect(dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute(
                "select public.learning_worker_update_failed(%s::uuid, %s::text, %s::text)",
                (submission_id, error_code, failure_msg),
            )
        conn.commit()

        with conn.cursor() as cur:
            cur.execute(
                """
                select analysis_status, error_code, vision_last_error, vision_attempts
                  from public.learning_submissions
                 where id = %s::uuid
                """,
                (submission_id,),
            )
            row = cur.fetchone()

    assert row is not None, "expected submission row"
    status, code, last_error, attempts = row
    assert status == "failed"
    assert code == error_code
    assert last_error == failure_msg[:1024]
    assert attempts in (None, 0)
