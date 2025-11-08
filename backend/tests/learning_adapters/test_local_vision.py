"""
Unit tests for the local Vision adapter (DSPy/Ollama-backed).

Intent:
    Drive a minimal implementation via TDD:
      - Happy path for JPEG/PNG/PDF returns Markdown and metadata.
      - Timeouts are classified as transient errors.
      - Unsupported MIME types are classified as permanent errors.

Notes:
    We mock the `ollama` client to avoid network/model dependencies.
    Tests import error classes and result types from the worker module.
"""

from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

pytest.importorskip("psycopg")

from backend.learning.workers.process_learning_submission_jobs import (  # type: ignore
    VisionPermanentError,
    VisionResult,
    VisionTransientError,
)


class _FakeOllamaClient:
    """Minimal stub for the ollama client used by the adapter."""

    def __init__(self, *, mode: str = "ok"):
        self.mode = mode

    def generate(self, model: str, prompt: str, options: dict | None = None, **_: object) -> dict:
        if self.mode == "timeout":
            raise TimeoutError("simulated timeout")
        # Return a deterministic response payload as many client libs do.
        return {"response": "## Extracted text\n\nFrom local vision."}


def _install_fake_ollama(monkeypatch: pytest.MonkeyPatch, *, mode: str = "ok") -> None:
    fake_module = SimpleNamespace(Client=lambda base_url=None: _FakeOllamaClient(mode=mode))
    monkeypatch.setitem(sys.modules, "ollama", fake_module)


@pytest.mark.parametrize(
    "mime",
    [
        "image/jpeg",
        "image/png",
        "application/pdf",
    ],
)
def test_local_vision_happy_path_returns_markdown(monkeypatch: pytest.MonkeyPatch, tmp_path, mime: str) -> None:
    _install_fake_ollama(monkeypatch, mode="ok")

    # Import after monkeypatching so adapter sees fake module.
    import importlib

    mod = importlib.import_module("backend.learning.adapters.local_vision")
    adapter = mod.build()  # type: ignore[attr-defined]

    # For image/jpeg|png provide local bytes so the adapter can attach images.
    submission = {"id": "deadbeef-dead-beef-dead-beef000001", "kind": "file", "text_body": None}
    if mime in {"image/jpeg", "image/png"}:
        root = tmp_path / "storage"
        file_path = root / "submissions" / ("img.jpg" if mime == "image/jpeg" else "img.png")
        file_path.parent.mkdir(parents=True)
        header = b"\xff\xd8\xff" if mime == "image/jpeg" else b"\x89PNG\r\n\x1a\n"
        file_path.write_bytes(header + b"x" * 16)
        monkeypatch.setenv("STORAGE_VERIFY_ROOT", str(root))
        job_payload = {"mime_type": mime, "storage_key": f"submissions/{file_path.name}", "size_bytes": file_path.stat().st_size}
    else:
        job_payload = {"mime_type": mime, "storage_key": "files/abc123"}

    result: VisionResult = adapter.extract(submission=submission, job_payload=job_payload)
    assert isinstance(result, VisionResult)
    assert isinstance(result.text_md, str) and len(result.text_md.strip()) > 0
    # Metadata should indicate a local adapter for observability.
    assert isinstance(result.raw_metadata, dict)
    assert result.raw_metadata.get("adapter") in {"local", "local_vision"}


def test_local_vision_timeout_is_transient(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_ollama(monkeypatch, mode="timeout")

    import importlib

    mod = importlib.import_module("backend.learning.adapters.local_vision")
    adapter = mod.build()  # type: ignore[attr-defined]

    submission = {"id": "deadbeef-dead-beef-dead-beef000002", "kind": "file"}
    job_payload = {"mime_type": "image/jpeg", "storage_key": "files/def456"}

    with pytest.raises(VisionTransientError):
        adapter.extract(submission=submission, job_payload=job_payload)


def test_local_vision_unsupported_mime_is_permanent(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_ollama(monkeypatch, mode="ok")

    import importlib

    mod = importlib.import_module("backend.learning.adapters.local_vision")
    adapter = mod.build()  # type: ignore[attr-defined]

    submission = {"id": "deadbeef-dead-beef-dead-beef000003", "kind": "file"}
    job_payload = {"mime_type": "application/zip", "storage_key": "files/ghi789"}

    with pytest.raises(VisionPermanentError):
        adapter.extract(submission=submission, job_payload=job_payload)
