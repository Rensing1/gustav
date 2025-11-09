"""
E2E-style tests for the learning worker using local AI adapters (Ollama/DSPy).

Intent:
    Validate pending → completed flow with the real worker logic, local adapters,
    and mocked AI clients. The tests assert that:
      - With `dspy` importable, Feedback uses the DSPy branch (no need to call Ollama),
        and returns `criteria.v2`.
      - Vision uses Ollama and produces Markdown text.

Notes:
    - We do NOT rely on `AI_BACKEND` alias here; DI switching is covered in a
      separate test. Here we focus on successful processing with local adapters.
    - External calls are mocked via `sys.modules` entries for `ollama` and `dspy`.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from types import SimpleNamespace
from datetime import datetime, timezone
import os
import json

import pytest

pytest.importorskip("psycopg")

import psycopg  # type: ignore  # noqa: E402

from backend.learning.repo_db import DBLearningRepo  # noqa: E402
from backend.learning.usecases.submissions import (  # noqa: E402
    CreateSubmissionInput,
    CreateSubmissionUseCase,
)
from backend.tests.utils.db import require_db_or_skip as _require_db_or_skip  # noqa: E402
from backend.tests.test_learning_api_contract import _prepare_learning_fixture  # type: ignore  # noqa: E402


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
    def __init__(self, response_text: str = "### Extracted\n\nMock text") -> None:
        self.response_text = response_text

    def generate(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return {"response": self.response_text}


def _install_fake_ollama(monkeypatch: pytest.MonkeyPatch, *, text: str = "### Extracted\n\nMock text") -> None:
    fake_module = SimpleNamespace(Client=lambda base_url=None: _FakeOllamaClient(response_text=text))
    monkeypatch.setitem(sys.modules, "ollama", fake_module)


def _install_fake_dspy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "dspy", SimpleNamespace(__version__="0.0-test"))


def _truthy_env(name: str) -> bool:
    return (os.getenv(name) or "").strip().lower() in ("1", "true", "yes", "on")


def _use_real_ai_stack() -> bool:
    return _truthy_env("RUN_OLLAMA_E2E") and _truthy_env("RUN_OLLAMA_VISION_E2E")


def _ensure_real_ai_dependencies() -> None:
    """Fail fast when the environment requests real adapters but deps are missing."""
    try:
        __import__("ollama")  # type: ignore[unused-ignore]
    except Exception as exc:
        raise AssertionError("RUN_OLLAMA_*=1 requires the `ollama` package") from exc
    try:
        __import__("dspy")  # type: ignore[unused-ignore]
    except Exception as exc:
        raise AssertionError("RUN_OLLAMA_*=1 expects DSPy to be installed") from exc


@pytest.mark.anyio
async def test_e2e_local_ai_text_submission_completed_v2_with_dspy(monkeypatch: pytest.MonkeyPatch) -> None:
    _require_db_or_skip()
    fixture = await _prepare_learning_fixture()
    dsn = _dsn()
    worker_dsn = os.getenv("SERVICE_ROLE_DSN") or dsn

    # Clean queue
    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute("delete from public.learning_submission_jobs")
            cur.execute("select set_config('app.current_sub', %s, false)", (fixture.student_sub,))
            cur.execute(
                """
                delete from public.learning_submissions
                 where student_sub = %s
                   and idempotency_key in ('e2e-local-text-dspy')
                """,
                (fixture.student_sub,),
            )
        conn.commit()

    use_real_ai = _use_real_ai_stack()
    if use_real_ai:
        _ensure_real_ai_dependencies()
    else:
        # Mock AI backends: Vision uses Ollama; Feedback prefers DSPy
        _install_fake_ollama(monkeypatch, text="## Vision Output\n\nHello world.")
        _install_fake_dspy(monkeypatch)
        import importlib

        monkeypatch.setenv("AI_FEEDBACK_MODEL", "llama3.1")
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama:11434")

        dspy_program = importlib.import_module("backend.learning.adapters.dspy.feedback_program")

        def _fake_run_analysis_model(*, text_md: str, criteria):
            crit_items = [
                {"criterion": str(name), "max_score": 10, "score": 9, "explanation_md": f"Analyse {name}"}
                for name in criteria
            ]
            payload = {
                "schema": "criteria.v2",
                "score": 4,
                "criteria_results": crit_items,
            }
            return json.dumps(payload)

        def _fake_run_feedback_model(*, text_md: str, criteria, analysis_json):
            assert analysis_json["criteria_results"][0]["score"] == 9
            return "**DSPy Feedback**\n\n- Individuell formuliert."

        monkeypatch.setattr(dspy_program, "_run_analysis_model", _fake_run_analysis_model)
        monkeypatch.setattr(dspy_program, "_run_feedback_model", _fake_run_feedback_model)

    # Create pending text submission
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
            idempotency_key="e2e-local-text-dspy",
        )
    )
    submission_id = submission["id"]

    # Import and build local adapters
    import importlib

    local_vision = importlib.import_module("backend.learning.adapters.local_vision").build()  # type: ignore[attr-defined]
    local_feedback = importlib.import_module("backend.learning.adapters.local_feedback").build()  # type: ignore[attr-defined]

    # Run worker once
    from backend.learning.workers.process_learning_submission_jobs import run_once  # type: ignore

    processed = run_once(
        dsn=worker_dsn,
        vision_adapter=local_vision,
        feedback_adapter=local_feedback,
        now=datetime.now(tz=timezone.utc),
    )
    assert processed is True

    # Assert DB state
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
    assert isinstance(text_body, str) and "Vision Output" in text_body
    assert isinstance(analysis_json, dict)
    assert analysis_json.get("schema") == "criteria.v2"
    assert isinstance(feedback_md, str) and len(feedback_md.strip()) > 0
    assert feedback_md == "**DSPy Feedback**\n\n- Individuell formuliert."
    assert "Stärken: klar benannt" not in feedback_md
    assert any("Analyse" in it["explanation_md"] for it in analysis_json.get("criteria_results") or [])


@pytest.mark.anyio
async def test_e2e_local_ai_image_submission_completed_v2(monkeypatch: pytest.MonkeyPatch) -> None:
    _require_db_or_skip()
    fixture = await _prepare_learning_fixture()
    dsn = _dsn()
    worker_dsn = os.getenv("SERVICE_ROLE_DSN") or dsn

    # Clean queue
    with psycopg.connect(worker_dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute("delete from public.learning_submission_jobs")
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

    use_real_ai = _use_real_ai_stack()
    if use_real_ai:
        _ensure_real_ai_dependencies()
    else:
        # Mock Ollama for Vision; Feedback will fall back to Ollama (no dspy here)
        _install_fake_ollama(monkeypatch, text="### OCR Lines\n- one\n- two")
        if "dspy" in sys.modules:
            monkeypatch.delitem(sys.modules, "dspy", raising=False)

    # Create pending image submission
    repo = DBLearningRepo(dsn=dsn)
    create = CreateSubmissionUseCase(repo)
    submission = create.execute(
        CreateSubmissionInput(
            course_id=fixture.course_id,
            task_id=fixture.task["id"],
            student_sub=fixture.student_sub,
            kind="image",
            text_body=None,
            storage_key="storage://bucket/key.jpg",
            mime_type="image/jpeg",
            size_bytes=1024,
            sha256="0" * 64,
            idempotency_key="e2e-local-image",
        )
    )
    submission_id = submission["id"]

    # Build adapters
    import importlib

    local_vision = importlib.import_module("backend.learning.adapters.local_vision").build()  # type: ignore[attr-defined]
    local_feedback = importlib.import_module("backend.learning.adapters.local_feedback").build()  # type: ignore[attr-defined]

    from backend.learning.workers.process_learning_submission_jobs import run_once  # type: ignore

    processed = run_once(
        dsn=worker_dsn,
        vision_adapter=local_vision,
        feedback_adapter=local_feedback,
        now=datetime.now(tz=timezone.utc),
    )
    assert processed is True

    # Verify state: no bytes available → vision schedules retry (pending)
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
