"""
Vision adapter — logging redacts PII.

Expected:
  - Logs must NOT contain bucket names, object keys or student_sub values.
  - Logs MAY include submission_id and generic hints (e.g., wrong_content).
"""

from __future__ import annotations

import importlib
from types import SimpleNamespace
import sys

import pytest


def test_redacts_pii_from_logs(tmp_path, monkeypatch: pytest.MonkeyPatch, caplog) -> None:
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

    # Arrange a submission with clearly identifiable PII-like segments
    submission = {
        "id": "sub-logs-1",
        "course_id": "courseX",
        "task_id": "taskY",
        "student_sub": "studentPII",
        "kind": "file",
        "mime_type": "application/pdf",
        "storage_key": "submissions/courseX/taskY/studentPII/sub-logs-1.pdf",
    }
    job_payload = {"mime_type": "application/pdf", "storage_key": submission["storage_key"]}

    with pytest.raises(mod.VisionTransientError):
        adapter.extract(submission=submission, job_payload=job_payload)

    logs = "\n".join(r.getMessage() for r in caplog.records)
    # Positive hint still present
    assert "wrong_content" in logs or "wrong_content_pre_render" in logs
    # PII and object location details must be absent
    assert "studentPII" not in logs
    assert "courseX/taskY" not in logs
    assert "object_key=" not in logs
    assert "bucket=" not in logs


def test_redacts_pii_when_derived_page_read_fails(tmp_path, monkeypatch: pytest.MonkeyPatch, caplog) -> None:
    """
    Regression: derived PDF page reads must not log filesystem paths.

    Why:
        Derived paths include student_sub and would leak PII when logged.
    """
    from backend.storage.config import get_submissions_bucket

    monkeypatch.setenv("STORAGE_VERIFY_ROOT", str(tmp_path))

    bucket = get_submissions_bucket()
    submission_id = "sub-logs-pagefail"
    course_id = "courseX"
    task_id = "taskY"
    student_sub = "studentPII"

    derived_dir = tmp_path / bucket / course_id / task_id / student_sub / "derived" / submission_id
    derived_dir.mkdir(parents=True, exist_ok=True)

    page_path = derived_dir / "page_1.png"
    page_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 16)
    page_path.chmod(0)

    mod = importlib.import_module("backend.learning.adapters.local_vision")
    adapter = mod.build()  # type: ignore[attr-defined]

    submission = {
        "id": submission_id,
        "course_id": course_id,
        "task_id": task_id,
        "student_sub": student_sub,
        "kind": "file",
        "mime_type": "application/pdf",
        # No storage_key: keep the test local and deterministic.
        "storage_key": "",
    }
    job_payload = {"mime_type": "application/pdf", "storage_key": ""}

    with pytest.raises(mod.VisionTransientError) as exc:
        adapter.extract(submission=submission, job_payload=job_payload)
    assert "pdf_images_unavailable" in str(exc.value)

    logs = "\n".join(r.getMessage() for r in caplog.records)
    assert "studentPII" not in logs
    assert "courseX/taskY" not in logs
    assert str(page_path) not in logs
