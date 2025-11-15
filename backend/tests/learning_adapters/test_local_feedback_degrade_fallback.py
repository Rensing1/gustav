"""
Degrade-to-Ollama tests when DSPy returns fallback/empty results.

Intent:
    Ensure the local feedback adapter detects DSPy fallback signals
    (e.g., parse_status=analysis_fallback or empty/stub feedback) and
    proactively switches to the direct Ollama path to obtain a non‑stub
    feedback string. This guards the regression where the user only sees
    stub feedback despite a reachable model.
"""

from __future__ import annotations

import importlib
import sys
from types import SimpleNamespace

import pytest

from backend.learning.adapters.ports import FeedbackResult


class _FakeOllamaClient:
    def generate(self, model: str, prompt: str, options: dict | None = None, **_: object) -> dict:  # noqa: D401
        # Return a clear non‑stub response so the test can assert it was used.
        return {"response": "### Model feedback\n\nThis is real model output."}


def _install_fake_ollama(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_module = SimpleNamespace(Client=lambda host=None: _FakeOllamaClient())
    monkeypatch.setitem(sys.modules, "ollama", fake_module)


def test_degrade_to_ollama_on_dspy_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Adapter should call Ollama when DSPy signals analysis fallback."""
    # Make dspy importable
    fake_dspy = SimpleNamespace(__version__="0.0-test")
    monkeypatch.setitem(sys.modules, "dspy", fake_dspy)

    # Install fake Ollama client
    _install_fake_ollama(monkeypatch)

    # Prepare a DSPy program result that looks like a fallback (empty feedback)
    fallback_result = FeedbackResult(
        feedback_md="",  # forces degrade
        analysis_json={"schema": "criteria.v2", "score": 0, "criteria_results": []},
        parse_status="analysis_fallback",
    )

    program = importlib.import_module("backend.learning.adapters.dspy.feedback_program")
    monkeypatch.setattr(program, "analyze_feedback", lambda **_: fallback_result)

    mod = importlib.import_module("backend.learning.adapters.local_feedback")
    adapter = mod.build()  # type: ignore[attr-defined]

    res = adapter.analyze(text_md="# Text", criteria=["Inhalt"])  # type: ignore[arg-type]
    assert isinstance(res, FeedbackResult)
    assert res.analysis_json.get("schema") == "criteria.v2"
    assert res.feedback_md.startswith("### Model feedback"), "expected Ollama fallback output"
    assert res.parse_status == "model"

