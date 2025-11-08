"""Worker test: submission in 'extracted' state should reach 'completed'."""
from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

pytest.importorskip("psycopg")
import psycopg  # type: ignore  # noqa: E402

from backend.tests.utils.db import require_db_or_skip as _require_db_or_skip  # noqa: E402


def _dsn() -> str:
    host = os.getenv("TEST_DB_HOST", "127.0.0.1")
    port = os.getenv("TEST_DB_PORT", "54322")
    user = os.getenv("APP_DB_USER", "gustav_app")
    password = os.getenv("APP_DB_PASSWORD", "CHANGE_ME_DEV")
    return (
        os.getenv("LEARNING_DATABASE_URL")
        or os.getenv("DATABASE_URL")
        or f"postgresql://{user}:{password}@{host}:{port}/postgres"
    )


class _FakeOllamaClient:
    def __init__(self, response_text: str = "## Vision PDF\n\nDetected text") -> None:
        self.response_text = response_text

    def generate(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return {"response": self.response_text}


def _install_fake_ollama(monkeypatch: pytest.MonkeyPatch, *, text: str = "## Vision PDF\n\nDetected text") -> None:
    fake_module = SimpleNamespace(Client=lambda base_url=None: _FakeOllamaClient(response_text=text))
    monkeypatch.setitem(sys.modules, "ollama", fake_module)


@pytest.mark.anyio
async def test_worker_completes_pdf_from_extracted(monkeypatch: pytest.MonkeyPatch) -> None:
    _require_db_or_skip()
    worker_dsn = os.getenv("SERVICE_ROLE_DSN") or os.getenv("RLS_TEST_SERVICE_DSN")
    if not worker_dsn:
        pytest.skip("SERVICE_ROLE_DSN required for worker integration test")

    # Clean queue to avoid interference from previous runs
    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute("delete from public.learning_submission_jobs")
        conn.commit()

    # Provision minimal course/task data directly via SQL (keeps test isolated)
    teacher_sub = f"teacher-{uuid.uuid4()}"
    student_sub = f"student-{uuid.uuid4()}"
    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, false)", (teacher_sub,))
            cur.execute(
                "insert into public.courses (title, teacher_id) values (%s, %s) returning id",
                ("Vision Test Course", teacher_sub),
            )
            course_id = cur.fetchone()[0]
            cur.execute(
                "insert into public.units (title, author_id) values (%s, %s) returning id",
                ("Vision Unit", teacher_sub),
            )
            unit_id = cur.fetchone()[0]
            cur.execute(
                "insert into public.unit_sections (unit_id, title, position) values (%s, %s, %s) returning id",
                (unit_id, "Section", 1),
            )
            section_id = cur.fetchone()[0]
            cur.execute(
                """
                insert into public.unit_tasks (unit_id, section_id, instruction_md, criteria, position)
                values (%s, %s, %s, %s::text[], %s) returning id
                """,
                (unit_id, section_id, "Beschreibe den Graphen", ['Kriterium A'], 1),
            )
            task_id = cur.fetchone()[0]
            # Enrol student (new role column default already 'student')
            cur.execute(
                "insert into public.course_memberships (course_id, student_id, role) values (%s, %s, 'student')",
                (course_id, student_sub),
            )
            # Seed submission in pending state
            submission_id = uuid.uuid4()
            storage_key = f"submissions/{course_id}/{task_id}/{student_sub}/orig/sample.pdf"
            cur.execute(
                """
                insert into public.learning_submissions (
                    id, course_id, task_id, student_sub, kind,
                    text_body, storage_key, mime_type, size_bytes, sha256,
                    attempt_nr, analysis_status, analysis_json
                ) values (
                    %s::uuid, %s::uuid, %s::uuid, %s, 'file',
                    null, %s, 'application/pdf', 1024, %s,
                    1, 'pending', null
                )
                """,
                (str(submission_id), course_id, task_id, student_sub, storage_key, "0" * 64),
            )
            # Queue job payload as the use case would do
            payload = {
                "submission_id": str(submission_id),
                "course_id": str(course_id),
                "task_id": str(task_id),
                "student_sub": student_sub,
                "kind": "file",
                "attempt_nr": 1,
                "criteria": ["Kriterium A"],
            }
            cur.execute(
                "insert into public.learning_submission_jobs (submission_id, payload) values (%s::uuid, %s::jsonb)",
                (str(submission_id), json.dumps(payload)),
            )
        conn.commit()

    # Mark submission as already extracted to mimic finished render step
    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute(
                """
                update public.learning_submissions
                   set analysis_status = 'extracted',
                       analysis_json = jsonb_build_object('page_keys',
                           to_jsonb(ARRAY['k/page_0001.png','k/page_0002.png']))
                 where id = %s::uuid
                """,
                (str(submission_id),),
            )
        conn.commit()

    # Mock Ollama (pure in-memory)
    _install_fake_ollama(monkeypatch, text="### Extracted from PDF\n- line a\n- line b")
    if "dspy" in sys.modules:
        monkeypatch.delitem(sys.modules, "dspy", raising=False)

    from backend.learning.workers.process_learning_submission_jobs import run_once  # noqa: E402

    processed = run_once(
        dsn=worker_dsn,
        vision_adapter=__import__("backend.learning.adapters.local_vision", fromlist=["build"]).build(),  # type: ignore[attr-defined]
        feedback_adapter=__import__("backend.learning.adapters.local_feedback", fromlist=["build"]).build(),  # type: ignore[attr-defined]
        now=datetime.now(tz=timezone.utc),
    )
    assert processed is True

    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute(
                "select analysis_status, text_body, analysis_json from public.learning_submissions where id=%s::uuid",
                (str(submission_id),),
            )
            status, text_body, analysis_json = cur.fetchone()

    assert status == "completed"
    assert isinstance(text_body, str) and "Extracted from PDF" in text_body
    assert isinstance(analysis_json, dict) and analysis_json.get("schema") == "criteria.v2"
