"""
Vision adapter — remote fetch from Supabase when local file missing.

Why:
    In proxy mode files land in Supabase Storage and are not available under
    STORAGE_VERIFY_ROOT. The adapter should fetch image bytes via service-role
    to provide `images=[<b64>]` to the model.

Approach:
    - Do NOT set STORAGE_VERIFY_ROOT.
    - Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.
    - Monkeypatch httpx.get to return PNG bytes; patch ollama.Client to capture
      `images` parameter.
"""

from __future__ import annotations

import base64
import importlib
from types import SimpleNamespace
import sys

import pytest

pytest.importorskip("psycopg")

from backend.learning.workers.process_learning_submission_jobs import VisionResult  # type: ignore


class _FakeResponse:
    def __init__(self, content: bytes, status_code: int = 200):
        self._content = content
        self.status_code = status_code

    @property
    def content(self) -> bytes:
        return self._content


class _CapturingClient:
    def __init__(self) -> None:
        self.last_images = None

    def generate(self, *, model: str, prompt: str, options: dict | None = None, images: list[str] | None = None, **_: object) -> dict:  # type: ignore[override]
        self.last_images = images
        return {"response": "ok"}


def _install_fake_httpx_and_ollama(monkeypatch: pytest.MonkeyPatch, data: bytes, client: _CapturingClient) -> None:
    fake_httpx = SimpleNamespace(get=lambda url, headers=None, timeout=None: _FakeResponse(data, 200))
    monkeypatch.setitem(sys.modules, "httpx", fake_httpx)
    fake_ollama = SimpleNamespace(Client=lambda base_url=None: client)
    monkeypatch.setitem(sys.modules, "ollama", fake_ollama)


def test_remote_fetches_image_and_sends_to_model(monkeypatch: pytest.MonkeyPatch) -> None:
    # No local storage root
    monkeypatch.delenv("STORAGE_VERIFY_ROOT", raising=False)
    # Supabase service-role access
    monkeypatch.setenv("SUPABASE_URL", "http://supabase.local:54321")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "srk")

    # Prepare a tiny PNG payload returned by httpx.get
    png = b"\x89PNG\r\n\x1a\n" + b"x" * 16
    client = _CapturingClient()
    _install_fake_httpx_and_ollama(monkeypatch, png, client)

    mod = importlib.import_module("backend.learning.adapters.local_vision")
    adapter = mod.build()  # type: ignore[attr-defined]

    submission = {"id": "deadbeef-dead-beef-0000-remoteimg", "kind": "file"}
    job_payload = {
        "mime_type": "image/png",
        "storage_key": "submissions/course/task/student/file.png",
        "size_bytes": len(png),
        "sha256": None,
    }

    res: VisionResult = adapter.extract(submission=submission, job_payload=job_payload)
    assert isinstance(res, VisionResult)
    assert client.last_images is not None and isinstance(client.last_images, list) and len(client.last_images) == 1
    # roundtrip check
    restored = base64.b64decode(client.last_images[0])
    assert restored.startswith(b"\x89PNG")

