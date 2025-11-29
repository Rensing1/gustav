"""
Tests for GPT-OSS think-level handling (DSPy + Ollama).

Intent:
    - For GPT-OSS models, we must send `think="low"` (configurable) to avoid
      long reasoning traces.
    - Non-GPT-OSS models must remain unchanged.

Scope:
    - DSPy LM kwargs builder.
    - DSPy feedback program uses the kwargs.
    - Ollama fallback sends top-level `think` only for GPT-OSS.
"""

from __future__ import annotations

import builtins
import importlib
import sys
from types import SimpleNamespace

import pytest


def test_build_lm_kwargs_adds_think_for_gpt_oss() -> None:
    from backend.learning.adapters.dspy import helpers as lm_helpers

    kwargs = lm_helpers.build_lm_kwargs(
        model_name="gpt-oss-mini",
        api_base="http://ollama:11434",
        think_level=None,  # default to low
    )

    assert kwargs.get("api_base") == "http://ollama:11434"
    assert kwargs.get("extra_body", {}).get("think") == "low"


def test_build_lm_kwargs_skips_think_for_other_models() -> None:
    from backend.learning.adapters.dspy import helpers as lm_helpers

    kwargs = lm_helpers.build_lm_kwargs(
        model_name="llama3.1",
        api_base=None,
        think_level="medium",
    )

    assert "extra_body" not in kwargs
    assert kwargs == {}


def test_feedback_program_sets_think_for_gpt_oss(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Ensure DSPy feedback program builds the LM with think="low" for GPT-OSS.
    """
    from backend.learning.adapters.dspy import feedback_program
    from backend.learning.adapters.dspy import programs as dspy_programs

    monkeypatch.setenv("AI_FEEDBACK_MODEL", "gpt-oss-mini")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama:11434")
    monkeypatch.delenv("AI_THINK_LEVEL", raising=False)

    observed: dict = {}

    class _FakeLM:
        def __init__(self, model: str, **kwargs) -> None:
            observed["model"] = model
            observed["kwargs"] = kwargs

    fake_dspy = SimpleNamespace(
        __version__="0.0-test",
        LM=_FakeLM,
        JSONAdapter=None,
        configure=lambda **kwargs: observed.setdefault("configured", kwargs),
    )
    monkeypatch.setitem(sys.modules, "dspy", fake_dspy)

    def _structured_analysis(**kwargs):  # type: ignore[no-untyped-def]
        return feedback_program.CriteriaAnalysis(
            schema="criteria.v2",
            score=0,
            criteria_results=[],
        )

    def _structured_feedback(**kwargs):  # type: ignore[no-untyped-def]
        return "**ok**"

    monkeypatch.setattr(dspy_programs, "run_structured_analysis", _structured_analysis)
    monkeypatch.setattr(dspy_programs, "run_structured_feedback", _structured_feedback)

    result = feedback_program.analyze_feedback(text_md="# t", criteria=["Inhalt"])
    assert result.feedback_md.startswith("**ok**")

    assert observed["model"].endswith("gpt-oss-mini")
    assert observed["kwargs"]["extra_body"]["think"] == "low"
    assert observed["kwargs"]["api_base"] == "http://ollama:11434"


def test_local_feedback_ollama_sends_think_for_gpt_oss(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fallback Ollama call must include top-level think only for GPT-OSS."""

    called: dict = {}

    class _CapturingClient:
        def generate(self, model: str, prompt: str, options=None, **kwargs):  # type: ignore[no-untyped-def]
            called["model"] = model
            called["think"] = kwargs.get("think")
            called["options"] = options or {}
            return {"response": "ok"}

    fake_module = SimpleNamespace(Client=lambda base_url=None: _CapturingClient())
    monkeypatch.setitem(sys.modules, "ollama", fake_module)

    original_import = builtins.__import__

    def _fake_import(name, *args, **kwargs):
        if name == "dspy":
            raise ImportError("hide dspy to force fallback")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fake_import)

    monkeypatch.setenv("AI_FEEDBACK_MODEL", "gpt-oss-mini")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama:11434")
    monkeypatch.delenv("AI_THINK_LEVEL", raising=False)

    mod = importlib.reload(importlib.import_module("backend.learning.adapters.local_feedback"))
    adapter = mod.build()  # type: ignore[attr-defined]

    result = adapter.analyze(text_md="# answer", criteria=["Inhalt"])  # type: ignore[arg-type]
    assert result.feedback_md

    assert called["model"].startswith("gpt-oss")
    assert called["think"] == "low"
    assert called["options"].get("raw") is True


def test_local_feedback_ollama_skips_think_for_other_models(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-GPT-OSS models must not receive a think flag."""
    called: dict = {}

    class _CapturingClient:
        def generate(self, model: str, prompt: str, options=None, **kwargs):  # type: ignore[no-untyped-def]
            called["model"] = model
            called["think"] = kwargs.get("think")
            called["options"] = options or {}
            return {"response": "ok"}

    fake_module = SimpleNamespace(Client=lambda base_url=None: _CapturingClient())
    monkeypatch.setitem(sys.modules, "ollama", fake_module)

    original_import = builtins.__import__

    def _fake_import(name, *args, **kwargs):
        if name == "dspy":
            raise ImportError("hide dspy to force fallback")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fake_import)

    monkeypatch.setenv("AI_FEEDBACK_MODEL", "llama3.1")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama:11434")

    mod = importlib.reload(importlib.import_module("backend.learning.adapters.local_feedback"))
    adapter = mod.build()  # type: ignore[attr-defined]

    result = adapter.analyze(text_md="# answer", criteria=["Inhalt"])  # type: ignore[arg-type]
    assert result.feedback_md

    assert called["model"] == "llama3.1"
    assert called["think"] is None
    assert called["options"].get("raw") is True
