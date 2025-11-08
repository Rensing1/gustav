"""
DB repo: mark_extracted transitions status, stores page keys internally.

Given a minimal seeded submission in 'pending' state, calling
DBLearningRepo.mark_extracted records the derived page keys in
`internal_metadata` (jsonb), keeps `analysis_json` null, and sets
analysis_status='extracted' without completing the submission.
"""
from __future__ import annotations

import os
import uuid

import pytest

from backend.tests.utils.db import require_db_or_skip as _require_db_or_skip


def _dsn() -> str:
    host = os.getenv("TEST_DB_HOST", "127.0.0.1")
    port = os.getenv("TEST_DB_PORT", "54322")
    user = os.getenv("APP_DB_USER", "gustav_app")
    password = os.getenv("APP_DB_PASSWORD", "CHANGE_ME_DEV")
    return os.getenv("DATABASE_URL") or f"postgresql://{user}:{password}@{host}:{port}/postgres"


@pytest.mark.anyio
async def test_mark_extracted_updates_status_and_analysis_json():
    _require_db_or_skip()
    try:
        import psycopg  # type: ignore
    except Exception:  # pragma: no cover
        pytest.skip("psycopg not available")

    # Arrange: seed minimal course/unit/section/task and a pending submission
    dsn = os.getenv("SERVICE_ROLE_DSN") or os.getenv("RLS_TEST_SERVICE_DSN") or _dsn()
    teacher = f"teacher-{uuid.uuid4()}"
    student = f"student-{uuid.uuid4()}"
    with psycopg.connect(dsn) as conn:  # type: ignore
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, false)", (teacher,))
            cur.execute("insert into public.courses (title, teacher_id) values (%s, %s) returning id", ("RepoTest Course", teacher))
            course_id = cur.fetchone()[0]
            cur.execute("insert into public.units (title, author_id) values (%s, %s) returning id", ("RepoTest Unit", teacher))
            unit_id = cur.fetchone()[0]
            cur.execute("insert into public.unit_sections (unit_id, title, position) values (%s, %s, %s) returning id", (unit_id, "S1", 1))
            section_id = cur.fetchone()[0]
            # Minimal task in section
            cur.execute(
                """
                insert into public.unit_tasks (unit_id, section_id, instruction_md, position)
                values (%s, %s, %s, %s) returning id
                """,
                (unit_id, section_id, "Do it", 1),
            )
            task_id = cur.fetchone()[0]
            # Enroll student and create a pending submission
            cur.execute(
                "insert into public.course_memberships (course_id, student_id, role) values (%s, %s, 'student')",
                (course_id, student),
            )
            # Switch session context to the student so the RLS policy allows inserting submissions
            cur.execute("select set_config('app.current_sub', %s, false)", (student,))
            sub_id = uuid.uuid4()
            cur.execute(
                """
                insert into public.learning_submissions (
                  id, course_id, task_id, student_sub, kind,
                  storage_key, mime_type, size_bytes, sha256, attempt_nr,
                  analysis_status, analysis_json
                ) values (
                  %s::uuid, %s::uuid, %s::uuid, %s, 'file',
                  %s, 'application/pdf', 1024, %s, 1,
                  'pending', null
                )
                """,
                (
                    str(sub_id),
                    str(course_id),
                    str(task_id),
                    student,
                    f"submissions/{course_id}/{task_id}/{student}/orig/sample.pdf",
                    "0" * 64,
                ),
            )
            conn.commit()

    # Act: call repo.mark_extracted
    from backend.learning.repo_db import DBLearningRepo  # type: ignore

    repo = DBLearningRepo(dsn=dsn)
    keys = [
        f"submissions/{course_id}/{task_id}/{student}/derived/{sub_id}/page_0001.png",
        f"submissions/{course_id}/{task_id}/{student}/derived/{sub_id}/page_0002.png",
    ]
    repo.mark_extracted(submission_id=str(sub_id), page_keys=keys)

    # Assert: row reflects extracted status, public analysis_json stays null,
    # internal_metadata contains the derived page keys
    with psycopg.connect(dsn) as conn:  # type: ignore
        with conn.cursor() as cur:
            cur.execute(
                """
                select analysis_status,
                       analysis_json::text,
                       internal_metadata::text,
                       completed_at is not null
                  from public.learning_submissions
                 where id=%s::uuid
                """,
                (str(sub_id),),
            )
            row = cur.fetchone()
    assert row is not None
    status, analysis_json_text, internal_metadata_text, completed = row
    assert status == "extracted"
    assert analysis_json_text in (None, "null")
    assert internal_metadata_text and '"page_keys"' in internal_metadata_text
    for k in keys:
        assert k in (internal_metadata_text or "")
    # Not completed yet at this stage
    assert completed is False
