"""
Regression test: the learning worker must not hold an open DB transaction while calling external adapters.

Why:
    The worker runs LLM/VLM calls that may hang or take minutes. If the worker keeps
    a DB transaction open during that time (state "idle in transaction"), it can
    stall the queue and cause operational issues (see ticket 2026-01-15).

Contract:
    While the worker is blocked inside an adapter call:
      - The leased job must be visible as `status='leased'` to other connections.
      - The worker session must NOT be `idle in transaction`.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timedelta, timezone

import pytest

pytest.importorskip("psycopg")

import psycopg  # type: ignore  # noqa: E402

from backend.tests.test_learning_api_contract import _prepare_learning_fixture  # type: ignore  # noqa: E402
from backend.tests.utils.db import require_db_or_skip as _require_db_or_skip  # noqa: E402
from backend.tests.utils.db_isolation import cleanup_learning_jobs_for_run, current_test_run_id  # noqa: E402


def _dsn_with_application_name(dsn: str, application_name: str) -> str:
    if not dsn:
        return dsn
    if "application_name=" in dsn:
        return dsn
    sep = "&" if "?" in dsn else "?"
    return f"{dsn}{sep}application_name={application_name}"


def _row_value(row, key: str, idx: int):  # type: ignore[no-untyped-def]
    """Support both dict_row and tuple rows in tests."""
    if isinstance(row, dict):
        return row.get(key)
    return row[idx]


@pytest.mark.anyio
async def test_worker_commits_before_entering_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    _require_db_or_skip()
    fixture = await _prepare_learning_fixture()

    base_dsn = os.getenv("SERVICE_ROLE_DSN") or os.getenv("DATABASE_URL") or ""
    if not base_dsn:
        pytest.skip("No SERVICE_ROLE_DSN/DATABASE_URL available for worker regression test.")
    worker_dsn = _dsn_with_application_name(base_dsn, "pytest-learning-worker-stall")

    from backend.learning.workers.process_learning_submission_jobs import (  # type: ignore
        FeedbackResult,
        VisionResult,
        run_once,
    )

    monkeypatch.setenv("WORKER_CONCURRENCY", "1")
    test_run_id = current_test_run_id()

    # Clean queue
    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cleanup_learning_jobs_for_run(conn, test_run_id)
            cur.execute("select set_config('app.current_sub', %s, false)", (fixture.student_sub,))
        conn.commit()

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
                    "storage://bucket/key.png",
                    "image/png",
                    1024,
                    "0" * 64,
                    "stall-regression",
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

    entered = threading.Event()
    release = threading.Event()

    class _VisionAdapter:
        def extract(self, *, submission: dict, job_payload: dict) -> VisionResult:  # type: ignore[override]
            return VisionResult(text_md="OCR text", raw_metadata={"adapter": "pass-through"})

    class _FeedbackAdapter:
        def analyze_visual(  # type: ignore[override]
            self,
            *,
            submission: dict,
            job_payload: dict,
            criteria,
            instruction_md=None,
            teacher_context_md=None,
        ) -> FeedbackResult:
            entered.set()
            assert release.wait(timeout=10), "test timeout: visual feedback adapter never released"
            return FeedbackResult(
                feedback_md="**Das ist dir gut gelungen:** A.\n\n**Das kannst du besser:** B.",
                analysis_json={"schema": "criteria.v2", "score": 0, "criteria_results": []},
                parse_status="parsed_structured",
            )

        def analyze(self, *, text_md: str, criteria, instruction_md=None, teacher_context_md=None) -> FeedbackResult:  # type: ignore[override]
            return FeedbackResult(
                feedback_md="**Das ist dir gut gelungen:** A.\n\n**Das kannst du besser:** B.",
                analysis_json={"schema": "criteria.v2", "score": 0, "criteria_results": []},
                parse_status="parsed_structured",
            )

    worker_exc: list[BaseException] = []

    def _run_worker() -> None:
        try:
            run_once(
                dsn=worker_dsn,
                vision_adapter=_VisionAdapter(),
                feedback_adapter=_FeedbackAdapter(),
                now=future_tick,
                test_run_id=test_run_id,
            )
        except BaseException as exc:  # pragma: no cover - unexpected
            worker_exc.append(exc)

    t = threading.Thread(target=_run_worker, daemon=True)
    t.start()

    assert entered.wait(timeout=10), "test timeout: worker did not enter visual feedback adapter"

    # 1) Job row must already be leased and committed (visible to other sessions).
    with psycopg.connect(base_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute(
                "select status from public.learning_submission_jobs where submission_id = %s::uuid",
                (submission_id,),
            )
            row = cur.fetchone()
    assert row, "expected queued job row to exist while worker is blocked"
    assert _row_value(row, "status", 0) == "leased"

    # 2) The worker session must NOT be "idle in transaction" while blocked.
    with psycopg.connect(base_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute(
                """
                select state
                  from pg_stat_activity
                 where application_name = %s
                 order by backend_start desc
                 limit 1
                """,
                ("pytest-learning-worker-stall",),
            )
            state_row = cur.fetchone()
    assert state_row and isinstance(state_row[0], str)
    assert state_row[0] != "idle in transaction"

    # Release and ensure the worker thread finishes.
    release.set()
    t.join(timeout=10)
    assert not t.is_alive(), "worker thread did not finish"
    assert not worker_exc, f"worker raised: {worker_exc[0]!r}"
