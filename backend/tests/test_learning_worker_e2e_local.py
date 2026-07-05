"""
E2E-style tests for the learning worker using local DSPy adapters (stubbed).

Intent:
    Validate the real worker logic against a real test database without
    performing real LLM/VLM network calls.

Coverage:
    - Text submissions: pending → completed, preserving student text.
    - Image submissions without bytes: Vision schedules a retry (pending).
"""

from __future__ import annotations

import json
import os
import sys
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

pytest.importorskip("psycopg")
pytestmark = pytest.mark.db_write

import psycopg  # type: ignore  # noqa: E402

from backend.learning.adapters.ports import FeedbackResult  # noqa: E402
from backend.learning.repo_db import DBLearningRepo  # noqa: E402
from backend.learning.usecases.submissions import (  # noqa: E402
    CreateSubmissionInput,
    CreateSubmissionUseCase,
)
from backend.tests.test_learning_api_contract import _prepare_learning_fixture  # type: ignore  # noqa: E402
from backend.tests.utils.db import require_db_or_skip as _require_db_or_skip  # noqa: E402
from backend.tests.utils.db_isolation import cleanup_learning_jobs_for_run, current_test_run_id  # noqa: E402


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


def _install_fake_dspy(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeLM:
        def __init__(self, model: str, **_kwargs) -> None:
            self.model = model

    class _FakeJSONAdapter:
        pass

    @contextmanager
    def _ctx(**_kwargs):  # type: ignore[no-untyped-def]
        yield

    monkeypatch.setitem(
        sys.modules,
        "dspy",
        SimpleNamespace(
            __version__="0.0-test",
            LM=_FakeLM,
            JSONAdapter=_FakeJSONAdapter,
            context=_ctx,
        ),
    )


@pytest.mark.anyio
async def test_worker_completes_text_submission(monkeypatch: pytest.MonkeyPatch) -> None:
    _require_db_or_skip()
    fixture = await _prepare_learning_fixture()
    test_run_id = current_test_run_id()
    dsn = _dsn()
    worker_dsn = os.getenv("SERVICE_ROLE_DSN") or dsn

    # Ensure deterministic env for local_feedback (required even when DSPy is stubbed).
    monkeypatch.setenv("OPENAI_BASE_URL", "http://example/api/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("AI_TEXT_MODEL", "text-model")
    _install_fake_dspy(monkeypatch)

    from backend.learning.adapters.dspy import feedback_program

    monkeypatch.setattr(
        feedback_program,
        "analyze_feedback",
        lambda **_: FeedbackResult(
            feedback_md="**Das ist dir gut gelungen:** A.\n\n**Das kannst du besser:** B.",
            analysis_json={"schema": "criteria.v2", "score": 4, "criteria_results": []},
            parse_status="parsed_structured",
        ),
    )

    # Clean queue + previous submissions for idempotency key.
    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cleanup_learning_jobs_for_run(conn, test_run_id)
            cur.execute("select set_config('app.current_sub', %s, false)", (fixture.student_sub,))
            cur.execute(
                """
                delete from public.learning_submissions
                 where student_sub = %s
                   and idempotency_key in ('e2e-local-text')
                """,
                (fixture.student_sub,),
            )
        conn.commit()

    repo = DBLearningRepo(dsn=dsn)
    create = CreateSubmissionUseCase(repo)
    submission = create.execute(
        CreateSubmissionInput(
            course_id=fixture.course_id,
            task_id=fixture.task["id"],
            student_sub=fixture.student_sub,
            kind="text",
            text_body="# Draft text",
            storage_key=None,
            mime_type=None,
            size_bytes=None,
            sha256=None,
            score_raw=None,
            score_max=None,
            idempotency_key="e2e-local-text",
        )
    )
    submission_id = submission["id"]

    import importlib

    local_vision = importlib.import_module("backend.learning.adapters.local_vision").build()  # type: ignore[attr-defined]
    local_feedback = importlib.import_module("backend.learning.adapters.local_feedback").build()  # type: ignore[attr-defined]

    from backend.learning.workers.process_learning_submission_jobs import run_once  # type: ignore

    processed = run_once(
        dsn=worker_dsn,
        vision_adapter=local_vision,
        feedback_adapter=local_feedback,
        now=datetime.now(tz=timezone.utc),
        test_run_id=test_run_id,
    )
    assert processed is True

    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute(
                """
                select analysis_status, text_body, analysis_json, feedback_md
                  from public.learning_submissions
                 where id = %s::uuid
                """,
                (submission_id,),
            )
            status, text_body, analysis_json, feedback_md = cur.fetchone()

    assert status == "completed"
    assert isinstance(text_body, str) and text_body.strip() == "# Draft text"
    assert isinstance(analysis_json, dict) and analysis_json.get("schema") == "criteria.v2"
    assert feedback_md == "**Das ist dir gut gelungen:** A.\n\n**Das kannst du besser:** B."


@pytest.mark.anyio
async def test_worker_schedules_retry_when_image_bytes_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    _require_db_or_skip()
    fixture = await _prepare_learning_fixture()
    test_run_id = current_test_run_id()
    dsn = _dsn()
    worker_dsn = os.getenv("SERVICE_ROLE_DSN") or dsn

    # Clean queue
    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cleanup_learning_jobs_for_run(conn, test_run_id)
            cur.execute("select set_config('app.current_sub', %s, false)", (fixture.student_sub,))
            cur.execute(
                """
                delete from public.learning_submissions
                 where student_sub = %s
                   and idempotency_key in ('e2e-local-image')
                """,
                (fixture.student_sub,),
            )
        conn.commit()

    # Avoid local filesystem and remote Supabase fetch in this test.
    monkeypatch.delenv("STORAGE_VERIFY_ROOT", raising=False)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_PUBLIC_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

    # Create a pending image submission + job, but schedule it slightly in the future.
    future_tick = datetime.now(tz=timezone.utc) + timedelta(minutes=2)
    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, false)", (fixture.student_sub,))
            cur.execute(
                """
                insert into public.learning_submissions (
                    course_id,
                    task_id,
                    section_id,
                    student_sub,
                    kind,
                    storage_key,
                    mime_type,
                    size_bytes,
                    sha256,
                    attempt_nr,
                    analysis_status,
                    idempotency_key
                )
                values (
                    %s::uuid,
                    %s::uuid,
                    %s::uuid,
                    %s,
                    'image',
                    %s,
                    %s,
                    %s,
                    %s,
                    1,
                    'pending',
                    %s
                )
                returning id::text
                """,
                (
                    fixture.course_id,
                    fixture.task["id"],
                    fixture.section_id,
                    fixture.student_sub,
                    "storage://bucket/key.jpg",
                    "image/jpeg",
                    1024,
                    "0" * 64,
                    "e2e-local-image",
                ),
            )
            submission_id = str(cur.fetchone()[0])
            job_payload = {
                "_gustav_source": "pytest",
                "_gustav_test_run_id": test_run_id,
                "submission_id": submission_id,
                "course_id": fixture.course_id,
                "task_id": fixture.task["id"],
                "task_kind": str((fixture.task or {}).get("kind") or "native"),
                "student_sub": fixture.student_sub,
                "kind": "image",
                "attempt_nr": 1,
                "criteria": list((fixture.task or {}).get("criteria") or []),
                "instruction_md": (fixture.task or {}).get("instruction_md"),
            }
            cur.execute(
                """
                insert into public.learning_submission_jobs (
                    submission_id,
                    payload,
                    visible_at
                )
                values (%s::uuid, %s::jsonb, %s)
                """,
                (submission_id, json.dumps(job_payload), future_tick),
            )
        conn.commit()

    import importlib

    local_vision = importlib.import_module("backend.learning.adapters.local_vision").build()  # type: ignore[attr-defined]
    local_feedback = importlib.import_module("backend.learning.adapters.local_feedback").build()  # type: ignore[attr-defined]

    from backend.learning.workers.process_learning_submission_jobs import run_once  # type: ignore

    processed = run_once(
        dsn=worker_dsn,
        vision_adapter=local_vision,
        feedback_adapter=local_feedback,
        now=future_tick,
        test_run_id=test_run_id,
    )
    assert processed is True

    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute(
                """
                select analysis_status, text_body, analysis_json
                  from public.learning_submissions
                 where id = %s::uuid
                """,
                (submission_id,),
            )
            status, text_body, analysis_json = cur.fetchone()

    assert status == "pending"
    assert text_body is None
    assert analysis_json is None
