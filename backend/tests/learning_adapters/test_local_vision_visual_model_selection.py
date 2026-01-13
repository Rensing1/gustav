"""
Local Vision adapter — Visual task model selection (Phase 3)

Intent:
    Visual tasks must use a dedicated Vision Language Model (VLM) so that
    graphical content is interpreted correctly, while native tasks can keep an
    OCR-oriented prompt/model.

Design:
    - `AI_VISION_MODEL` remains the default (OCR-like extraction).
    - `AI_VISUAL_MODEL` overrides the model when `job_payload.task_kind="visual"`.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("psycopg")


class _CapturingOllamaClient:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def generate(self, **kwargs: object) -> dict:
        self.calls.append(dict(kwargs))
        return {"response": "## ok"}


def _install_capturing_ollama(monkeypatch: pytest.MonkeyPatch, client: _CapturingOllamaClient) -> None:
    fake_module = SimpleNamespace(Client=lambda base_url=None: client)
    monkeypatch.setitem(sys.modules, "ollama", fake_module)


def _write_dummy_png(path: Path) -> None:
    # Minimal valid-ish PNG header + a little payload; sufficient for byte reads.
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 32)


def test_visual_task_uses_visual_model_and_non_ocr_prompt(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client = _CapturingOllamaClient()
    _install_capturing_ollama(monkeypatch, client)

    monkeypatch.setenv("AI_VISION_MODEL", "ocr-model")
    monkeypatch.setenv("AI_VISUAL_MODEL", "vlm-model")

    # Ensure local reads succeed so the adapter reaches the model call.
    storage_root = tmp_path / "storage"
    storage_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("STORAGE_VERIFY_ROOT", str(storage_root))

    storage_key = "submissions/course/task/student/visual.png"
    target = storage_root / storage_key
    target.parent.mkdir(parents=True, exist_ok=True)
    _write_dummy_png(target)

    # Import after env/module patching.
    mod = importlib.import_module("backend.learning.adapters.local_vision")
    importlib.reload(mod)
    adapter = mod.build()  # type: ignore[attr-defined]

    submission = {"id": "sub-1", "kind": "image", "mime_type": "image/png", "storage_key": storage_key}

    # 1) Native-like: no task_kind provided -> OCR model
    _ = adapter.extract(
        submission=submission,
        job_payload={"mime_type": "image/png", "storage_key": storage_key, "size_bytes": target.stat().st_size},
    )
    assert client.calls, "expected at least one ollama.generate call"
    first = client.calls[-1]
    assert first.get("model") == "ocr-model"
    assert isinstance(first.get("prompt"), str)
    assert "OCR" in str(first.get("prompt"))

    # 2) Visual: task_kind=visual -> VLM model + non-OCR intent
    _ = adapter.extract(
        submission=submission,
        job_payload={
            "mime_type": "image/png",
            "storage_key": storage_key,
            "size_bytes": target.stat().st_size,
            "task_kind": "visual",
        },
    )
    second = client.calls[-1]
    assert second.get("model") == "vlm-model"
    prompt = str(second.get("prompt") or "")
    assert "OCR-Werkzeug" not in prompt, "visual tasks must not force OCR-only prompt"

