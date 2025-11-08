"""
Text pass-through tests for the local Vision adapter.

Why:
    Ensure that pure text submissions do not require the Ollama client and
    are passed through as Markdown to the Feedback step. This fixes the UX
    issue where an unhelpful error text was shown instead of the student's
    submission.
"""

from __future__ import annotations

import importlib
import sys

import pytest

pytest.importorskip("psycopg")

from backend.learning.workers.process_learning_submission_jobs import VisionResult  # type: ignore


def test_text_passthrough_no_ollama_import(monkeypatch: pytest.MonkeyPatch) -> None:
    # Ensure that even if `ollama` is not importable, text flow still works.
    monkeypatch.delitem(sys.modules, "ollama", raising=False)

    mod = importlib.import_module("backend.learning.adapters.local_vision")
    adapter = mod.build()  # type: ignore[attr-defined]

    submission = {
        "id": "deadbeef-dead-beef-dead-beef200001",
        "kind": "text",
        "text_body": "# Meine Lösung\n\nDie Höhe wird aus dem EVS abgeleitet.",
    }
    job_payload = {"mime_type": None}

    res: VisionResult = adapter.extract(submission=submission, job_payload=job_payload)
    assert isinstance(res, VisionResult)
    assert "Meine Lösung" in res.text_md
    assert res.raw_metadata.get("backend") == "pass_through"

