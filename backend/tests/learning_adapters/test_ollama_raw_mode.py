"""
Assert adapters and DSPy program call Ollama with raw=True and without invalid
server options like "timeout".

Motivation:
    The Ollama server rejects unknown options (logs: invalid option provided option=timeout)
    and some model templates may error (e.g., function "currentDate" not defined).
    Using raw=True bypasses server-side templates and keeps prompts fully under
    our control.
"""

from __future__ import annotations

import importlib
import os
import sys
from types import SimpleNamespace

import pytest


def test_local_feedback_uses_raw_option(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"options": None}

    class _CapturingClient:
        def generate(self, *, model: str, prompt: str, options: dict | None = None, **_: object):  # type: ignore[no-untyped-def]
            calls["options"] = dict(options or {})
            return {"response": "OK"}

    fake_module = SimpleNamespace(Client=lambda host=None: _CapturingClient())
    monkeypatch.setitem(sys.modules, "ollama", fake_module)

    mod = importlib.import_module("backend.learning.adapters.local_feedback")
    adapter = mod.build()  # type: ignore[attr-defined]

    adapter.analyze(text_md="# Text", criteria=["Inhalt"])  # type: ignore[arg-type]

    opts = calls["options"] or {}
    assert "timeout" not in opts
    assert opts.get("raw") is True
    assert opts.get("template") == "{{ .Prompt }}"


def test_dspy_feedback_program_uses_raw_option(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"options": None}

    class _CapturingClient:
        def generate(self, *, model: str, prompt: str, options: dict | None = None, **_: object):  # type: ignore[no-untyped-def]
            calls["options"] = dict(options or {})
            return {"response": "{}"}

    fake_module = SimpleNamespace(Client=lambda host=None: _CapturingClient())
    monkeypatch.setitem(sys.modules, "ollama", fake_module)

    # Ensure required env so _lm_call doesn't raise
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama:11434")
    monkeypatch.setenv("AI_FEEDBACK_MODEL", "llama3.1")

    program = importlib.import_module("backend.learning.adapters.dspy.feedback_program")
    program._lm_call(prompt="hi", timeout=5)  # type: ignore[attr-defined]

    opts = calls["options"] or {}
    assert "timeout" not in opts
    assert opts.get("raw") is True
    assert opts.get("template") == "{{ .Prompt }}"
