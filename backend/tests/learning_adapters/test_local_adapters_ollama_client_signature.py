"""
Compatibility tests for ollama.Client initialization in local adapters.

Intent:
    Ensure adapters construct the Ollama client in a way that is compatible
    with real clients expecting a positional `host` argument, not a
    `base_url` keyword. This guards against regressions where tests pass with
    a permissive fake but the real client breaks at runtime.

Scenarios:
    - Vision adapter succeeds when `ollama.Client` only accepts `host`.
    - Feedback adapter succeeds when `ollama.Client` only accepts `host`.

Notes:
    We install a fake `ollama` module with a `Client(host=None)` constructor.
    Current implementation calls `Client(base_url=...)` which raises a
    TypeError against this fake, causing the adapter to misclassify it as a
    transient error. These tests drive the adapters to use a positional arg.
"""

from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

pytest.importorskip("psycopg")

from backend.learning.workers.process_learning_submission_jobs import (  # type: ignore
    FeedbackResult,
    VisionResult,
)


class _HostOnlyOllamaClient:
    """Fake Ollama client that only accepts a positional/`host` arg."""

    def __init__(self, *, mode: str = "ok"):
        self.mode = mode

    def generate(self, model: str, prompt: str, options: dict | None = None, **_: object) -> dict:
        if self.mode == "timeout":
            raise TimeoutError("simulated timeout")
        return {"response": "### OK\n\nHost-only client accepted."}


def _install_host_only_client(monkeypatch: pytest.MonkeyPatch, *, mode: str = "ok") -> None:
    def _ctor(host=None):  # noqa: D401 - host-only signature by design
        return _HostOnlyOllamaClient(mode=mode)

    fake_module = SimpleNamespace(Client=_ctor)
    monkeypatch.setitem(sys.modules, "ollama", fake_module)


def test_local_vision_accepts_host_only_client(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _install_host_only_client(monkeypatch)

    import importlib

    mod = importlib.import_module("backend.learning.adapters.local_vision")
    adapter = mod.build()  # type: ignore[attr-defined]

    # Provide actual bytes so the adapter passes images to the model
    root = tmp_path / "storage"
    file_path = root / "submissions" / "img.jpg"
    file_path.parent.mkdir(parents=True)
    file_path.write_bytes(b"\xff\xd8\xff" + b"x" * 32)  # minimal JPEG-like bytes
    monkeypatch.setenv("STORAGE_VERIFY_ROOT", str(root))

    submission = {"id": "deadbeef-dead-beef-dead-beef100001", "kind": "file"}
    job_payload = {"mime_type": "image/jpeg", "storage_key": "submissions/img.jpg", "size_bytes": file_path.stat().st_size}

    result: VisionResult = adapter.extract(submission=submission, job_payload=job_payload)
    assert isinstance(result, VisionResult)
    assert isinstance(result.text_md, str) and len(result.text_md.strip()) > 0


def test_local_feedback_accepts_host_only_client(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_host_only_client(monkeypatch)

    import importlib

    mod = importlib.import_module("backend.learning.adapters.local_feedback")
    adapter = mod.build()  # type: ignore[attr-defined]

    res: FeedbackResult = adapter.analyze(text_md="# Text", criteria=["Inhalt", "Struktur"])  # type: ignore[arg-type]
    assert isinstance(res, FeedbackResult)
    assert res.analysis_json.get("schema") == "criteria.v2"
