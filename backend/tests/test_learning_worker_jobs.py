"""
Worker integration tests for the learning submission pipeline.

Why:
    Ensure the worker service processes queued submissions end-to-end:
    leasing a job, invoking Vision/Feedback adapters, and persisting
    the completed status back into Postgres while removing the job.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import logging
import os
from pathlib import Path
import uuid
from typing import Sequence

import pytest

from backend.learning.repo_db import DBLearningRepo
from backend.learning.usecases.submissions import CreateSubmissionInput, CreateSubmissionUseCase
from backend.tests.utils.db import require_db_or_skip as _require_db_or_skip

pytest.importorskip("psycopg")
pytestmark = pytest.mark.db_write

try:
    _require_db_or_skip()
except pytest.skip.Exception as exc:  # pragma: no cover - module level skip
    pytest.skip(str(exc), allow_module_level=True)

import psycopg  # type: ignore  # noqa: E402

from backend.tests.test_learning_api_contract import _prepare_learning_fixture  # type: ignore
from backend.tests.utils.db_isolation import cleanup_learning_jobs_for_run, current_test_run_id
from backend.learning.workers import process_learning_submission_jobs as worker_module  # noqa: E402  # type: ignore
from backend.learning.workers.process_learning_submission_jobs import (  # noqa: E402  # type: ignore
    FeedbackResult,
    TokenUsageEvent,
    VisionResult,
    run_once,
)
from backend.learning.workers import telemetry  # noqa: E402  # type: ignore


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


@dataclass
class _StubVisionAdapter:
    text_md: str

    def extract(self, *, submission: dict, job_payload: dict) -> VisionResult:
        """Return deterministic Markdown for the worker to persist."""
        return VisionResult(text_md=self.text_md, raw_metadata={"source": "stub"})


@dataclass
class _StubFeedbackAdapter:
    feedback_md: str
    base_score: int = 4

    def analyze(self, *, text_md: str, criteria: Sequence[str]) -> FeedbackResult:
        """Return deterministic feedback+analysis shaped like criteria.v2."""
        results = []
        for index, criterion in enumerate(criteria):
            results.append(
                {
                    "criterion": criterion,
                    "score": min(10, self.base_score + index),
                    "max_score": 10,
                    "explanation_md": f"Stub feedback for {criterion}",
                }
            )
        return FeedbackResult(
            feedback_md=self.feedback_md,
            analysis_json={
                "schema": "criteria.v2",
                "score": self.base_score,
                "criteria_results": results,
            },
        )


class _TransientVisionAdapter:
    """Raise a transient vision error to exercise the retry path."""

    def __init__(self, message: str = "temporary vision glitch"):
        self.calls = 0
        self.message = message

    def extract(self, *, submission: dict, job_payload: dict) -> VisionResult:
        self.calls += 1
        raise worker_module.VisionTransientError(self.message)  # type: ignore[attr-defined]


class _PermanentVisionAdapter:
    """Always raise a transient error to exhaust retries quickly."""

    def __init__(self, message: str = "permanent vision failure"):
        self.calls = 0
        self.message = message

    def extract(self, *, submission: dict, job_payload: dict) -> VisionResult:
        self.calls += 1
        raise worker_module.VisionTransientError(self.message)  # type: ignore[attr-defined]


class _TransientFeedbackAdapter:
    """Raise a transient feedback error to exercise feedback retry bookkeeping."""

    def __init__(self, message: str = "temporary feedback issue"):
        self.calls = 0
        self.message = message

    def analyze(self, *, text_md: str, criteria: Sequence[str]) -> FeedbackResult:
        self.calls += 1
        raise worker_module.FeedbackTransientError(self.message)  # type: ignore[attr-defined]


class _RecordingFeedbackAdapter:
    """Return valid criteria feedback and retain the Evidence text for assertions."""

    def __init__(self) -> None:
        self.calls = 0
        self.seen_text_md = ""

    def analyze(self, *, text_md: str, criteria: Sequence[str]) -> FeedbackResult:
        self.calls += 1
        self.seen_text_md = text_md
        return FeedbackResult(
            feedback_md="Automatische Rückmeldung auf Basis der verfügbaren Abgabe.",
            analysis_json={
                "schema": "criteria.v2",
                "criteria_results": [
                    {
                        "criterion": str(criteria[0] if criteria else "Abgabe"),
                        "explanation_md": "Die Abgabe wurde verarbeitet.",
                    }
                ],
            },
        )


class _PermanentFeedbackAdapter:
    """Raise a permanent feedback error to ensure the worker records failures."""

    def __init__(self, message: str = "permanent feedback failure"):
        self.calls = 0
        self.message = message

    def analyze(self, *, text_md: str, criteria: Sequence[str]) -> FeedbackResult:
        self.calls += 1
        raise worker_module.FeedbackPermanentError(self.message)  # type: ignore[attr-defined]


class _ImageTooComplexFeedbackAdapter:
    """Raise the internal visual admission code used for complex screenshot PNGs."""

    def __init__(self) -> None:
        self.calls = 0
        self.visual_calls = 0

    def analyze(self, *, text_md: str, criteria: Sequence[str]) -> FeedbackResult:
        self.calls += 1
        raise worker_module.FeedbackPermanentError("image_too_complex_for_provider")  # type: ignore[attr-defined]

    def analyze_visual(self, *, submission: dict, job_payload: dict, criteria: Sequence[str], **_: object) -> FeedbackResult:
        self.visual_calls += 1
        raise worker_module.FeedbackPermanentError("image_too_complex_for_provider")  # type: ignore[attr-defined]


class _InvalidAnalysisFeedbackAdapter:
    """Raise a deterministic invalid-analysis error that must not be retried."""

    def __init__(self, message: str = "feedback_invalid_analysis") -> None:
        self.calls = 0
        self.message = message

    def analyze(self, *, text_md: str, criteria: Sequence[str]) -> FeedbackResult:
        self.calls += 1
        raise worker_module.FeedbackInvalidAnalysisError(self.message)  # type: ignore[attr-defined]


class _CountingVisionAdapter:
    """Vision adapter that records invocations for OCR-reuse tests."""

    def __init__(self) -> None:
        self.calls = 0

    def extract(self, *, submission: dict, job_payload: dict) -> VisionResult:
        self.calls += 1
        return VisionResult(
            text_md="## Counting Vision\n\nShould be bypassed when cache is present.",
            raw_metadata={"source": "counting_adapter"},
        )


class _UsageFeedbackAdapter:
    """Return deterministic feedback with one technical token usage event."""

    def __init__(self, event_key: str) -> None:
        self.event_key = event_key

    def analyze(self, *, text_md: str, criteria: Sequence[str]) -> FeedbackResult:
        return FeedbackResult(
            feedback_md="**Das ist dir gut gelungen:** A.\n\n**Das kannst du besser:** B.",
            analysis_json={"schema": "criteria.v2", "score": 0, "criteria_results": []},
            usage_events=[
                TokenUsageEvent(
                    event_key=self.event_key,
                    model="openai/mistral-small-latest",
                    stage="feedback",
                    modality="text",
                    call_kind="primary",
                    usage_known=True,
                    input_tokens=11,
                    output_tokens=7,
                    total_tokens=18,
                )
            ],
        )


async def _prepare_submission_with_job(*, idempotency_key: str) -> tuple[dict, str, str, str]:
    """Create a pending submission and return (fixture, worker_dsn, job_id, submission_id)."""
    test_run_id = current_test_run_id()
    fixture = await _prepare_learning_fixture()
    dsn = _dsn()
    worker_dsn = os.getenv("SERVICE_ROLE_DSN") or dsn

    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        cleanup_learning_jobs_for_run(conn, test_run_id)
        conn.commit()

    # Ensure membership exists (some suite orders may skip API add_member on errors)
    try:
        with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into public.course_memberships (course_id, student_id, role)
                    select %s::uuid, %s, 'student'
                    where not exists (
                        select 1 from public.course_memberships
                         where course_id = %s::uuid and student_id = %s
                    )
                    """,
                    (fixture.course_id, fixture.student_sub, fixture.course_id, fixture.student_sub),
                )
            conn.commit()
    except Exception:
        # Best-effort hardening; tests relying on API path still validate main behaviour
        pass

    repo = DBLearningRepo(dsn=dsn)
    usecase = CreateSubmissionUseCase(repo)
    submission = usecase.execute(
        CreateSubmissionInput(
            course_id=fixture.course_id,
            task_id=fixture.task["id"],
            student_sub=fixture.student_sub,
            intent="submit",
            kind="text",
            text_body="Pending answer for retry path",
            storage_key=None,
            mime_type=None,
            size_bytes=None,
            sha256=None,
            score_raw=None,
            score_max=None,
            idempotency_key=idempotency_key,
        )
    )
    submission_id = submission["id"]

    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute(
                """
                select id::text
                  from public.learning_submission_jobs
                 where submission_id = %s::uuid
                 order by created_at desc
                """,
                (submission_id,),
            )
            row = cur.fetchone()
            if not row:
                # Fallback: insert a queued job deterministically for this submission.
                cur.execute(
                    """
                    insert into public.learning_submission_jobs (submission_id, payload, visible_at, status, retry_count)
                    values (%s::uuid, %s::jsonb, now(), 'queued', 0)
                    returning id::text
                    """,
                    (
                        submission_id,
                        {
                            "student_sub": fixture.student_sub,
                            "criteria": [],
                            "_gustav_source": "pytest",
                            "_gustav_test_run_id": test_run_id,
                        },
                    ),
                )
                job_id = cur.fetchone()[0]
            else:
                job_id = row[0]
    return fixture, worker_dsn, job_id, submission_id


def _set_job_visibility(worker_dsn: str, job_id: str, *, visible_at: datetime) -> None:
    """Pin a job's visibility for deterministic leasing, clearing previous processing state.

    Why:
        Worker tests should not depend on external worker processes or a previous
        retry attempt. We reset `retry_count` and `error_code` so the next
        `run_once()` call always exercises the "first retry" path deterministically.
    """
    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute(
                """
                update public.learning_submission_jobs
                   set visible_at = %s,
                       status = 'queued',
                       retry_count = 0,
                       error_code = null,
                       lease_key = null,
                       leased_until = null,
                       updated_at = now()
                 where id = %s::uuid
                """,
                (visible_at, job_id),
            )
        conn.commit()


def _force_submission_to_file(worker_dsn: str, submission_id: str) -> None:
    """Switch the stored submission to a non-text kind so Vision adapters run."""
    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute(
                """
                update public.learning_submissions
                   set kind = 'image',
                       mime_type = 'image/png',
                       text_body = null,
                       storage_key = coalesce(storage_key, 'learning/test.png'),
                       size_bytes = coalesce(size_bytes, 1),
                       sha256 = coalesce(sha256, repeat('0', 64))
                 where id = %s::uuid
                """,
                (submission_id,),
            )
        conn.commit()


def _hex_record(*, addr: int, record_type: int, data: bytes) -> str:
    ll = len(data)
    total = ll + ((addr >> 8) & 0xFF) + (addr & 0xFF) + (record_type & 0xFF) + sum(data)
    checksum = (-total) & 0xFF
    return f":{ll:02X}{addr:04X}{record_type:02X}{data.hex().upper()}{checksum:02X}"


def _make_hex_without_magic() -> bytes:
    blob = b"\x00" * 64
    lines: list[str] = []
    for i in range(0, len(blob), 16):
        lines.append(_hex_record(addr=i, record_type=0x00, data=blob[i : i + 16]))
    lines.append(_hex_record(addr=0, record_type=0x01, data=b""))
    return ("\n".join(lines) + "\n").encode("ascii")


def _counter_value(name: str, **labels: str) -> int:
    snapshot = telemetry.counter_snapshot(name)
    key = tuple(sorted(labels.items()))
    return snapshot.get(key, 0)


def _gauge_value(name: str, **labels: str) -> float:
    snapshot = telemetry.gauge_snapshot(name)
    key = tuple(sorted(labels.items()))
    return snapshot.get(key, 0.0)


@pytest.mark.anyio
async def test_worker_processes_pending_submission_to_completed():
    """Worker should mark a queued submission as completed and clear the job."""

    _require_db_or_skip()
    fixture = await _prepare_learning_fixture()
    dsn = _dsn()
    worker_dsn = os.getenv("SERVICE_ROLE_DSN") or dsn

    # Ensure a clean queue so the worker leases the job created in this test.
    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        cleanup_learning_jobs_for_run(conn)
        conn.commit()

    repo = DBLearningRepo(dsn=dsn)
    usecase = CreateSubmissionUseCase(repo)
    submission = usecase.execute(
        CreateSubmissionInput(
            course_id=fixture.course_id,
            task_id=fixture.task["id"],
            student_sub=fixture.student_sub,
            intent="submit",
            kind="text",
            text_body="Schülerantwort pending",
            storage_key=None,
            mime_type=None,
            size_bytes=None,
            sha256=None,
            score_raw=None,
            score_max=None,
            idempotency_key="worker-happy-path",
        )
    )
    submission_id = submission["id"]
    # Ensure the submission row exists in the learning repo.
    history = repo.list_submissions(
        student_sub=fixture.student_sub,
        course_id=fixture.course_id,
        task_id=fixture.task["id"],
        limit=5,
        offset=0,
    )
    assert any(entry["id"] == submission_id for entry in history)

    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute(
                """
                select id::text
                  from public.learning_submission_jobs
                 where submission_id = %s::uuid
                 order by created_at desc
                """,
                (submission_id,),
            )
            job_row = cur.fetchone()
            if not job_row:
                pytest.fail("Submission did not enqueue a learning_submission_job")
            job_id = job_row[0]

    _force_submission_to_file(worker_dsn, submission_id)

    processed = run_once(
        dsn=worker_dsn,
        vision_adapter=_StubVisionAdapter(text_md="## Vision Extract\n\nStub content."),
        feedback_adapter=_StubFeedbackAdapter(feedback_md="### Feedback\n\n- Gut gemacht."),
        now=datetime.now(tz=timezone.utc),
        test_run_id=current_test_run_id(),
    )

    assert processed is True

    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            try:
                cur.execute(
                    """
                    select analysis_status,
                           text_body,
                           analysis_json,
                           feedback_md,
                           vision_attempts,
                           vision_last_error
                      from public.learning_submissions
                     where id = %s::uuid
                    """,
                    (submission_id,),
                )
            except psycopg.errors.UndefinedColumn:  # type: ignore[attr-defined]
                cur.execute(
                    """
                    select analysis_status,
                           text_body,
                           analysis_json,
                           feedback_md,
                           ocr_attempts,
                           ocr_last_error
                      from public.learning_submissions
                     where id = %s::uuid
                    """,
                    (submission_id,),
                )
            row = cur.fetchone()
            assert row is not None
            analysis_status, text_body, analysis_json, feedback_md, attempts, last_error = row

            cur.execute(
                "select count(*) from public.learning_submission_jobs where id = %s::uuid", (job_id,)
            )
            remaining_jobs = int(cur.fetchone()[0])

    assert analysis_status == "completed"
    assert text_body == "## Vision Extract\n\nStub content."
    assert attempts == 1
    assert last_error is None
    assert remaining_jobs == 0

    assert isinstance(analysis_json, dict)
    assert analysis_json["schema"] == "criteria.v2"
    assert analysis_json["score"] == _StubFeedbackAdapter.base_score


@pytest.mark.anyio
async def test_worker_calliope_hex_missing_source_uses_fallback_evidence_and_completes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    """Calliope HEX soft extraction failures must still reach feedback."""

    _require_db_or_skip()
    fixture, worker_dsn, job_id, submission_id = await _prepare_submission_with_job(
        idempotency_key=f"worker-calliope-soft-{uuid.uuid4().hex}"
    )
    hex_bytes = _make_hex_without_magic()
    digest = sha256(hex_bytes).hexdigest()

    from backend.storage.config import get_submissions_bucket
    from backend.storage.mime_types import MAKECODE_HEX_MIME

    bucket = get_submissions_bucket()
    storage_root = tmp_path / "storage"
    monkeypatch.setenv("STORAGE_VERIFY_ROOT", str(storage_root))
    storage_key = f"{bucket}/{fixture.course_id}/{fixture.task['id']}/{fixture.student_sub}/missing-source.hex"
    file_path = storage_root / storage_key
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(hex_bytes)

    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (fixture.student_sub,))
            cur.execute("update public.unit_tasks set kind = 'calliope' where id = %s::uuid", (fixture.task["id"],))
            cur.execute(
                """
                update public.learning_submissions
                   set kind = 'file',
                       mime_type = %s,
                       text_body = null,
                       storage_key = %s,
                       size_bytes = %s,
                       sha256 = %s
                 where id = %s::uuid
                """,
                (MAKECODE_HEX_MIME, storage_key, len(hex_bytes), digest, submission_id),
            )
            cur.execute(
                """
                update public.learning_submission_jobs
                   set payload = payload || %s::jsonb,
                       status = 'queued',
                       visible_at = now(),
                       lease_key = null,
                       leased_until = null
                 where id = %s::uuid
                """,
                (
                    json.dumps(
                        {
                            "task_kind": "calliope",
                            "kind": "file",
                            "mime_type": MAKECODE_HEX_MIME,
                            "storage_key": storage_key,
                            "size_bytes": len(hex_bytes),
                            "sha256": digest,
                            "criteria": ["Abgabe"],
                        }
                    ),
                    job_id,
                ),
            )
        conn.commit()

    from backend.learning.adapters import local_vision

    feedback = _RecordingFeedbackAdapter()
    processed = run_once(
        dsn=worker_dsn,
        vision_adapter=local_vision.build(),
        feedback_adapter=feedback,
        now=datetime.now(tz=timezone.utc),
        test_run_id=current_test_run_id(),
    )

    assert processed is True
    assert feedback.calls == 1
    assert "makecode.evidence.v1" in feedback.seen_text_md
    assert "extraction_status: source_unavailable" in feedback.seen_text_md
    assert "extraction_error: missing_makecode_source" in feedback.seen_text_md
    assert "### file:" not in feedback.seen_text_md

    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute(
                """
                select analysis_status, text_body, feedback_md, analysis_json, error_code
                  from public.learning_submissions
                 where id = %s::uuid
                """,
                (submission_id,),
            )
            row = cur.fetchone()
            cur.execute("select count(*) from public.learning_submission_jobs where id = %s::uuid", (job_id,))
            remaining_jobs = int(cur.fetchone()[0])

    assert row is not None
    status, text_body, feedback_md, analysis_json, error_code = row
    assert status == "completed"
    assert "extraction_status: source_unavailable" in str(text_body)
    assert feedback_md == "Automatische Rückmeldung auf Basis der verfügbaren Abgabe."
    assert isinstance(analysis_json, dict)
    assert analysis_json.get("schema") == "criteria.v2"
    assert error_code is None
    assert remaining_jobs == 0


@pytest.mark.anyio
async def test_worker_filius_fls_extracts_evidence_and_completes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    """Filius FLS submissions should run through deterministic evidence extraction."""

    _require_db_or_skip()
    fixture, worker_dsn, job_id, submission_id = await _prepare_submission_with_job(
        idempotency_key=f"worker-filius-fls-{uuid.uuid4().hex}"
    )
    fls_bytes = Path("backend/tests/fixtures/filius/inf-schule-clientserver/filius_ClientServer.fls").read_bytes()
    digest = sha256(fls_bytes).hexdigest()

    from backend.storage.config import get_submissions_bucket
    from backend.storage.mime_types import FILIUS_FLS_MIME

    bucket = get_submissions_bucket()
    storage_root = tmp_path / "storage"
    monkeypatch.setenv("STORAGE_VERIFY_ROOT", str(storage_root))
    storage_key = f"{bucket}/{fixture.course_id}/{fixture.task['id']}/{fixture.student_sub}/network.fls"
    file_path = storage_root / storage_key
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(fls_bytes)

    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (fixture.student_sub,))
            cur.execute("update public.unit_tasks set kind = 'filius' where id = %s::uuid", (fixture.task["id"],))
            cur.execute(
                """
                update public.learning_submissions
                   set kind = 'file',
                       mime_type = %s,
                       text_body = null,
                       storage_key = %s,
                       size_bytes = %s,
                       sha256 = %s
                 where id = %s::uuid
                """,
                (FILIUS_FLS_MIME, storage_key, len(fls_bytes), digest, submission_id),
            )
            cur.execute(
                """
                update public.learning_submission_jobs
                   set payload = payload || %s::jsonb,
                       status = 'queued',
                       visible_at = now(),
                       lease_key = null,
                       leased_until = null
                 where id = %s::uuid
                """,
                (
                    json.dumps(
                        {
                            "task_kind": "filius",
                            "kind": "file",
                            "mime_type": FILIUS_FLS_MIME,
                            "storage_key": storage_key,
                            "size_bytes": len(fls_bytes),
                            "sha256": digest,
                            "criteria": ["Netzwerkstruktur"],
                        }
                    ),
                    job_id,
                ),
            )
        conn.commit()

    from backend.learning.adapters import local_vision

    feedback = _RecordingFeedbackAdapter()
    processed = run_once(
        dsn=worker_dsn,
        vision_adapter=local_vision.build(),
        feedback_adapter=feedback,
        now=datetime.now(tz=timezone.utc),
        test_run_id=current_test_run_id(),
    )

    assert processed is True
    assert feedback.calls == 1
    assert "filius.evidence.v1" in feedback.seen_text_md
    assert "## Nodes" in feedback.seen_text_md
    assert "## Links" in feedback.seen_text_md

    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute(
                """
                select analysis_status, text_body, feedback_md, analysis_json, error_code
                  from public.learning_submissions
                 where id = %s::uuid
                """,
                (submission_id,),
            )
            row = cur.fetchone()
            cur.execute("select count(*) from public.learning_submission_jobs where id = %s::uuid", (job_id,))
            remaining_jobs = int(cur.fetchone()[0])

    assert row is not None
    status, text_body, feedback_md, analysis_json, error_code = row
    assert status == "completed"
    assert "filius.evidence.v1" in str(text_body)
    assert "## Nodes" in str(text_body)
    assert feedback_md == "Automatische Rückmeldung auf Basis der verfügbaren Abgabe."
    assert isinstance(analysis_json, dict)
    assert analysis_json.get("schema") == "criteria.v2"
    assert error_code is None
    assert remaining_jobs == 0


@pytest.mark.anyio
async def test_worker_persists_ai_usage_events_from_feedback_result():
    """Worker should persist captured token events before completing a submission."""

    _require_db_or_skip()
    fixture, worker_dsn, _job_id, submission_id = await _prepare_submission_with_job(
        idempotency_key=f"worker-ai-usage-{uuid.uuid4().hex}"
    )
    tick = datetime.now(tz=timezone.utc)
    event_key = str(uuid.uuid4())

    processed = run_once(
        dsn=worker_dsn,
        vision_adapter=_StubVisionAdapter(text_md="## Student answer\n\nContent."),
        feedback_adapter=_UsageFeedbackAdapter(event_key=event_key),
        now=tick,
        test_run_id=current_test_run_id(),
    )

    assert processed is True

    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (fixture.student_sub,))
            cur.execute(
                """
                select model,
                       stage,
                       modality,
                       call_kind,
                       usage_known,
                       input_tokens,
                       output_tokens,
                       total_tokens,
                       student_sub,
                       course_id::text,
                       task_id::text
                  from public.ai_usage_events
                 where event_key = %s::uuid
                """,
                (event_key,),
            )
            row = cur.fetchone()

    assert row == (
        "openai/mistral-small-latest",
        "feedback",
        "text",
        "primary",
        True,
        11,
        7,
        18,
        fixture.student_sub,
        fixture.course_id,
        fixture.task["id"],
    )


@pytest.mark.anyio
async def test_worker_retries_vision_transient_error(monkeypatch):
    """Transient vision errors should requeue the job with backoff and keep submission pending."""

    _require_db_or_skip()
    _, worker_dsn, job_id, submission_id = await _prepare_submission_with_job(
        idempotency_key="worker-retry-path"
    )

    _force_submission_to_file(worker_dsn, submission_id)

    # Deterministic configuration for retries.
    monkeypatch.setenv("WORKER_BACKOFF_SECONDS", "2")
    worker_module.MAX_RETRIES = 3  # type: ignore[attr-defined]
    tick = datetime.now(tz=timezone.utc) + timedelta(hours=1)
    _set_job_visibility(worker_dsn, job_id, visible_at=tick)

    processed = run_once(
        dsn=worker_dsn,
        vision_adapter=_TransientVisionAdapter(),
        feedback_adapter=_StubFeedbackAdapter(feedback_md="unused"),
        now=tick,
        test_run_id=current_test_run_id(),
    )

    assert processed is True

    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute(
                """
                select status,
                       retry_count,
                       visible_at,
                       error_code
                  from public.learning_submission_jobs
                 where id = %s::uuid
                """,
                (job_id,),
            )
            status, retry_count, visible_at, error_code = cur.fetchone()

            cur.execute(
                """
                select analysis_status,
                       error_code,
                       vision_attempts,
                       vision_last_error,
                       vision_last_attempt_at
                  from public.learning_submissions
                 where id = %s::uuid
                """,
                (submission_id,),
            )
            (
                submission_status,
                submission_error,
                vision_attempts,
                vision_last_error,
                last_attempt_at,
            ) = cur.fetchone()

    assert status == "queued"
    assert retry_count == 1
    assert error_code is None
    assert visible_at.tzinfo is not None
    assert visible_at >= tick + timedelta(seconds=2)

    assert submission_status == "pending"
    assert submission_error == "vision_retrying"
    assert vision_attempts == 1
    assert vision_last_error is not None
    assert "temporary vision glitch" in vision_last_error
    assert last_attempt_at is not None


@pytest.mark.anyio
async def test_worker_marks_failed_after_max_retries(monkeypatch):
    """After exhausting retries the worker should mark the submission as failed and keep the job for auditing."""

    _require_db_or_skip()
    _, worker_dsn, job_id, submission_id = await _prepare_submission_with_job(
        idempotency_key="worker-fail-path"
    )

    _force_submission_to_file(worker_dsn, submission_id)

    monkeypatch.setenv("WORKER_BACKOFF_SECONDS", "1")
    worker_module.MAX_RETRIES = 1  # type: ignore[attr-defined]

    tick = datetime.now(tz=timezone.utc) + timedelta(hours=1)
    _set_job_visibility(worker_dsn, job_id, visible_at=tick)
    run_once(
        dsn=worker_dsn,
        vision_adapter=_PermanentVisionAdapter(),
        feedback_adapter=_StubFeedbackAdapter(feedback_md="unused"),
        now=tick,
        test_run_id=current_test_run_id(),
    )

    # Use a slightly larger offset than the nominal backoff to avoid
    # flakiness on slower CI/DB clocks. With WORKER_BACKOFF_SECONDS=1 and
    # first retry_count=0, visible_at = now + 1s; we wait 3s.
    second_tick = tick + timedelta(seconds=3)
    processed = run_once(
        dsn=worker_dsn,
        vision_adapter=_PermanentVisionAdapter(),
        feedback_adapter=_StubFeedbackAdapter(feedback_md="unused"),
        now=second_tick,
        test_run_id=current_test_run_id(),
    )

    assert processed is True

    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute(
                """
                select status,
                       retry_count,
                       error_code
                  from public.learning_submission_jobs
                 where id = %s::uuid
                """,
                (job_id,),
            )
            status, retry_count, job_error = cur.fetchone()

            cur.execute(
                """
                select analysis_status,
                       error_code,
                       vision_attempts,
                       vision_last_error
                  from public.learning_submissions
                 where id = %s::uuid
                """,
                (submission_id,),
            )
            submission_status, submission_error, vision_attempts, vision_last_error = cur.fetchone()

    assert status == "failed"
    assert retry_count == 1
    assert job_error == "vision_failed"

    assert submission_status == "failed"
    assert submission_error == "vision_failed"
    assert vision_attempts == 2
    assert vision_last_error is not None
    assert "permanent vision failure" in vision_last_error


@pytest.mark.anyio
@pytest.mark.parametrize("feedback_error_message", ["temporary feedback issue", "provider_rate_limited"])
async def test_worker_retries_feedback_transient_error(monkeypatch, feedback_error_message: str):
    """Transient feedback errors should keep submission pending and record retry metadata."""

    _require_db_or_skip()
    _fixture, worker_dsn, job_id, submission_id = await _prepare_submission_with_job(
        idempotency_key="worker-feedback-retry"
    )

    monkeypatch.setenv("WORKER_BACKOFF_SECONDS", "3")
    worker_module.MAX_RETRIES = 3  # type: ignore[attr-defined]
    tick = datetime.now(tz=timezone.utc) + timedelta(hours=1)
    _set_job_visibility(worker_dsn, job_id, visible_at=tick)

    processed = run_once(
        dsn=worker_dsn,
        vision_adapter=_StubVisionAdapter(text_md="## Student answer\n\nContent."),
        feedback_adapter=_TransientFeedbackAdapter(message=feedback_error_message),
        now=tick,
        test_run_id=current_test_run_id(),
    )

    assert processed is True

    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute(
                """
                select status,
                       retry_count,
                       visible_at
                  from public.learning_submission_jobs
                 where id = %s::uuid
                """,
                (job_id,),
            )
            status, retry_count, visible_at = cur.fetchone()

            cur.execute(
                """
                select analysis_status,
                       error_code,
                       feedback_last_error,
                       feedback_last_attempt_at,
                       vision_attempts
                  from public.learning_submissions
                 where id = %s::uuid
                """,
                (submission_id,),
            )
            (
                submission_status,
                submission_error,
                feedback_last_error,
                feedback_last_attempt_at,
                vision_attempts,
            ) = cur.fetchone()

    assert status == "queued"
    assert retry_count == 1
    assert visible_at.tzinfo is not None
    assert visible_at >= tick + timedelta(seconds=3)
    assert visible_at < tick + timedelta(seconds=30)

    assert submission_status == "pending"
    assert submission_error == "feedback_retrying"
    assert feedback_last_error is not None
    assert feedback_error_message in feedback_last_error
    assert feedback_last_attempt_at is not None
    assert vision_attempts == 0


@pytest.mark.anyio
async def test_worker_marks_feedback_failure_records_job_error(monkeypatch: pytest.MonkeyPatch):
    """Permanent feedback failures should persist error_code for audit trail."""

    _require_db_or_skip()
    # Ensure worker and app talk to the same database for this test
    monkeypatch.setenv("SERVICE_ROLE_DSN", _dsn())
    fixture, worker_dsn, job_id, submission_id = await _prepare_submission_with_job(
        idempotency_key="worker-feedback-fail"
    )

    tick = datetime.now(tz=timezone.utc)
    processed = run_once(
        dsn=worker_dsn,
        vision_adapter=_StubVisionAdapter(text_md="## Answer\n\nContent."),
        feedback_adapter=_PermanentFeedbackAdapter(),
        now=tick,
        test_run_id=current_test_run_id(),
    )

    assert processed is True

    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute(
                """
                select status,
                       retry_count,
                       error_code
                  from public.learning_submission_jobs
                 where id = %s::uuid
                """,
                (job_id,),
            )
            status, retry_count, job_error_code = cur.fetchone()

            cur.execute(
                "select set_config('app.current_sub', %s, true)",
                (fixture.student_sub,),
            )
            cur.execute(
                """
                select analysis_status,
                       error_code,
                       feedback_last_error
                  from public.learning_submissions
                 where id = %s::uuid
                """,
                (submission_id,),
            )
            submission_status, submission_error, feedback_last_error = cur.fetchone()

    assert status == "failed"
    assert retry_count == 0
    assert job_error_code == "feedback_failed"

    assert submission_status == "failed"
    assert submission_error == "feedback_failed"
    assert feedback_last_error is not None
    assert "permanent feedback failure" in feedback_last_error


@pytest.mark.anyio
async def test_worker_marks_complex_image_provider_admission_as_feedback_failed(monkeypatch: pytest.MonkeyPatch):
    """Complex-image provider admission failures stay internal but do not retry."""

    _require_db_or_skip()
    monkeypatch.setenv("SERVICE_ROLE_DSN", _dsn())
    fixture, worker_dsn, job_id, submission_id = await _prepare_submission_with_job(
        idempotency_key="worker-complex-image-provider-admission"
    )
    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute(
                """
                update public.learning_submission_jobs
                   set payload = payload || '{"analysis_mode": "visual_direct"}'::jsonb
                 where id = %s::uuid
                """,
                (job_id,),
            )
        conn.commit()

    tick = datetime.now(tz=timezone.utc)
    feedback_adapter = _ImageTooComplexFeedbackAdapter()
    processed = run_once(
        dsn=worker_dsn,
        vision_adapter=_StubVisionAdapter(text_md="## Answer\n\nContent."),
        feedback_adapter=feedback_adapter,
        now=tick,
        test_run_id=current_test_run_id(),
    )

    assert processed is True
    assert feedback_adapter.calls == 0
    assert feedback_adapter.visual_calls == 1

    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute(
                """
                select status,
                       retry_count,
                       error_code
                  from public.learning_submission_jobs
                 where id = %s::uuid
                """,
                (job_id,),
            )
            status, retry_count, job_error_code = cur.fetchone()

            cur.execute(
                "select set_config('app.current_sub', %s, true)",
                (fixture.student_sub,),
            )
            cur.execute(
                """
                select analysis_status,
                       error_code,
                       feedback_last_error
                  from public.learning_submissions
                 where id = %s::uuid
                """,
                (submission_id,),
            )
            submission_status, submission_error, feedback_last_error = cur.fetchone()

    assert status == "failed"
    assert retry_count == 0
    assert job_error_code == "feedback_failed"
    assert submission_status == "failed"
    assert submission_error == "feedback_failed"
    assert feedback_last_error == "image_too_complex_for_provider"


@pytest.mark.anyio
async def test_worker_logs_safe_feedback_context_and_persists_specific_feedback_reason(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
):
    """Feedback failures should keep stable codes while logging safe job context."""

    _require_db_or_skip()
    monkeypatch.setenv("SERVICE_ROLE_DSN", _dsn())
    fixture, worker_dsn, job_id, submission_id = await _prepare_submission_with_job(
        idempotency_key="worker-feedback-specific-reason"
    )

    caplog.set_level(logging.INFO, logger=worker_module.LOG.name)
    tick = datetime.now(tz=timezone.utc)
    processed = run_once(
        dsn=worker_dsn,
        vision_adapter=_StubVisionAdapter(text_md="## Answer\n\nContent."),
        feedback_adapter=_PermanentFeedbackAdapter(message="invalid_feedback_format"),
        now=tick,
        test_run_id=current_test_run_id(),
    )

    assert processed is True

    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute(
                """
                select status,
                       retry_count,
                       error_code
                  from public.learning_submission_jobs
                 where id = %s::uuid
                """,
                (job_id,),
            )
            status, retry_count, job_error_code = cur.fetchone()

            cur.execute(
                "select set_config('app.current_sub', %s, true)",
                (fixture.student_sub,),
            )
            cur.execute(
                """
                select analysis_status,
                       error_code,
                       feedback_last_error
                  from public.learning_submissions
                 where id = %s::uuid
                """,
                (submission_id,),
            )
            submission_status, submission_error, feedback_last_error = cur.fetchone()

    assert status == "failed"
    assert retry_count == 0
    assert job_error_code == "feedback_failed"
    assert submission_status == "failed"
    assert submission_error == "feedback_failed"
    assert feedback_last_error == "invalid_feedback_format"

    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert "invalid_feedback_format" in messages
    assert fixture.task["id"] in messages
    assert "intent=submit" in messages
    assert "criteria_count=2" in messages


@pytest.mark.anyio
async def test_worker_marks_invalid_analysis_without_retry(monkeypatch: pytest.MonkeyPatch):
    """Deterministic invalid-analysis errors must fail once with a precise error code."""

    _require_db_or_skip()
    monkeypatch.setenv("SERVICE_ROLE_DSN", _dsn())
    fixture, worker_dsn, job_id, submission_id = await _prepare_submission_with_job(
        idempotency_key="worker-feedback-invalid-analysis"
    )

    tick = datetime.now(tz=timezone.utc)
    processed = run_once(
        dsn=worker_dsn,
        vision_adapter=_StubVisionAdapter(text_md="## Answer\n\nContent."),
        feedback_adapter=_InvalidAnalysisFeedbackAdapter(),
        now=tick,
        test_run_id=current_test_run_id(),
    )

    assert processed is True

    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute(
                """
                select status,
                       retry_count,
                       error_code
                  from public.learning_submission_jobs
                 where id = %s::uuid
                """,
                (job_id,),
            )
            status, retry_count, job_error_code = cur.fetchone()

            cur.execute(
                "select set_config('app.current_sub', %s, true)",
                (fixture.student_sub,),
            )
            cur.execute(
                """
                select analysis_status,
                       error_code,
                       feedback_last_error
                  from public.learning_submissions
                 where id = %s::uuid
                """,
                (submission_id,),
            )
            submission_status, submission_error, feedback_last_error = cur.fetchone()

    assert status == "failed"
    assert retry_count == 0
    assert job_error_code == "feedback_invalid_analysis"
    assert submission_status == "failed"
    assert submission_error == "feedback_invalid_analysis"
    assert feedback_last_error == "feedback_invalid_analysis"


@pytest.mark.anyio
async def test_worker_success_updates_metrics_and_gauge():
    """Successful runs should increment processed counter and leave inflight gauge at zero."""

    _require_db_or_skip()
    telemetry.reset_for_tests()
    _fixture, worker_dsn, job_id, submission_id = await _prepare_submission_with_job(
        idempotency_key="worker-metrics-success"
    )

    tick = datetime.now(tz=timezone.utc) + timedelta(hours=1)
    _set_job_visibility(worker_dsn, job_id, visible_at=tick)
    processed = run_once(
        dsn=worker_dsn,
        vision_adapter=_StubVisionAdapter(text_md="# Metrics Success"),
        feedback_adapter=_StubFeedbackAdapter(feedback_md="Well done"),
        now=tick,
        test_run_id=current_test_run_id(),
    )

    assert processed is True
    assert _counter_value("ai_worker_processed_total", status="completed") == 1
    assert _gauge_value("analysis_jobs_inflight") == 0.0


@pytest.mark.anyio
async def test_worker_retry_emits_retry_metric_and_warning(caplog: pytest.LogCaptureFixture):
    """Transient vision errors should bump retry metrics and emit structured warnings."""

    _require_db_or_skip()
    telemetry.reset_for_tests()
    _fixture, worker_dsn, job_id, submission_id = await _prepare_submission_with_job(
        idempotency_key="worker-metrics-retry"
    )
    _force_submission_to_file(worker_dsn, submission_id)

    caplog.set_level(logging.INFO, logger=worker_module.LOG.name)
    tick = datetime.now(tz=timezone.utc) + timedelta(hours=1)
    _set_job_visibility(worker_dsn, job_id, visible_at=tick)
    processed = run_once(
        dsn=worker_dsn,
        vision_adapter=_TransientVisionAdapter(message="temporary retry"),
        feedback_adapter=_StubFeedbackAdapter(feedback_md="unused"),
        now=tick,
        test_run_id=current_test_run_id(),
    )

    assert processed is True
    assert _counter_value("ai_worker_retry_total", phase="vision") == 1
    assert _gauge_value("analysis_jobs_inflight") == 0.0

    warnings = [rec for rec in caplog.records if rec.levelname in ("WARNING", "INFO")]
    assert any("temporary retry" in rec.getMessage() and "next_visible_at" in rec.getMessage() for rec in warnings)


@pytest.mark.anyio
async def test_worker_concurrency_leases_multiple_jobs(monkeypatch: pytest.MonkeyPatch):
    """Worker should lease and process up to WORKER_CONCURRENCY jobs in one tick."""

    _require_db_or_skip()
    telemetry.reset_for_tests()
    monkeypatch.setenv("WORKER_CONCURRENCY", "2")
    test_run_id = current_test_run_id()

    worker_dsn = os.getenv("SERVICE_ROLE_DSN") or _dsn()
    teacher_sub = f"teacher-{uuid.uuid4()}"
    student_sub = f"student-{uuid.uuid4()}"

    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cleanup_learning_jobs_for_run(conn, test_run_id)

            cur.execute("select set_config('app.current_sub', %s, false)", (teacher_sub,))
            cur.execute(
                "insert into public.courses (title, teacher_id) values (%s, %s) returning id",
                ("Concurrency Course", teacher_sub),
            )
            course_id = cur.fetchone()[0]
            cur.execute(
                "insert into public.units (title, author_id) values (%s, %s) returning id",
                ("Concurrency Unit", teacher_sub),
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
                (unit_id, section_id, "Beschreibe den Graphen", ["Kriterium A"], 1),
            )
            task_id = cur.fetchone()[0]

            submission_ids: list[str] = []
            payloads: list[dict] = []
            for idx in range(2):
                submission_id = str(uuid.uuid4())
                submission_ids.append(submission_id)
                attempt_nr = idx + 1
                cur.execute(
                    """
                    insert into public.learning_submissions (
                        id, course_id, task_id, section_id, student_sub, kind,
                        text_body, storage_key, mime_type, size_bytes, sha256,
                        attempt_nr, analysis_status, analysis_json
                    ) values (
                        %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s, 'text',
                        %s, null, null, null, null,
                        %s, 'pending', null
                    )
                    """,
                    (
                        submission_id,
                        course_id,
                        task_id,
                        section_id,
                        student_sub,
                        f"Text answer {idx}",
                        attempt_nr,
                    ),
                )
                payload = {
                    # Tag test-created jobs so a running docker worker can ignore them.
                    # (See `WORKER_SKIP_PYTEST_JOBS` in docker-compose.yml and the
                    # dedicated contract tests below.)
                    "_gustav_source": "pytest",
                    "_gustav_test_run_id": test_run_id,
                    "submission_id": submission_id,
                    "course_id": str(course_id),
                    "task_id": str(task_id),
                    "student_sub": student_sub,
                    "kind": "text",
                    "attempt_nr": attempt_nr,
                    "criteria": ["Kriterium A"],
                }
                payloads.append(payload)
                cur.execute(
                    "insert into public.learning_submission_jobs (submission_id, payload) values (%s::uuid, %s::jsonb)",
                    (submission_id, json.dumps(payload)),
                )
        conn.commit()

    processed = run_once(
        dsn=worker_dsn,
        vision_adapter=_StubVisionAdapter(text_md="## Vision Extract\n\nContent."),
        feedback_adapter=_StubFeedbackAdapter(feedback_md="Feedback"),
        now=datetime.now(tz=timezone.utc),
        test_run_id=test_run_id,
    )

    assert processed is True

    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute(
                "select count(*) from public.learning_submission_jobs where payload->>'_gustav_test_run_id' = %s",
                (test_run_id,),
            )
            remaining_jobs = int(cur.fetchone()[0])
            cur.execute(
                """
                select analysis_status, text_body from public.learning_submissions
                where id = any(%s::uuid[])
                """,
                (submission_ids,),
            )
            rows = cur.fetchall()

    assert remaining_jobs == 0
    assert {row[0] for row in rows} == {"completed"}
    assert _gauge_value("analysis_jobs_inflight") == 0.0


@pytest.mark.anyio
async def test_worker_feedback_retry_uses_cached_ocr(monkeypatch: pytest.MonkeyPatch):
    """When OCR text is cached in the job, Vision should not run again."""

    _require_db_or_skip()
    telemetry.reset_for_tests()
    test_run_id = current_test_run_id()
    worker_dsn = os.getenv("SERVICE_ROLE_DSN") or _dsn()

    teacher_sub = f"teacher-{uuid.uuid4()}"
    student_sub = f"student-{uuid.uuid4()}"
    cached_text = "## Cached OCR\n\nLine A\nLine B"

    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cleanup_learning_jobs_for_run(conn, test_run_id)
            cur.execute("select set_config('app.current_sub', %s, false)", (teacher_sub,))
            cur.execute(
                "insert into public.courses (title, teacher_id) values (%s, %s) returning id",
                ("OCR Reuse Course", teacher_sub),
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
                insert into public.unit_tasks (unit_id, section_id, instruction_md, criteria, position)
                values (%s, %s, %s, %s::text[], %s) returning id
                """,
                (unit_id, section_id, "Beschreibe den Graphen", ["Kriterium A"], 1),
            )
            task_id = cur.fetchone()[0]

            submission_id = str(uuid.uuid4())
            cur.execute(
                """
                insert into public.learning_submissions (
                    id, course_id, task_id, section_id, student_sub, kind,
                    text_body, storage_key, mime_type, size_bytes, sha256,
                    attempt_nr, analysis_status, analysis_json
                ) values (
                    %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s, 'file',
                    null, 'dummy/storage', 'application/pdf', 1024, %s,
                    1, 'extracted', null
                )
                """,
                (submission_id, course_id, task_id, section_id, student_sub, "0" * 64),
            )
            payload = {
                "_gustav_source": "pytest",
                "_gustav_test_run_id": test_run_id,
                "submission_id": submission_id,
                "course_id": str(course_id),
                "task_id": str(task_id),
                "student_sub": student_sub,
                "kind": "file",
                "attempt_nr": 1,
                "criteria": ["Kriterium A"],
                "cached_text_md": cached_text,
            }
            cur.execute(
                "insert into public.learning_submission_jobs (submission_id, payload) values (%s::uuid, %s::jsonb)",
                (submission_id, json.dumps(payload)),
            )
        conn.commit()

    counting_vision = _CountingVisionAdapter()
    processed = run_once(
        dsn=worker_dsn,
        vision_adapter=counting_vision,
        feedback_adapter=_StubFeedbackAdapter(feedback_md="Feedback"),
        now=datetime.now(tz=timezone.utc),
        test_run_id=test_run_id,
    )

    assert processed is True
    assert counting_vision.calls == 0

    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute(
                "select count(*) from public.learning_submission_jobs where payload->>'_gustav_test_run_id' = %s",
                (test_run_id,),
            )
            remaining_jobs = int(cur.fetchone()[0])
            cur.execute(
                """
                select analysis_status, text_body from public.learning_submissions
                where id = %s::uuid
                """,
                (submission_id,),
            )
            status, text_body = cur.fetchone()

    assert remaining_jobs == 0
    assert status == "completed"
    assert isinstance(text_body, str) and "Cached OCR" in text_body
    assert _gauge_value("analysis_jobs_inflight") == 0.0


@pytest.mark.anyio
async def test_worker_releases_job_when_processing_crashes(monkeypatch: pytest.MonkeyPatch):
    """If processing raises, the job should not remain leased indefinitely."""

    _require_db_or_skip()
    telemetry.reset_for_tests()
    monkeypatch.setenv("WORKER_CONCURRENCY", "1")
    monkeypatch.setenv("WORKER_LEASE_SECONDS", "60")
    # Keep this test deterministic across environments:
    # - local run_once must lease pytest-tagged jobs (explicit false),
    # - external docker workers (default true) should skip them.
    monkeypatch.setenv("WORKER_SKIP_PYTEST_JOBS", "false")
    lease_now = datetime.now(tz=timezone.utc) + timedelta(minutes=5)
    test_run_id = current_test_run_id()

    worker_dsn = os.getenv("SERVICE_ROLE_DSN") or _dsn()
    teacher_sub = f"teacher-{uuid.uuid4()}"
    student_sub = f"student-{uuid.uuid4()}"

    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cleanup_learning_jobs_for_run(conn, test_run_id)
            cur.execute("select set_config('app.current_sub', %s, false)", (teacher_sub,))
            cur.execute(
                "insert into public.courses (title, teacher_id) values (%s, %s) returning id",
                ("Crash Course", teacher_sub),
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
                insert into public.unit_tasks (unit_id, section_id, instruction_md, criteria, position)
                values (%s, %s, %s, %s::text[], %s) returning id
                """,
                (unit_id, section_id, "Beschreibe den Graphen", ["Kriterium A"], 1),
            )
            task_id = cur.fetchone()[0]

            submission_id = str(uuid.uuid4())
            cur.execute(
                """
                insert into public.learning_submissions (
                    id, course_id, task_id, section_id, student_sub, kind,
                    text_body, storage_key, mime_type, size_bytes, sha256,
                    attempt_nr, analysis_status, analysis_json
                ) values (
                    %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s, 'text',
                    %s, null, null, null, null,
                    1, 'pending', null
                )
                """,
                (
                    submission_id,
                    course_id,
                    task_id,
                    section_id,
                    student_sub,
                    "Crash submission",
                ),
            )
            payload = {
                "_gustav_source": "pytest",
                "_gustav_test_run_id": test_run_id,
                "submission_id": submission_id,
                "course_id": str(course_id),
                "task_id": str(task_id),
                "student_sub": student_sub,
                "kind": "text",
                "attempt_nr": 1,
                "criteria": ["Kriterium A"],
            }
            cur.execute(
                """
                insert into public.learning_submission_jobs (submission_id, payload, visible_at)
                values (%s::uuid, %s::jsonb, %s)
                """,
                (submission_id, json.dumps(payload), lease_now),
            )
        conn.commit()

    def _boom(**kwargs):
        raise RuntimeError("processing crashed")

    monkeypatch.setattr(worker_module, "_process_job", _boom)

    with pytest.raises(RuntimeError):
        run_once(
            dsn=worker_dsn,
            vision_adapter=_StubVisionAdapter(text_md="# boom"),
            feedback_adapter=_StubFeedbackAdapter(feedback_md="unused"),
            now=lease_now,
            test_run_id=test_run_id,
        )

    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute(
                """
                select status, lease_key, leased_until
                  from public.learning_submission_jobs
                 where submission_id = %s::uuid
                """,
                (submission_id,),
            )
            status, lease_key, leased_until = cur.fetchone()

    assert status == "queued"
    assert lease_key is None
    assert leased_until is None


@pytest.mark.anyio
async def test_worker_concurrency_is_capped(monkeypatch: pytest.MonkeyPatch):
    """Extremely high WORKER_CONCURRENCY should be capped to a safe maximum."""

    _require_db_or_skip()
    telemetry.reset_for_tests()
    monkeypatch.setenv("WORKER_CONCURRENCY", "10")
    test_run_id = current_test_run_id()

    worker_dsn = os.getenv("SERVICE_ROLE_DSN") or _dsn()
    teacher_sub = f"teacher-{uuid.uuid4()}"
    student_sub = f"student-{uuid.uuid4()}"

    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cleanup_learning_jobs_for_run(conn, test_run_id)
            cur.execute("select set_config('app.current_sub', %s, false)", (teacher_sub,))
            cur.execute(
                "insert into public.courses (title, teacher_id) values (%s, %s) returning id",
                ("Capped Concurrency Course", teacher_sub),
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
                insert into public.unit_tasks (unit_id, section_id, instruction_md, criteria, position)
                values (%s, %s, %s, %s::text[], %s) returning id
                """,
                (unit_id, section_id, "Beschreibe den Graphen", ["Kriterium A"], 1),
            )
            task_id = cur.fetchone()[0]

            submission_ids: list[str] = []
            for idx in range(6):
                submission_id = str(uuid.uuid4())
                submission_ids.append(submission_id)
                cur.execute(
                    """
                    insert into public.learning_submissions (
                        id, course_id, task_id, section_id, student_sub, kind,
                        text_body, storage_key, mime_type, size_bytes, sha256,
                        attempt_nr, analysis_status, analysis_json
                    ) values (
                        %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s, 'text',
                        %s, null, null, null, null,
                        %s, 'pending', null
                    )
                    """,
                    (
                        submission_id,
                        course_id,
                        task_id,
                        section_id,
                        student_sub,
                        f"Text answer {idx}",
                        idx + 1,
                    ),
                )
                payload = {
                    "_gustav_source": "pytest",
                    "_gustav_test_run_id": test_run_id,
                    "submission_id": submission_id,
                    "course_id": str(course_id),
                    "task_id": str(task_id),
                    "student_sub": student_sub,
                    "kind": "text",
                    "attempt_nr": idx + 1,
                    "criteria": ["Kriterium A"],
                }
                cur.execute(
                    "insert into public.learning_submission_jobs (submission_id, payload) values (%s::uuid, %s::jsonb)",
                    (submission_id, json.dumps(payload)),
                )
        conn.commit()

    processed = run_once(
        dsn=worker_dsn,
        vision_adapter=_StubVisionAdapter(text_md="## Vision Extract\n\nContent."),
        feedback_adapter=_StubFeedbackAdapter(feedback_md="Feedback"),
        now=datetime.now(tz=timezone.utc),
        test_run_id=test_run_id,
    )

    assert processed is True

    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute(
                "select count(*) from public.learning_submission_jobs where payload->>'_gustav_test_run_id' = %s",
                (test_run_id,),
            )
            remaining_jobs = int(cur.fetchone()[0])

    assert remaining_jobs >= 2, "concurrency should be capped, leaving some jobs queued"


@pytest.mark.anyio
async def test_worker_extends_lease_window(monkeypatch: pytest.MonkeyPatch):
    """Leased jobs should have a lease_until sufficiently in the future to avoid premature reprocessing."""

    _require_db_or_skip()
    telemetry.reset_for_tests()
    monkeypatch.setenv("WORKER_LEASE_SECONDS", "2")

    _fixture, worker_dsn, job_id, _submission_id = await _prepare_submission_with_job(
        idempotency_key="worker-lease-extend"
    )

    now = datetime.now(tz=timezone.utc)
    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        leased = worker_module._lease_jobs(conn, now=now, limit=1, test_run_id=current_test_run_id())
        job = leased[0] if leased else None
        conn.commit()
    assert job is not None

    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute(
                "select leased_until from public.learning_submission_jobs where id = %s::uuid",
                (job_id,),
            )
            leased_until = cur.fetchone()[0]
        conn.commit()

    expected_min = now + timedelta(seconds=worker_module._lease_duration_seconds())
    assert leased_until >= expected_min

    # Cleanup to avoid leaking leased jobs to other tests
    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        cleanup_learning_jobs_for_run(conn)
        conn.commit()


@pytest.mark.anyio
async def test_create_submission_tags_queue_jobs_under_pytest(monkeypatch: pytest.MonkeyPatch):
    """Jobs created by in-process tests must be tagged so docker workers can ignore them."""

    _require_db_or_skip()
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "worker-job-tagging")
    test_run_id = current_test_run_id()

    fixture = await _prepare_learning_fixture()
    dsn = _dsn()
    worker_dsn = os.getenv("SERVICE_ROLE_DSN") or dsn

    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        cleanup_learning_jobs_for_run(conn, test_run_id)
        conn.commit()

    repo = DBLearningRepo(dsn=dsn)
    usecase = CreateSubmissionUseCase(repo)
    submission = usecase.execute(
        CreateSubmissionInput(
            course_id=fixture.course_id,
            task_id=fixture.task["id"],
            student_sub=fixture.student_sub,
            intent="submit",
            kind="text",
            text_body="pytest tags jobs",
            storage_key=None,
            mime_type=None,
            size_bytes=None,
            sha256=None,
            score_raw=None,
            score_max=None,
            idempotency_key=f"pytest-job-tag-{uuid.uuid4()}",
        )
    )

    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute(
                """
                select payload
                  from public.learning_submission_jobs
                 where submission_id = %s::uuid
                 order by created_at desc
                 limit 1
                """,
                (submission["id"],),
            )
            row = cur.fetchone()
        conn.commit()
    assert row is not None
    payload = row[0]
    if isinstance(payload, str):
        payload = json.loads(payload)
    assert payload.get("_gustav_source") == "pytest"
    assert payload.get("_gustav_test_run_id") == test_run_id

    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        cleanup_learning_jobs_for_run(conn, test_run_id)
        conn.commit()


@pytest.mark.anyio
async def test_worker_skips_pytest_tagged_jobs_when_configured(monkeypatch: pytest.MonkeyPatch):
    """When WORKER_SKIP_PYTEST_JOBS=true, leasing must ignore pytest-tagged jobs."""

    _require_db_or_skip()
    telemetry.reset_for_tests()
    monkeypatch.setenv("WORKER_SKIP_PYTEST_JOBS", "true")
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "worker-skip-pytest-jobs")
    test_run_id = current_test_run_id()

    fixture = await _prepare_learning_fixture()
    dsn = _dsn()
    worker_dsn = os.getenv("SERVICE_ROLE_DSN") or dsn

    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        cleanup_learning_jobs_for_run(conn, test_run_id)
        conn.commit()

    repo = DBLearningRepo(dsn=dsn)
    usecase = CreateSubmissionUseCase(repo)
    submission_pytest = usecase.execute(
        CreateSubmissionInput(
            course_id=fixture.course_id,
            task_id=fixture.task["id"],
            student_sub=fixture.student_sub,
            intent="submit",
            kind="text",
            text_body="pytest job",
            storage_key=None,
            mime_type=None,
            size_bytes=None,
            sha256=None,
            score_raw=None,
            score_max=None,
            idempotency_key=f"pytest-job-{uuid.uuid4()}",
        )
    )
    submission_real = usecase.execute(
        CreateSubmissionInput(
            course_id=fixture.course_id,
            task_id=fixture.task["id"],
            student_sub=fixture.student_sub,
            intent="submit",
            kind="text",
            text_body="non-pytest job",
            storage_key=None,
            mime_type=None,
            size_bytes=None,
            sha256=None,
            score_raw=None,
            score_max=None,
            idempotency_key=f"non-pytest-job-{uuid.uuid4()}",
        )
    )

    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute(
                "select id::text from public.learning_submission_jobs where submission_id = %s::uuid",
                (submission_pytest["id"],),
            )
            pytest_job_id = cur.fetchone()[0]
            cur.execute(
                "select id::text from public.learning_submission_jobs where submission_id = %s::uuid",
                (submission_real["id"],),
            )
            real_job_id = cur.fetchone()[0]

            # Remove the pytest marker from one job so it represents a "real" queue item.
            cur.execute(
                "update public.learning_submission_jobs set payload = payload - '_gustav_source' where id = %s::uuid",
                (real_job_id,),
            )
        conn.commit()

    now = datetime.now(tz=timezone.utc)
    # Make the jobs visible and lease in the *same* transaction. This avoids
    # flakiness when a docker worker is running concurrently: the worker can't
    # see the jobs until we commit, and by then the "real" job is already leased.
    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            for job_id, visible_at in (
                (pytest_job_id, now - timedelta(seconds=5)),
                (real_job_id, now - timedelta(seconds=4)),
            ):
                cur.execute(
                    """
                    update public.learning_submission_jobs
                       set visible_at = %s,
                           status = 'queued',
                           retry_count = 0,
                           error_code = null,
                           lease_key = null,
                           leased_until = null,
                           updated_at = now()
                     where id = %s::uuid
                    """,
                    (visible_at, job_id),
                )
        leased_jobs = worker_module._lease_jobs(conn, now=now, limit=1, test_run_id=test_run_id)
        leased = leased_jobs[0] if leased_jobs else None
        conn.commit()
    assert leased is not None
    assert leased.id == real_job_id

    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        cleanup_learning_jobs_for_run(conn, test_run_id)
        conn.commit()
