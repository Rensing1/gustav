"""
Unit tests for the DSPy vision program.

Covers:
- ImportError when `dspy` is not importable.
- With fake DSPy: `extract_text_from_image(...)` calls `dspy.Predict(...)` with a
  `dspy.Image(url=...)` and returns `(text_md, meta)` with an explicit `program`
  marker.
- Fail-fast: missing/empty `text_md` raises.
"""

from __future__ import annotations

import sys
from types import SimpleNamespace
import builtins

import pytest


class _FakeImage:
    def __init__(self, *, url: str):
        self.url = url


class _FakePredict:
    seen_signature = None
    calls: list[dict] = []

    def __init__(self, signature):  # noqa: ANN001
        type(self).seen_signature = signature

    def __call__(self, **kwargs):  # noqa: ANN003
        type(self).calls.append(kwargs)
        return SimpleNamespace(text_md="Erkannter Text")


def _install_fake_dspy(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = SimpleNamespace(
        __version__="0.0-test",
        Signature=object,
        InputField=lambda **_: None,
        OutputField=lambda **_: None,
        Image=_FakeImage,
        Predict=_FakePredict,
    )
    monkeypatch.setitem(sys.modules, "dspy", fake)


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
        prog.extract_text_from_image(image_data_uri="data:image/png;base64,AA==")


def test_vision_program_returns_markdown_and_meta(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_dspy(monkeypatch)
    from importlib import import_module

    prog = import_module("backend.learning.adapters.dspy.vision_program")
    _FakePredict.calls = []
    text_md, meta = prog.extract_text_from_image(image_data_uri="data:image/png;base64,AA==")
    assert text_md == "Erkannter Text"
    assert meta.get("backend") == "dspy"
    assert meta.get("program") == "vision_ocr"
    assert _FakePredict.calls
    image = _FakePredict.calls[0].get("student_image")
    assert isinstance(image, _FakeImage)
    assert image.url == "data:image/png;base64,AA=="


def test_vision_program_empty_text_is_fail_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_dspy(monkeypatch)
    from importlib import import_module

    class _EmptyPredict(_FakePredict):
        def __call__(self, **kwargs):  # noqa: ANN003
            type(self).calls.append(kwargs)
            return SimpleNamespace(text_md="  ")

    sys.modules["dspy"].Predict = _EmptyPredict  # type: ignore[attr-defined]
    prog = import_module("backend.learning.adapters.dspy.vision_program")
    with pytest.raises(RuntimeError):
        prog.extract_text_from_image(image_data_uri="data:image/png;base64,AA==")
