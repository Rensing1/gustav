"""
Worker should pass task context (instruction + teacher-only AI context) to the
Feedback adapter when supported.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Sequence

import pytest
import httpx
from httpx import ASGITransport

pytest.importorskip("psycopg")
import psycopg  # type: ignore  # noqa: E402

import main  # type: ignore  # noqa: E402
from backend.tests.utils.db import require_db_or_skip as _require_db_or_skip  # noqa: E402
from backend.learning.repo_db import DBLearningRepo  # noqa: E402
from backend.learning.usecases.submissions import (  # noqa: E402
    CreateSubmissionInput,
    CreateSubmissionUseCase,
)
from backend.learning.workers.process_learning_submission_jobs import (  # noqa: E402
    FeedbackResult,
    VisionResult,
    run_once,
)
from backend.tests.test_learning_api_contract import _prepare_learning_fixture  # type: ignore  # noqa: E402
from backend.tests.utils.db_isolation import cleanup_learning_jobs_for_run, current_test_run_id  # noqa: E402
from identity_access.stores import SessionStore  # type: ignore  # noqa: E402


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=ASGITransport(app=main.app),
        base_url="http://test",
        headers={"Origin": "http://test"},
    )


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


@pytest.mark.anyio
async def test_job_payload_does_not_contain_teacher_context():
    _require_db_or_skip()
    fixture = await _prepare_learning_fixture()
    dsn = _dsn()
    worker_dsn = os.getenv("SERVICE_ROLE_DSN") or dsn

    # Reset queue
    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        cleanup_learning_jobs_for_run(conn)
        conn.commit()

    # Enqueue a new submission
    repo = DBLearningRepo(dsn=dsn)
    create = CreateSubmissionUseCase(repo)
    submission = create.execute(
        CreateSubmissionInput(
            course_id=fixture.course_id,
            task_id=fixture.task["id"],
            student_sub=fixture.student_sub,
            kind="text",
            text_body="Antwort",
            storage_key=None,
            mime_type=None,
            size_bytes=None,
            sha256=None,
            score_raw=None,
            score_max=None,
            idempotency_key="worker-payload-context",
        )
    )
    submission_id = submission["id"]

    # Inspect job payload
    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute(
                "select payload from public.learning_submission_jobs where submission_id = %s::uuid",
                (submission_id,),
            )
            row = cur.fetchone()
            assert row is not None, "Job row missing"
            payload = row[0]
            if isinstance(payload, str):
                payload = json.loads(payload)

    # The job payload must not leak teacher-only context.
    assert "teacher_context_md" not in payload


@dataclass
class _Vision:
    text: str

    def extract(self, *, submission: dict, job_payload: dict) -> VisionResult:
        return VisionResult(text_md=self.text)


class _FeedbackCapturingAdapter:
    def __init__(self) -> None:
        self.last_kwargs: dict | None = None

    def analyze(  # type: ignore[no-untyped-def]
        self,
        *,
        text_md: str,
        criteria: Sequence[str],
        instruction_md=None,
        teacher_context_md=None,
    ) -> FeedbackResult:
        # Capture context for assertions and return a minimal valid result
        self.last_kwargs = {
            "text_md": text_md,
            "criteria": list(criteria),
            "instruction_md": instruction_md,
            "teacher_context_md": teacher_context_md,
        }
        return FeedbackResult(
            feedback_md="Prosa-Feedback",
            analysis_json={"schema": "criteria.v2", "score": 3, "criteria_results": []},
        )

    def analyze_visual(  # type: ignore[no-untyped-def]
        self,
        *,
        submission: dict,
        job_payload: dict,
        criteria: Sequence[str],
        instruction_md=None,
        teacher_context_md=None,
    ) -> FeedbackResult:
        self.last_kwargs = {
            "submission": submission,
            "job_payload": job_payload,
            "criteria": list(criteria),
            "instruction_md": instruction_md,
            "teacher_context_md": teacher_context_md,
        }
        return FeedbackResult(
            feedback_md="**Das ist dir gut gelungen:** A.\n\n**Das kannst du besser:** B.",
            analysis_json={"schema": "criteria.v2", "score": 3, "criteria_results": []},
        )


async def _prepare_modular_learning_fixture() -> dict:
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402
    import routes.learning as learning  # noqa: E402

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
        from backend.learning.repo_db import DBLearningRepo as _DBLearningRepo  # type: ignore

        assert isinstance(learning.REPO, _DBLearningRepo)
    except Exception:
        pytest.skip("DB-backed repos required")

    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="teacher-worker-modular", name="Lehrkraft", roles=["teacher"])  # type: ignore
    student = main.SESSION_STORE.create(sub="student-worker-modular", name="Schüler", roles=["student"])  # type: ignore

    async with (await _client()) as client:
        client.cookies.set("gustav_session", teacher.session_id)
        course_resp = await client.post("/api/teaching/courses", json={"title": "Kurs Modular Worker"})
        assert course_resp.status_code == 201, course_resp.text
        course_id = course_resp.json()["id"]

        unit_resp = await client.post(
            "/api/teaching/units",
            json={"title": "Einheit Modular Worker", "unit_type": "modular"},
        )
        assert unit_resp.status_code == 201, unit_resp.text
        unit_id = unit_resp.json()["id"]

        section_resp = await client.post(
            f"/api/teaching/units/{unit_id}/sections",
            json={"title": "Modul 1"},
        )
        assert section_resp.status_code == 201, section_resp.text
        section_id = section_resp.json()["id"]

        task_resp = await client.post(
            f"/api/teaching/units/{unit_id}/sections/{section_id}/tasks",
            json={
                "instruction_md": "### Entwickle eine begründete Zukunftshypothese",
                "criteria": ["Kriterium A", "Kriterium B"],
                "teacher_context_md": "Achte auf Belege aus Material M1 und M2.",
                "max_attempts": 2,
            },
        )
        assert task_resp.status_code == 201, task_resp.text
        task = task_resp.json()

        module_resp = await client.post(
            f"/api/teaching/courses/{course_id}/modules",
            json={"unit_id": unit_id},
        )
        assert module_resp.status_code == 201, module_resp.text
        module_id = module_resp.json()["id"]

        member_resp = await client.post(
            f"/api/teaching/courses/{course_id}/members",
            json={"student_sub": student.sub},  # type: ignore[attr-defined]
        )
        assert member_resp.status_code in (201, 204), member_resp.text

    return {
        "teacher_session_id": teacher.session_id,
        "student_session_id": student.session_id,
        "student_sub": student.sub,  # type: ignore[attr-defined]
        "course_id": course_id,
        "module_id": module_id,
        "unit_id": unit_id,
        "section_id": section_id,
        "task": task,
    }


@pytest.mark.anyio
async def test_worker_passes_task_context_to_feedback_adapter():
    _require_db_or_skip()
    fixture = await _prepare_learning_fixture()
    dsn = _dsn()
    worker_dsn = os.getenv("SERVICE_ROLE_DSN") or dsn

    # Reset queue
    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        cleanup_learning_jobs_for_run(conn)
        conn.commit()

    # Enqueue submission
    repo = DBLearningRepo(dsn=dsn)
    create = CreateSubmissionUseCase(repo)
    submission = create.execute(
        CreateSubmissionInput(
            course_id=fixture.course_id,
            task_id=fixture.task["id"],
            student_sub=fixture.student_sub,
            kind="text",
            text_body="Antwort",
            storage_key=None,
            mime_type=None,
            size_bytes=None,
            sha256=None,
            score_raw=None,
            score_max=None,
            idempotency_key="worker-pass-context",
        )
    )
    sub_id = submission["id"]

    assert _job_pending(worker_dsn=worker_dsn, submission_id=sub_id)

    captured_kwargs: dict | None = None
    for attempt in range(10):
        adapter = _FeedbackCapturingAdapter()
        processed = run_once(
            dsn=worker_dsn,
            vision_adapter=_Vision(text="Text"),
            feedback_adapter=adapter,
            now=datetime.now(tz=timezone.utc),
            test_run_id=current_test_run_id(),
        )
        assert processed is True
        if not _job_pending(worker_dsn=worker_dsn, submission_id=sub_id):
            captured_kwargs = adapter.last_kwargs
            break

    assert captured_kwargs is not None, "Worker did not process the targeted submission"
    assert captured_kwargs.get("instruction_md") == fixture.task.get("instruction_md")
    assert captured_kwargs.get("teacher_context_md") == fixture.task.get("teacher_context_md")


@pytest.mark.anyio
async def test_modular_submission_job_payload_includes_instruction_but_not_teacher_context():
    fixture = await _prepare_modular_learning_fixture()
    dsn = _dsn()
    worker_dsn = os.getenv("SERVICE_ROLE_DSN") or dsn

    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        cleanup_learning_jobs_for_run(conn)
        conn.commit()

    repo = DBLearningRepo(dsn=dsn)
    create = CreateSubmissionUseCase(repo)
    submission = create.execute(
        CreateSubmissionInput(
            course_id=fixture["course_id"],
            task_id=fixture["task"]["id"],
            student_sub=fixture["student_sub"],
            kind="image",
            text_body=None,
            storage_key="submissions/modular/context.png",
            mime_type="image/png",
            size_bytes=123,
            sha256="a" * 64,
            score_raw=None,
            score_max=None,
            idempotency_key="modular-payload-context",
            intent="feedback",
        )
    )

    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute(
                "select payload from public.learning_submission_jobs where submission_id = %s::uuid",
                (submission["id"],),
            )
            row = cur.fetchone()
            assert row is not None, "Job row missing"
            payload = row[0]
            if isinstance(payload, str):
                payload = json.loads(payload)

    assert payload.get("instruction_md") == fixture["task"]["instruction_md"]
    assert "teacher_context_md" not in payload


@pytest.mark.anyio
async def test_worker_passes_modular_visual_task_context_to_visual_feedback_adapter(monkeypatch: pytest.MonkeyPatch, tmp_path):
    fixture = await _prepare_modular_learning_fixture()
    dsn = _dsn()
    worker_dsn = os.getenv("SERVICE_ROLE_DSN") or dsn
    monkeypatch.setenv("SERVICE_ROLE_DSN", worker_dsn)
    monkeypatch.setenv("STORAGE_VERIFY_ROOT", str(tmp_path))

    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        cleanup_learning_jobs_for_run(conn)
        conn.commit()

    storage_key = f"submissions/{fixture['course_id']}/{fixture['task']['id']}/{fixture['student_sub']}/visual-context.png"
    target = tmp_path / storage_key
    target.parent.mkdir(parents=True, exist_ok=True)
    payload_bytes = b"\x89PNG\r\n\x1a\n" + b"z" * 64
    target.write_bytes(payload_bytes)

    repo = DBLearningRepo(dsn=dsn)
    create = CreateSubmissionUseCase(repo)
    submission = create.execute(
        CreateSubmissionInput(
            course_id=fixture["course_id"],
            task_id=fixture["task"]["id"],
            student_sub=fixture["student_sub"],
            kind="image",
            text_body=None,
            storage_key=storage_key,
            mime_type="image/png",
            size_bytes=len(payload_bytes),
            sha256="b" * 64,
            score_raw=None,
            score_max=None,
            idempotency_key="modular-visual-context",
            intent="feedback",
        )
    )

    adapter = _FeedbackCapturingAdapter()
    processed = run_once(
        dsn=worker_dsn,
        vision_adapter=_Vision(text="unused"),
        feedback_adapter=adapter,
        now=datetime.now(tz=timezone.utc),
        test_run_id=current_test_run_id(),
    )

    assert processed is True
    assert not _job_pending(worker_dsn=worker_dsn, submission_id=submission["id"])
    assert adapter.last_kwargs is not None
    assert adapter.last_kwargs.get("instruction_md") == fixture["task"]["instruction_md"]
    assert adapter.last_kwargs.get("teacher_context_md") == "Achte auf Belege aus Material M1 und M2."


def _job_pending(*, worker_dsn: str, submission_id: str) -> bool:
    """Return True when a queue entry for the submission still exists."""
    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute(
                "select 1 from public.learning_submission_jobs where submission_id = %s::uuid limit 1",
                (submission_id,),
            )
            return cur.fetchone() is not None
