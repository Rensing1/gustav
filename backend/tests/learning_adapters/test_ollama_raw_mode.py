"""
Regression test: Ollama fallback must enforce raw mode and bypass server templates.

Intent:
    Guard against regressions where the local feedback adapter would allow
    server-side templates (which can fail on missing functions) or omit the
    `raw` flag. This keeps behavior deterministic and mirrors earlier fixes.
"""

from __future__ import annotations

import importlib
import sys
from types import SimpleNamespace

import pytest

pytest.importorskip("psycopg")


def _install_capturing_ollama(monkeypatch: pytest.MonkeyPatch, calls: list) -> None:
    class _Client:
        def generate(self, model: str, prompt: str, options: dict | None = None, **_: object) -> dict:
            calls.append({"model": model, "prompt": prompt, "options": options or {}})
            return {"response": "feedback"}

    monkeypatch.setitem(sys.modules, "ollama", SimpleNamespace(Client=lambda base_url=None: _Client()))


def test_local_feedback_fallback_uses_raw_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    # Force DSPy path to be skipped (missing model env)
    monkeypatch.delenv("AI_FEEDBACK_MODEL", raising=False)
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama:11434")

    calls: list = []
    _install_capturing_ollama(monkeypatch, calls)

    mod = importlib.import_module("backend.learning.adapters.local_feedback")
    adapter = mod.build()  # type: ignore[attr-defined]

    result = adapter.analyze(text_md="# Text", criteria=["Inhalt"])  # type: ignore[arg-type]
    assert result.feedback_md.strip()

    assert len(calls) == 1, "Expected exactly one Ollama generate call"
    opts = calls[0]["options"]
    assert opts.get("raw") is True
    assert opts.get("template") == "{{ .Prompt }}"
