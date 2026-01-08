"""
Worker integration test: Visual tasks use the Visual (image) DSPy pipeline.

Intent:
    When `Task.kind="visual"` a submission is upload-only and should be
    evaluated from the visual input (image/PDF), not from OCR text.

Contract encoded by this test:
    - The worker must NOT call the Vision adapter for visual tasks.
    - The worker must call `feedback_adapter.analyze_visual(...)` and persist
      its `criteria.v2` analysis_json + feedback_md on the submission row.

Notes:
    We keep this test deterministic by using stub adapters:
    - Vision adapter explodes if called.
    - Visual feedback adapter returns a fixed `criteria.v2` payload.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import uuid

import pytest

pytest.importorskip("psycopg")
import psycopg  # type: ignore  # noqa: E402

from backend.learning.repo_db import DBLearningRepo  # noqa: E402
from backend.learning.usecases.submissions import CreateSubmissionInput, CreateSubmissionUseCase  # noqa: E402
from backend.learning.workers.process_learning_submission_jobs import (  # noqa: E402
    FeedbackResult,
    VisionResult,
    run_once,
)
from backend.tests.test_learning_worker_jobs import _dsn  # type: ignore  # noqa: E402
from backend.tests.test_learning_visual_upload_only_api import _prepare_visual_task_fixture  # type: ignore  # noqa: E402
from backend.tests.utils.db import require_db_or_skip as _require_db_or_skip  # noqa: E402


try:
    _require_db_or_skip()
except pytest.skip.Exception as exc:  # pragma: no cover - module level skip
    pytest.skip(str(exc), allow_module_level=True)


class _ExplodingVisionAdapter:
    def __init__(self) -> None:
        self.called = False

    def extract(self, *, submission: dict, job_payload: dict) -> VisionResult:  # pragma: no cover
        self.called = True
        raise AssertionError("Vision must not be called for visual tasks")


class _StubVisualFeedbackAdapter:
    def __init__(self) -> None:
        self.called = False
        self.last_payload: dict | None = None

    def analyze_visual(  # type: ignore[no-untyped-def]
        self,
        *,
        submission: dict,
        job_payload: dict,
        criteria,
        instruction_md=None,
        hints_md=None,
    ) -> FeedbackResult:
        self.called = True
        self.last_payload = {
            "submission_kind": submission.get("kind"),
            "task_kind": (job_payload or {}).get("task_kind"),
            "criteria": list(criteria or []),
            "instruction_md": instruction_md,
            "hints_md": hints_md,
        }
        return FeedbackResult(
            feedback_md="VLM Feedback",
            analysis_json={"schema": "criteria.v2", "score": 4, "criteria_results": []},
            parse_status="parsed_structured",
        )


@pytest.mark.anyio
async def test_worker_routes_visual_tasks_to_visual_feedback(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fx = await _prepare_visual_task_fixture()
    dsn = _dsn()
    monkeypatch.setenv("SERVICE_ROLE_DSN", dsn)

    # Provide a local storage root with a real file so future implementations
    # can load bytes without changing the test.
    monkeypatch.setenv("STORAGE_VERIFY_ROOT", str(tmp_path))

    # Clean queue for determinism.
    with psycopg.connect(dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute("delete from public.learning_submission_jobs")
        conn.commit()

    # Prepare a dummy PNG under the storage key.
    storage_key = f"submissions/{fx['course_id']}/{fx['task_id']}/{fx['student'].sub}/visual.png"  # type: ignore[attr-defined]
    payload_bytes = b"\x89PNG\r\n\x1a\n" + b"x" * 64
    target = tmp_path / storage_key
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload_bytes)
    sha = hashlib.sha256(payload_bytes).hexdigest()

    # Enqueue a Visual submission (kind=image). The fixture uses max_attempts=2.
    repo = DBLearningRepo(dsn=dsn)
    usecase = CreateSubmissionUseCase(repo)
    submission = usecase.execute(
        CreateSubmissionInput(
            course_id=fx["course_id"],
            task_id=fx["task_id"],
            student_sub=fx["student"].sub,  # type: ignore[attr-defined]
            kind="image",
            text_body=None,
            storage_key=storage_key,
            mime_type="image/png",
            size_bytes=len(payload_bytes),
            sha256=sha,
            score_raw=None,
            score_max=None,
            idempotency_key=f"visual-worker-{uuid.uuid4().hex}",
        )
    )

    vision = _ExplodingVisionAdapter()
    feedback = _StubVisualFeedbackAdapter()

    processed = run_once(
        dsn=os.getenv("SERVICE_ROLE_DSN") or dsn,
        vision_adapter=vision,
        feedback_adapter=feedback,
        now=datetime.now(tz=timezone.utc),
    )

    assert processed is True
    assert vision.called is False
    assert feedback.called is True
    assert (feedback.last_payload or {}).get("task_kind") == "visual"

    # Verify persistence on the submission row
    with psycopg.connect(dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, false)", (fx["student"].sub,))  # type: ignore[attr-defined]
            cur.execute(
                "select analysis_status, feedback_md, analysis_json from public.learning_submissions where id = %s::uuid",
                (submission["id"],),
            )
            row = cur.fetchone()
    assert row is not None
    status, feedback_md, analysis_json = row
    assert status == "completed"
    assert feedback_md == "VLM Feedback"
    assert isinstance(analysis_json, dict)
    assert analysis_json.get("schema") == "criteria.v2"

