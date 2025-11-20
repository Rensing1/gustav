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
import importlib
import builtins

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


def _force_dspy_import_error(monkeypatch: pytest.MonkeyPatch) -> None:
    original_import = builtins.__import__

    def _fake_import(name, *args, **kwargs):
        if name == "dspy":
            raise ImportError("dspy intentionally hidden for test")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fake_import)


def _find_backend_marker(caplog: pytest.LogCaptureFixture, value: str) -> bool:
    """Helper to locate backend telemetry logs in the adapter output."""
    for record in caplog.records:
        message = record.getMessage()
        if "feedback_backend=" in message and f"feedback_backend={value}" in message:
            return True
    return False


def _find_parse_status_marker(caplog: pytest.LogCaptureFixture, value: str) -> bool:
    for record in caplog.records:
        message = record.getMessage()
        if "parse_status=" in message and f"parse_status={value}" in message:
            return True
    return False


def test_feedback_prefers_dspy_when_importable(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_bomb_ollama(monkeypatch)
    _install_fake_dspy(monkeypatch)

    import importlib

    from backend.learning.adapters.dspy import programs as dspy_programs

    monkeypatch.setenv("AI_FEEDBACK_MODEL", "llama3.1")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama:11434")

    # Stub structured DSPy helpers to return a minimal criteria.v2 payload
    # without invoking any Ollama client.
    def _structured_analysis(**kwargs):  # type: ignore[no-untyped-def]
        return {
            "schema": "criteria.v2",
            "score": 3,
            "criteria_results": [],
        }

    def _structured_feedback(**kwargs):  # type: ignore[no-untyped-def]
        return "**OK**"

    monkeypatch.setattr(dspy_programs, "run_structured_analysis", _structured_analysis, raising=False)
    monkeypatch.setattr(dspy_programs, "run_structured_feedback", _structured_feedback, raising=False)

    mod = importlib.import_module("backend.learning.adapters.local_feedback")
    adapter = mod.build()  # type: ignore[attr-defined]

    result: FeedbackResult = adapter.analyze(text_md="# Text", criteria=["Inhalt"])  # type: ignore[arg-type]
    assert isinstance(result, FeedbackResult)
    analysis = result.analysis_json
    assert analysis.get("schema") == "criteria.v2"


def test_feedback_falls_back_to_ollama_when_dspy_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    # Remove any pre-existing dspy markers
    _uninstall_fake_dspy(monkeypatch)
    _force_dspy_import_error(monkeypatch)

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

    from backend.learning.adapters.dspy import programs as dspy_programs

    def _structured_analysis(**kwargs):  # type: ignore[no-untyped-def]
        return {
            "schema": "criteria.v2",
            "score": 3,
            "criteria_results": [],
        }

    def _structured_feedback(**kwargs):  # type: ignore[no-untyped-def]
        return "**OK**"

    monkeypatch.setattr(dspy_programs, "run_structured_analysis", _structured_analysis, raising=False)
    monkeypatch.setattr(dspy_programs, "run_structured_feedback", _structured_feedback, raising=False)

    monkeypatch.setenv("AI_FEEDBACK_MODEL", "llama3.1")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama:11434")

    caplog.set_level("INFO")
    mod = importlib.import_module("backend.learning.adapters.local_feedback")
    adapter = mod.build()  # type: ignore[attr-defined]

    adapter.analyze(text_md="# Text", criteria=["Inhalt"])  # type: ignore[arg-type]
    assert _find_backend_marker(caplog, "dspy"), "DSPy backend log missing"


def test_feedback_logs_parse_status(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    """The adapter log should mention whether DSPy parsing succeeded."""
    _install_fake_dspy(monkeypatch)
    _install_bomb_ollama(monkeypatch)

    import importlib

    monkeypatch.setenv("AI_FEEDBACK_MODEL", "llama3.1")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama:11434")

    program = importlib.import_module("backend.learning.adapters.dspy.feedback_program")

    class _StubResult:
        feedback_md = "**OK**"
        analysis_json = {"schema": "criteria.v2", "criteria_results": []}
        parse_status = "parsed"

    monkeypatch.setattr(program, "analyze_feedback", lambda **_: _StubResult())

    caplog.set_level("INFO")
    mod = importlib.import_module("backend.learning.adapters.local_feedback")
    adapter = mod.build()  # type: ignore[attr-defined]

    adapter.analyze(text_md="# Text", criteria=["Inhalt"])  # type: ignore[arg-type]
    assert _find_parse_status_marker(caplog, "parsed"), "Expected parse_status log entry"


def test_feedback_handles_none_without_ollama(monkeypatch: pytest.MonkeyPatch) -> None:
    """If DSPy returns feedback_md=None, adapter should not persist 'None' nor call Ollama."""
    # Install fake dspy presence
    from types import SimpleNamespace

    fake_dspy = SimpleNamespace(__version__="0.0-test")
    monkeypatch.setitem(sys.modules, "dspy", fake_dspy)

    # Ensure DSPy prerequisites are met so that the adapter selects
    # the DSPy pipeline and does not fall back to Ollama.
    monkeypatch.setenv("AI_FEEDBACK_MODEL", "llama3.1")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama:11434")

    # Bomb ollama: ensure no fallback is attempted
    class _BombOllamaClient:
        def generate(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            raise AssertionError("ollama should not be called when DSPy is present")

    monkeypatch.setitem(sys.modules, "ollama", SimpleNamespace(Client=lambda host=None: _BombOllamaClient()))

    import importlib

    program = importlib.import_module("backend.learning.adapters.dspy.feedback_program")

    class _Result:
        feedback_md = None
        analysis_json = {"schema": "criteria.v2", "criteria_results": [
            {"criterion": "Inhalt", "max_score": 10, "score": 7, "explanation_md": "OK"}
        ]}
        parse_status = "parsed_structured"

    # Return DSPy object with feedback_md=None
    monkeypatch.setattr(program, "analyze_feedback", lambda **_: _Result())

    mod = importlib.import_module("backend.learning.adapters.local_feedback")
    adapter = mod.build()  # type: ignore[attr-defined]

    res = adapter.analyze(text_md="# Text", criteria=["Inhalt"])  # type: ignore[arg-type]
    assert isinstance(res.feedback_md, str) and res.feedback_md.strip() and res.feedback_md.lower() != "none"
    assert res.analysis_json.get("schema") == "criteria.v2"


def test_feedback_logs_backend_fallback(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    _uninstall_fake_dspy(monkeypatch)
    _force_dspy_import_error(monkeypatch)
    from backend.tests.learning_adapters.test_local_feedback import _install_fake_ollama

    _install_fake_ollama(monkeypatch, mode="ok")

    import importlib

    caplog.set_level("INFO")
    mod = importlib.import_module("backend.learning.adapters.local_feedback")
    adapter = mod.build()  # type: ignore[attr-defined]

    adapter.analyze(text_md="# Text", criteria=["Inhalt"])  # type: ignore[arg-type]
    assert _find_backend_marker(caplog, "ollama"), "Fallback backend log missing"


def test_feedback_dspy_fallback_degrades_to_ollama(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    DSPy-Fallback-Ergebnisse müssen den Ollama-Fallback triggern,
    statt stubartige 0er-Analysen als final zu speichern.
    """

    _install_fake_dspy(monkeypatch)
    monkeypatch.setenv("AI_FEEDBACK_MODEL", "llama3.1")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama:11434")

    # Ollama-Aufruf darf stattfinden und wird aufgezeichnet.
    calls: list[dict] = []

    class _CapturingClient:
        def generate(self, model: str, prompt: str, options: dict | None = None, **_: object) -> dict:
            calls.append({"model": model, "prompt": prompt, "options": options or {}})
            return {"response": "ollama-feedback"}

    import sys
    from types import SimpleNamespace

    monkeypatch.setitem(sys.modules, "ollama", SimpleNamespace(Client=lambda base_url=None: _CapturingClient()))

    import importlib

    program = importlib.import_module("backend.learning.adapters.dspy.feedback_program")

    class _FallbackResult:
        feedback_md = "Stub aus DSPy"
        analysis_json = {"schema": "criteria.v2", "criteria_results": []}
        parse_status = "analysis_feedback_fallback"

    monkeypatch.setattr(program, "analyze_feedback", lambda **_: _FallbackResult())

    mod = importlib.import_module("backend.learning.adapters.local_feedback")
    adapter = mod.build()  # type: ignore[attr-defined]

    result: FeedbackResult = adapter.analyze(text_md="# Text", criteria=["Inhalt"])  # type: ignore[arg-type]

    assert calls, "Ollama-Fallback wurde nicht aufgerufen"
    assert result.feedback_md.strip() == "ollama-feedback"
    assert result.parse_status == "model"


def test_feedback_recovers_when_json_adapter_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Regression guard: JSONAdapter failures must not force stub feedback.

    We simulate a JSONAdapter-enabled DSPy call raising ResponseError by making
    the structured analysis/synthesis helpers explode whenever the adapter is
    instantiated. The legacy fallback runners also raise so the test only
    passes when the JSONAdapter is skipped entirely (which is the desired fix).
    """

    from types import SimpleNamespace

    # Track whether the JSONAdapter was instantiated/configured.
    adapter_usage = {"used": False}

    monkeypatch.setenv("LEARNING_DSPY_JSON_ADAPTER", "false")

    class _TrackingJSONAdapter:
        def __init__(self) -> None:
            adapter_usage["used"] = True

        def __call__(self) -> "_TrackingJSONAdapter":
            adapter_usage["used"] = True
            return self

    def _fake_configure(*, lm, adapter=None, **_kwargs):  # type: ignore[no-untyped-def]
        if adapter is not None:
            adapter_usage["used"] = True

    fake_dspy = SimpleNamespace(
        __version__="0.0-test",
        JSONAdapter=_TrackingJSONAdapter,
        LM=lambda model: SimpleNamespace(model=model),
        configure=_fake_configure,
    )
    monkeypatch.setitem(sys.modules, "dspy", fake_dspy)

    # Patching must happen after the fake module is installed.
    from backend.learning.adapters.dspy import programs as dspy_programs
    from backend.learning.adapters.dspy import feedback_program as dspy_feedback

    def _raise_when_adapter_used(**kwargs):  # type: ignore[no-untyped-def]
        if adapter_usage["used"]:
            raise RuntimeError("ResponseError from JSONAdapter")
        return {
            "schema": "criteria.v2",
            "score": 4,
            "criteria_results": [
                {"criterion": "Inhalt", "max_score": 10, "score": 9, "explanation_md": "Analyse Inhalt"}
            ],
        }

    def _structured_feedback(**kwargs):  # type: ignore[no-untyped-def]
        if adapter_usage["used"]:
            raise RuntimeError("ResponseError from JSONAdapter")
        return "**DSPy Feedback**\n\n- Individuell formuliert."

    monkeypatch.setattr(dspy_programs, "run_structured_analysis", _raise_when_adapter_used)
    monkeypatch.setattr(dspy_programs, "run_structured_feedback", _structured_feedback)

    monkeypatch.setenv("AI_FEEDBACK_MODEL", "llama3.1")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama:11434")

    mod = importlib.import_module("backend.learning.adapters.local_feedback")
    adapter = mod.build()  # type: ignore[attr-defined]

    result: FeedbackResult = adapter.analyze(text_md="# Text", criteria=["Inhalt"])  # type: ignore[arg-type]
    assert result.feedback_md == "**DSPy Feedback**\n\n- Individuell formuliert."
    assert "Stärken: klar" not in result.feedback_md


def test_local_feedback_uses_dspy_without_direct_ollama_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    DSPy-only guard: local adapter must not call ollama directly
    when the DSPy feedback program is available and succeeds.

    Intent:
        - Encode the design decision that the feedback pipeline is
          orchestrated exclusively through DSPy when present.
        - Any attempt to call `ollama.Client.generate` in this scenario
          should fail the test.
    """

    _install_fake_dspy(monkeypatch)

    # Bomb ollama: any direct usage from the adapter must fail this test.
    _install_bomb_ollama(monkeypatch)

    import importlib

    program = importlib.import_module("backend.learning.adapters.dspy.feedback_program")

    class _StubResult:
        feedback_md = "DSPy Feedback"
        analysis_json = {"schema": "criteria.v2", "criteria_results": []}
        parse_status = "parsed_structured"

    monkeypatch.setattr(program, "analyze_feedback", lambda **_: _StubResult())

    monkeypatch.setenv("AI_FEEDBACK_MODEL", "llama3.1")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama:11434")

    mod = importlib.import_module("backend.learning.adapters.local_feedback")
    adapter = mod.build()  # type: ignore[attr-defined]

    result: FeedbackResult = adapter.analyze(text_md="# Text", criteria=["Inhalt"])  # type: ignore[arg-type]
    assert isinstance(result, FeedbackResult)
    assert result.analysis_json.get("schema") == "criteria.v2"
    assert result.feedback_md == "DSPy Feedback"
