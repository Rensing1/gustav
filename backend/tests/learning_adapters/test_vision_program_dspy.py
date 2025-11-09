"""
Unit tests for the DSPy vision program.

Covers:
- ImportError when `dspy` is not importable.
- With fake DSPy: returns Markdown that includes kind, MIME and source; returns meta
  indicating it used the DSPy path. We require a `meta['program']` marker
  ("dspy_vision") to make the contract explicit.
- MIME fallback: if job payload lacks `mime_type`, it falls back to submission.
"""

from __future__ import annotations

import sys
from types import SimpleNamespace
import builtins

import pytest


def _install_fake_dspy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "dspy", SimpleNamespace(__version__="0.0-test"))


def _uninstall_fake_dspy(monkeypatch: pytest.MonkeyPatch) -> None:
    if "dspy" in sys.modules:
        monkeypatch.delitem(sys.modules, "dspy", raising=False)


def test_vision_program_raises_when_dspy_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    _uninstall_fake_dspy(monkeypatch)
    from importlib import import_module

    original_import = builtins.__import__

    def _fake_import(name, *args, **kwargs):
        if name == "dspy":
            raise ImportError("dspy intentionally hidden for test")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fake_import)

    prog = import_module("backend.learning.adapters.dspy.vision_program")
    with pytest.raises(ImportError):
        prog.extract_text(submission={"kind": "image"}, job_payload={"mime_type": "image/jpeg"})


def test_vision_program_returns_markdown_and_meta(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_dspy(monkeypatch)
    from importlib import import_module

    prog = import_module("backend.learning.adapters.dspy.vision_program")
    text_md, meta = prog.extract_text(
        submission={"kind": "image"}, job_payload={"mime_type": "image/png", "storage_key": "storage://b/k.png"}
    )
    assert text_md.startswith("### DSPy Vision")
    assert "Kind: image; MIME: image/png" in text_md
    assert "Quelle: storage://b/k.png" in text_md
    assert meta.get("backend") == "dspy"
    assert meta.get("adapter") == "local_vision"
    # Contract: mark program explicitly (should fail until implemented)
    assert meta.get("program") == "dspy_vision"


def test_vision_program_mime_fallback_to_submission(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_dspy(monkeypatch)
    from importlib import import_module

    prog = import_module("backend.learning.adapters.dspy.vision_program")
    text_md, _ = prog.extract_text(
        submission={"kind": "file", "mime_type": "application/pdf"}, job_payload={"storage_key": "s://doc.pdf"}
    )
    assert "MIME: application/pdf" in text_md
