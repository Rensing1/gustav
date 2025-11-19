"""
Regression tests for DSPy/Ollama host configuration.

Intent:
    Ensure that the DSPy feedback program derives `OLLAMA_HOST` from
    the mandatory `OLLAMA_BASE_URL` before instantiating `dspy.LM`. This
    mirrors the docker-compose setup where only the base URL is provided.

Why:
    LiteLLM/DSPy fall back to `http://127.0.0.1:11434` when `OLLAMA_HOST`
    is missing, which breaks inside the worker container. The worker must
    therefore propagate the host part of `OLLAMA_BASE_URL` automatically.
"""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace

import pytest


def test_feedback_program_sets_ollama_host(monkeypatch: pytest.MonkeyPatch) -> None:
    """`dspy.LM` should see OLLAMA_HOST derived from OLLAMA_BASE_URL."""
    from backend.learning.adapters.dspy import feedback_program
    from backend.learning.adapters.dspy import programs as dspy_programs

    monkeypatch.setenv("AI_FEEDBACK_MODEL", "llama3.1")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama:11434")
    monkeypatch.delenv("OLLAMA_HOST", raising=False)

    observed = {"host": None, "api_base": None}

    class _FakeLM:
        def __init__(self, model: str, **kwargs) -> None:
            observed["host"] = os.getenv("OLLAMA_HOST")
            observed["api_base"] = kwargs.get("api_base")
            self.model = model

    fake_dspy = SimpleNamespace(
        __version__="0.0-test",
        LM=_FakeLM,
        JSONAdapter=None,
        configure=lambda **kwargs: None,
    )
    monkeypatch.setitem(sys.modules, "dspy", fake_dspy)

    def _structured_analysis(**kwargs):  # type: ignore[no-untyped-def]
        return {
            "schema": "criteria.v2",
            "score": 4,
            "criteria_results": [
                {"criterion": "Inhalt", "max_score": 10, "score": 9, "explanation_md": "Analyse Inhalt"}
            ],
        }

    def _structured_feedback(**kwargs):  # type: ignore[no-untyped-def]
        return "**DSPy Feedback**\n\n- Individuell formuliert."

    monkeypatch.setattr(dspy_programs, "run_structured_analysis", _structured_analysis)
    monkeypatch.setattr(dspy_programs, "run_structured_feedback", _structured_feedback)

    result = feedback_program.analyze_feedback(text_md="# Text", criteria=["Inhalt"])
    assert result.feedback_md.startswith("**DSPy Feedback**")
    assert observed["host"] == "http://ollama:11434", "OLLAMA_HOST should mirror the base URL"
    assert observed["api_base"] == "http://ollama:11434"
    assert os.getenv("OLLAMA_API_BASE") == "http://ollama:11434"
