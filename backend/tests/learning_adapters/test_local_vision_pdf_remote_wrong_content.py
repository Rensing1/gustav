"""
Vision adapter — remote fetch returns non-PDF content (HTML or JSON).

Expected:
  - Adapter treats loaded non-PDF bytes as permanent `invalid_upload_content`.
  - No model call or retry budget is consumed for deterministic mismatches.
"""

from __future__ import annotations

import importlib
from types import SimpleNamespace
import sys

import pytest


def test_pdf_remote_wrong_content_is_permanent(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STORAGE_VERIFY_ROOT", str(tmp_path))
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

    # Fake httpx streaming client returning HTML bytes with 200
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

    html = b"<!doctype html><title>Not Found</title>"
    fake_httpx = SimpleNamespace(Client=lambda timeout=None, follow_redirects=None: _HttpxClient(html, 200))
    monkeypatch.setitem(sys.modules, "httpx", fake_httpx)

    mod = importlib.import_module("backend.learning.adapters.local_vision")
    adapter = mod.build()  # type: ignore[attr-defined]

    submission = {
        "id": "sub-wrong",
        "course_id": "c1",
        "task_id": "t1",
        "student_sub": "s1",
        "kind": "file",
        "mime_type": "application/pdf",
        "storage_key": "submissions/c1/t1/s1/sub-wrong.pdf",
    }
    job_payload = {"mime_type": "application/pdf", "storage_key": submission["storage_key"]}

    with pytest.raises(mod.VisionPermanentError) as exc:
        adapter.extract(submission=submission, job_payload=job_payload)
    assert "invalid_upload_content" in str(exc.value)
