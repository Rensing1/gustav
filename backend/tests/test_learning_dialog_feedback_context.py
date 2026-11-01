"""Exercise dialog context privacy from the real API/DB through the worker to DSPy."""

import os
from datetime import datetime, timezone
from types import SimpleNamespace

import psycopg
import pytest

from backend.learning.adapters import local_feedback
from backend.learning.adapters.dspy import dialog_assessment_program
from backend.learning.repo_db import DBLearningRepo
from backend.learning.usecases.dialogs import DialogUseCases
from backend.learning.workers import process_learning_submission_jobs as worker
from backend.tests.test_learning_api_contract import _client, _prepare_learning_fixture, main
from backend.tests.test_teaching_dialog_task_service import VALID_DIALOG
from backend.tests.utils.db_isolation import cleanup_learning_jobs_for_run
from backend.web.learning_dialog_providers import LearningDialogProviders

pytestmark = pytest.mark.db_write


@pytest.mark.anyio
@pytest.mark.parametrize("criteria", [[], ["Begründen"]])
async def test_dialog_context_reaches_model_but_not_learner_or_queue(monkeypatch, criteria):
    fixture = await _prepare_learning_fixture(monkeypatch)
    context = "Interner Qualitätsanker: mehrere schlüssige Positionen sind zulässig."
    feedback = "Sie begründen Ihre Position nachvollziehbar."
    calls = []

    def predict(signature):
        assert signature is dialog_assessment_program.DialogAssessmentSignature

        def run(**kwargs):
            calls.append(kwargs)
            return SimpleNamespace(
                criteria_results=[{"score": 10, "explanation_md": feedback} for _ in criteria],
                feedback_md=feedback,
            )

        return run

    generator = SimpleNamespace(partner_reply=lambda **kwargs: {"message": "Welcher Beleg trägt Ihre Position?", "starters": []})
    # Other wiring tests reload main; use the same current app as the API client.
    monkeypatch.setattr(main.app.state, "learning_dialog_providers", LearningDialogProviders(
        usecases=lambda: DialogUseCases(DBLearningRepo(), generator),
    ))
    monkeypatch.setattr(dialog_assessment_program.dspy, "Predict", predict)
    adapter = local_feedback._LocalFeedbackAdapter()
    monkeypatch.setattr(adapter, "_get_text_analysis_lm", lambda: None)
    monkeypatch.setattr(local_feedback, "capture_dspy_usage", lambda operation, **kwargs: (operation(), []))

    async with await _client() as client:
        client.cookies.set("gustav_session", fixture.teacher_session_id)
        created = await client.post(
            f"/api/teaching/units/{fixture.unit_id}/sections/{fixture.section_id}/tasks",
            json={"instruction_md": "Begründen Sie Ihre Position.", "criteria": criteria,
                  "teacher_context_md": context, "dialog": {**VALID_DIALOG, "response_mode": "free_text"}},
        )
        assert created.status_code == 201, created.text
        task_id = created.json()["id"]
        base = f"/api/learning/courses/{fixture.course_id}/tasks/{task_id}"
        client.cookies.set("gustav_session", fixture.student_session_id)
        started = await client.post(f"{base}/dialog-sessions")
        assert started.status_code == 201, started.text
        session_id = started.json()["id"]
        session_url = f"{base}/dialog-sessions/{session_id}"
        turn = await client.post(
            f"{session_url}/turns", headers={"Idempotency-Key": "context-turn"},
            json={"student_message_md": "Meine Position folgt aus dem Beleg."},
        )
        assert turn.status_code == 200, turn.text
        completed = await client.post(
            f"{session_url}/complete", headers={"Idempotency-Key": "context-complete"},
            json={"closing_answer_md": "Der Beleg stützt meine Position."},
        )
        assert completed.status_code == 200, completed.text
        submission_id = completed.json()["submission"]["id"]

        for response in (started, turn, completed, await client.get(session_url)):
            assert "teacher_context_md" not in response.text
            assert context not in response.text
        sections = await client.get(f"/api/learning/courses/{fixture.course_id}/sections?include=materials,tasks")
        assert sections.status_code == 200, sections.text
        assert context not in sections.text
        assert "teacher_context_md" not in sections.text

        dsn = os.environ["SERVICE_ROLE_DSN"]
        try:
            with psycopg.connect(dsn, row_factory=psycopg.rows.dict_row) as conn:
                with conn.cursor() as cur:
                    cur.execute("select id::text, payload from public.learning_submission_jobs where submission_id=%s::uuid", (submission_id,))
                    row = cur.fetchone()
                    job_id, payload = row["id"], row["payload"]
                assert "teacher_context_md" not in payload
                assert context not in str(payload)
                worker._process_job(
                    conn=conn,
                    job=worker.QueuedJob(id=job_id, submission_id=submission_id, retry_count=0, payload=payload),
                    vision_adapter=SimpleNamespace(), feedback_adapter=adapter, now=datetime.now(timezone.utc),
                )
            assert len(calls) == 1
            assert calls[0]["teacher_context_md"] == context
            assert calls[0]["student_performance"]["closing_answer_md"] == "Der Beleg stützt meine Position."
            assert calls[0]["conversation_context"]["assistant_messages"] == ["Welcher Beleg trägt Ihre Position?"]
            response = await client.get(f"{base}/submissions?limit=10&offset=0")
            assert response.status_code == 200, response.text
            submission = next(item for item in response.json() if item["id"] == submission_id)
            assert submission["analysis_status"] == "completed"
            assert submission["feedback_md"] == feedback
            analysis = submission["analysis_json"] or {}
            assert len(analysis.get("criteria_results", [])) == len(criteria)
            if not criteria:
                assert "score" not in analysis
            assert context not in response.text
            assert "teacher_context_md" not in response.text
        finally:
            with psycopg.connect(dsn) as conn:
                cleanup_learning_jobs_for_run(conn)
