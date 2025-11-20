"""
Unit tests for the local Feedback adapter (DSPy/Ollama-backed).

Intent:
    Drive a minimal implementation via TDD:
      - Happy path returns feedback Markdown and a `criteria.v2` report.
      - Ensures score ranges are enforced (overall 0..5, per-criterion 0..10).
      - Timeouts are classified as transient errors.

Notes:
    We mock the `ollama` client. The adapter should not leak PII into logs.
"""

from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

pytest.importorskip("psycopg")

from backend.learning.workers.process_learning_submission_jobs import (  # type: ignore
    FeedbackResult,
    FeedbackTransientError,
)


class _FakeOllamaClient:
    def __init__(self, *, mode: str = "ok"):
        self.mode = mode

    def generate(self, model: str, prompt: str, options: dict | None = None, **_: object) -> dict:
        if self.mode == "timeout":
            raise TimeoutError("simulated timeout")
        return {"response": "### Feedback\n\n- Strong points; areas to improve."}


def _install_fake_ollama(monkeypatch: pytest.MonkeyPatch, *, mode: str = "ok") -> None:
    fake_module = SimpleNamespace(Client=lambda base_url=None: _FakeOllamaClient(mode=mode))
    monkeypatch.setitem(sys.modules, "ollama", fake_module)


def test_local_feedback_happy_path_criteria_v1(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_ollama(monkeypatch, mode="ok")

    import importlib

    mod = importlib.import_module("backend.learning.adapters.local_feedback")
    adapter = mod.build()  # type: ignore[attr-defined]

    text_md = "# Student Answer\n\nSome content."
    criteria = ["Inhalt", "Struktur", "Sprache"]

    result: FeedbackResult = adapter.analyze(text_md=text_md, criteria=criteria)
    assert isinstance(result, FeedbackResult)
    assert isinstance(result.feedback_md, str) and len(result.feedback_md.strip()) > 0

    analysis = result.analysis_json
    assert isinstance(analysis, dict)
    assert analysis.get("schema") == "criteria.v2"
    assert 0 <= analysis.get("score", -1) <= 5

    crit = analysis.get("criteria_results") or []
    assert isinstance(crit, list)
    assert len(crit) == len(criteria)
    for item in crit:
        # v2: ensure criterion present
        assert isinstance(item.get("criterion", ""), str) and item.get("criterion")
        max_score = int(item.get("max_score", 10))
        assert max_score >= 1
        score = int(item.get("score", 0))
        assert 0 <= score <= max_score
        assert isinstance(item.get("explanation_md", ""), str)


def test_local_feedback_timeout_is_transient(monkeypatch: pytest.MonkeyPatch) -> None:
    # Ensure DSPy path is disabled so the Ollama fallback runs.
    monkeypatch.delenv("AI_FEEDBACK_MODEL", raising=False)
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    _install_fake_ollama(monkeypatch, mode="timeout")

    import importlib

    mod = importlib.import_module("backend.learning.adapters.local_feedback")
    adapter = mod.build()  # type: ignore[attr-defined]

    with pytest.raises(FeedbackTransientError):
        adapter.analyze(text_md="# Answer", criteria=["Inhalt"])  # type: ignore[arg-type]
