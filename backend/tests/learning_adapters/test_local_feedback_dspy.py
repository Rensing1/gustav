"""
Unit tests: local Feedback adapter prefers DSPy when available (no new env vars).

Intent:
    - If `dspy` can be imported, the adapter must not call the Ollama client.
    - If `dspy` is absent, the adapter falls back to Ollama and still returns
      a valid `criteria.v2` structure.

Notes:
    We simulate DSPy presence by inserting a dummy module into `sys.modules`.
    We assert the negative condition by making Ollama's `generate` raise if
    called in the DSPy-present scenario.
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


class _BombOllamaClient:
    def generate(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("ollama should not be called when dspy is importable")


def _install_bomb_ollama(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_module = SimpleNamespace(Client=lambda base_url=None: _BombOllamaClient())
    monkeypatch.setitem(sys.modules, "ollama", fake_module)


def _install_fake_dspy(monkeypatch: pytest.MonkeyPatch) -> None:
    # Minimal stand-in; adapter should only need import success, not actual API.
    fake_dspy = SimpleNamespace(__version__="0.0-test")
    monkeypatch.setitem(sys.modules, "dspy", fake_dspy)


def _uninstall_fake_dspy(monkeypatch: pytest.MonkeyPatch) -> None:
    if "dspy" in sys.modules:
        monkeypatch.delitem(sys.modules, "dspy", raising=False)


def _find_backend_marker(caplog: pytest.LogCaptureFixture, value: str) -> bool:
    """Helper to locate backend telemetry logs in the adapter output."""
    for record in caplog.records:
        message = record.getMessage()
        if "feedback_backend=" in message and f"feedback_backend={value}" in message:
            return True
    return False


def test_feedback_prefers_dspy_when_importable(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_bomb_ollama(monkeypatch)
    _install_fake_dspy(monkeypatch)

    import importlib

    monkeypatch.setenv("AI_FEEDBACK_MODEL", "llama3.1")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama:11434")

    program = importlib.import_module("backend.learning.adapters.dspy.feedback_program")

    def _stub_lm_call(*, prompt: str, timeout: int) -> str:
        return '{"schema":"criteria.v2","score":3,"criteria_results":[]}'

    monkeypatch.setattr(program, "_lm_call", _stub_lm_call)

    mod = importlib.import_module("backend.learning.adapters.local_feedback")
    adapter = mod.build()  # type: ignore[attr-defined]

    result: FeedbackResult = adapter.analyze(text_md="# Text", criteria=["Inhalt"])  # type: ignore[arg-type]
    assert isinstance(result, FeedbackResult)
    analysis = result.analysis_json
    assert analysis.get("schema") == "criteria.v2"


def test_feedback_falls_back_to_ollama_when_dspy_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    # Remove any pre-existing dspy markers
    _uninstall_fake_dspy(monkeypatch)

    # Provide a benign ollama client
    from backend.tests.learning_adapters.test_local_feedback import _install_fake_ollama  # reuse helper

    _install_fake_ollama(monkeypatch, mode="ok")

    import importlib

    mod = importlib.import_module("backend.learning.adapters.local_feedback")
    adapter = mod.build()  # type: ignore[attr-defined]

    result: FeedbackResult = adapter.analyze(text_md="# Text", criteria=["Inhalt"])  # type: ignore[arg-type]
    assert isinstance(result, FeedbackResult)
    assert result.analysis_json.get("schema") == "criteria.v2"


def test_feedback_skips_dspy_when_env_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_dspy(monkeypatch)

    from backend.tests.learning_adapters.test_local_feedback import _install_fake_ollama

    _install_fake_ollama(monkeypatch, mode="ok")

    import importlib

    program = importlib.import_module("backend.learning.adapters.dspy.feedback_program")

    def _bomb_analyze_feedback(**kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("DSPy path should not run when required env is missing")

    monkeypatch.setattr(program, "analyze_feedback", _bomb_analyze_feedback)

    monkeypatch.setenv("AI_FEEDBACK_MODEL", "")
    monkeypatch.setenv("OLLAMA_BASE_URL", "")

    mod = importlib.import_module("backend.learning.adapters.local_feedback")
    adapter = mod.build()  # type: ignore[attr-defined]

    result: FeedbackResult = adapter.analyze(text_md="# Text", criteria=["Inhalt"])  # type: ignore[arg-type]
    assert result.analysis_json.get("schema") == "criteria.v2"


def test_feedback_dspy_timeout_raises_transient(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_dspy(monkeypatch)
    _install_bomb_ollama(monkeypatch)

    import importlib

    program = importlib.import_module("backend.learning.adapters.dspy.feedback_program")

    def _timeout(**kwargs):  # type: ignore[no-untyped-def]
        raise TimeoutError("DSPy timeout")

    monkeypatch.setattr(program, "analyze_feedback", _timeout)

    monkeypatch.setenv("AI_FEEDBACK_MODEL", "llama3.1")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama:11434")

    mod = importlib.import_module("backend.learning.adapters.local_feedback")
    adapter = mod.build()  # type: ignore[attr-defined]

    with pytest.raises(FeedbackTransientError):
        adapter.analyze(text_md="# Text", criteria=["Inhalt"])  # type: ignore[arg-type]


def test_feedback_logs_backend_dspy(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    _install_fake_dspy(monkeypatch)
    _install_bomb_ollama(monkeypatch)

    import importlib

    program = importlib.import_module("backend.learning.adapters.dspy.feedback_program")

    def _stub_lm_call(*, prompt: str, timeout: int) -> str:
        return '{"schema":"criteria.v2","score":3,"criteria_results":[],"feedback_md":"**OK**"}'

    monkeypatch.setattr(program, "_lm_call", _stub_lm_call)

    monkeypatch.setenv("AI_FEEDBACK_MODEL", "llama3.1")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama:11434")

    caplog.set_level("INFO")
    mod = importlib.import_module("backend.learning.adapters.local_feedback")
    adapter = mod.build()  # type: ignore[attr-defined]

    adapter.analyze(text_md="# Text", criteria=["Inhalt"])  # type: ignore[arg-type]
    assert _find_backend_marker(caplog, "dspy"), "DSPy backend log missing"


def test_feedback_logs_backend_fallback(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    _uninstall_fake_dspy(monkeypatch)
    from backend.tests.learning_adapters.test_local_feedback import _install_fake_ollama

    _install_fake_ollama(monkeypatch, mode="ok")

    import importlib

    caplog.set_level("INFO")
    mod = importlib.import_module("backend.learning.adapters.local_feedback")
    adapter = mod.build()  # type: ignore[attr-defined]

    adapter.analyze(text_md="# Text", criteria=["Inhalt"])  # type: ignore[arg-type]
    assert _find_backend_marker(caplog, "ollama"), "Fallback backend log missing"
