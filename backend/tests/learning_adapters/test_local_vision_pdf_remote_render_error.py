"""
Vision adapter — remote fetch returns a real PDF but rendering fails.

Expected:
  - Adapter logs `render_error` and treats as transient.
  - No model call is attempted.
"""

from __future__ import annotations

import importlib
from types import SimpleNamespace
import sys

import pytest


def test_pdf_remote_render_error_transient(tmp_path, monkeypatch: pytest.MonkeyPatch, caplog) -> None:
    monkeypatch.setenv("STORAGE_VERIFY_ROOT", str(tmp_path))
    monkeypatch.setenv("AI_VISION_MODEL", "qwen2.5vl:3b")
    monkeypatch.setenv("SUPABASE_URL", "http://supabase.local:54321")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "srk")
    # Ensure supabase.local resolves to a private host for HTTP fetches
    import socket
    import backend.learning.adapters.local_vision as local_vision  # type: ignore

    monkeypatch.setattr(
        local_vision.socket,
        "getaddrinfo",
        lambda host, *_args, **_kwargs: [
            (socket.AF_INET, None, None, "", ("10.0.0.42", 0)),
        ],
        raising=False,
    )

    # Fake httpx client returns plausible PDF bytes via streaming API
    class _HttpxStream:
        def __init__(self, data: bytes, status_code: int = 200):
            self._data = data
            self.status_code = status_code

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def iter_bytes(self):  # type: ignore[no-untyped-def]
            yield self._data

    class _HttpxClient:
        def __init__(self, data: bytes, status_code: int = 200):
            self._data = data
            self._status = status_code

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def stream(self, *_args, **_kwargs):  # type: ignore[no-untyped-def]
            return _HttpxStream(self._data, self._status)

    pdf_bytes = b"%PDF-1.4\n% test"
    fake_httpx = SimpleNamespace(Client=lambda timeout=None, follow_redirects=None: _HttpxClient(pdf_bytes, 200))
    monkeypatch.setitem(sys.modules, "httpx", fake_httpx)

    # process_pdf_bytes raises an exception
    import backend.learning.adapters.local_vision as local_vision  # type: ignore

    def _boom(_: bytes):
        raise RuntimeError("boom")

    monkeypatch.setattr(local_vision, "process_pdf_bytes", _boom)

    # Fake ollama client to detect accidental calls
    class _Client:
        def __init__(self, host=None):
            self.calls = []
        def generate(self, **kwargs):  # pragma: no cover - should not be called
            self.calls.append(kwargs)
            return {"response": "n/a"}

    fake_ollama = SimpleNamespace(Client=lambda base_url=None: _Client())
    monkeypatch.setitem(sys.modules, "ollama", fake_ollama)

    mod = importlib.import_module("backend.learning.adapters.local_vision")
    adapter = mod.build()  # type: ignore[attr-defined]

    submission = {
        "id": "sub-render-error",
        "course_id": "c1",
        "task_id": "t1",
        "student_sub": "s1",
        "kind": "file",
        "mime_type": "application/pdf",
        "storage_key": "submissions/c1/t1/s1/sub-render-error.pdf",
    }
    job_payload = {"mime_type": "application/pdf", "storage_key": submission["storage_key"]}

    with pytest.raises(mod.VisionTransientError) as exc:
        adapter.extract(submission=submission, job_payload=job_payload)
    assert "pdf_images_unavailable" in str(exc.value)

    logs = "\n".join(r.getMessage() for r in caplog.records)
    assert "render_error" in logs or "render_no_pages" in logs
