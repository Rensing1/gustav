"""
Vision adapter — ensure image bytes are passed to the Ollama client.

Why:
    We observed generic model refusals (e.g., "I can't assist with that")
    for image/PDF submissions. Root cause: the local vision adapter called
    the Ollama text endpoint without providing visual inputs. This test
    drives a minimal fix by asserting that the adapter forwards base64-encoded
    image bytes via the client's `images` parameter when available.

Approach:
    - Create a tiny PNG-like byte payload written under STORAGE_VERIFY_ROOT.
    - Monkeypatch `ollama.Client` with a fake that accepts an `images` kwarg
      and captures it for assertions.
    - Call the adapter and verify we receive a Markdown response and that the
      client saw exactly one base64 image string.
"""

from __future__ import annotations

import base64
import hashlib
import importlib
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

pytest.importorskip("psycopg")

from backend.learning.workers.process_learning_submission_jobs import VisionResult  # type: ignore


class _CapturingClient:
    def __init__(self) -> None:
        self.last_call: dict | None = None

    def generate(self, *, model: str, prompt: str, options: dict | None = None, images: list[str] | None = None, **_: object) -> dict:  # type: ignore[override]
        # Record call details for the assertion
        self.last_call = {"model": model, "prompt": prompt, "options": options, "images": images}
        return {"response": "## Extracted text\n\nFrom image."}


def _install_fake_ollama(monkeypatch: pytest.MonkeyPatch, client: _CapturingClient) -> None:
    fake_module = SimpleNamespace(Client=lambda base_url=None: client)
    monkeypatch.setitem(sys.modules, "ollama", fake_module)


def test_local_vision_sends_images_param_for_png(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Prepare a small fake PNG byte stream
    data = b"\x89PNG\r\n\x1a\n" + b"0" * 32
    sha = hashlib.sha256(data).hexdigest()

    # Create storage file under verify root
    root = tmp_path / "storage"
    file_path = root / "submissions" / "img.png"
    file_path.parent.mkdir(parents=True)
    file_path.write_bytes(data)

    # Expose root to adapter
    monkeypatch.setenv("STORAGE_VERIFY_ROOT", str(root))

    # Install fake Ollama client that captures images
    client = _CapturingClient()
    _install_fake_ollama(monkeypatch, client)

    mod = importlib.import_module("backend.learning.adapters.local_vision")
    adapter = mod.build()  # type: ignore[attr-defined]

    submission = {"id": "deadbeef-dead-beef-dead-beef000010", "kind": "file"}
    job_payload = {
        "mime_type": "image/png",
        "storage_key": "submissions/img.png",
        "size_bytes": len(data),
        "sha256": sha,
    }

    res: VisionResult = adapter.extract(submission=submission, job_payload=job_payload)
    assert isinstance(res, VisionResult)
    assert "Extracted" in res.text_md

    # Assert the fake client received one base64-encoded image
    assert client.last_call is not None
    images = client.last_call.get("images")  # type: ignore[assignment]
    assert isinstance(images, list) and len(images) == 1 and isinstance(images[0], str)

    # Spot-check: base64 decodes back to our original bytes
    restored = base64.b64decode(images[0])
    assert restored.startswith(b"\x89PNG\r\n\x1a\n")

