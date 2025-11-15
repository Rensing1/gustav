"""
Unit tests for the Local-Vision model invocation helper.

Intent:
    Must-Fix 1 verlangt kleinere Helfer. Dieses Modul definiert Tests für den
    künftigen `_call_model`-Helper, damit wir Verhalten (images-Handling,
    Markdown-Strip, Timeout-Mapping) zuerst vertraglich festhalten (Red-Phase).
"""

from __future__ import annotations

from types import SimpleNamespace
import sys

import pytest

pytest.importorskip("psycopg")


class _RecordingClient:
    def __init__(self, response):
        self.calls: list[dict] = []
        self._response = response

    def generate(self, **kwargs):  # type: ignore[no-untyped-def]
        self.calls.append(kwargs)
        return self._response


def _install_fake_ollama(monkeypatch: pytest.MonkeyPatch, response):
    client = _RecordingClient(response=response)
    fake = SimpleNamespace(Client=lambda base_url=None: client)
    monkeypatch.setitem(sys.modules, "ollama", fake)
    return client


def test_call_model_passes_images_kwarg(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _install_fake_ollama(monkeypatch, {"response": "ok"})
    import backend.learning.adapters.local_vision as local_vision  # type: ignore

    text = local_vision._call_model(  # type: ignore[attr-defined]
        mime="application/pdf",
        prompt="prompt",
        model="vision",
        base_url="http://ollama:11434",
        timeout=5,
        image_b64=None,
        image_list_b64=["img-data"],
    )
    assert text == "ok"
    assert len(client.calls) == 1
    assert client.calls[0]["images"] == ["img-data"]


def test_call_model_strips_fenced_code(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _install_fake_ollama(
        monkeypatch,
        {"response": "```\nline1\nline2\n```"},
    )
    import backend.learning.adapters.local_vision as local_vision  # type: ignore

    text = local_vision._call_model(  # type: ignore[attr-defined]
        mime="image/png",
        prompt="prompt",
        model="vision",
        base_url="http://ollama:11434",
        timeout=5,
        image_b64="img-one",
        image_list_b64=[],
    )
    assert text == "line1\nline2"
    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["images"] == ["img-one"]
