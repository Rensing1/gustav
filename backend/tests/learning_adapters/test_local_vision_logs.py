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
    monkeypatch.setenv("AI_VISION_MODEL", "qwen2.5vl:3b")
    monkeypatch.setenv("SUPABASE_URL", "http://supabase.local:54321")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "srk")

    # Fake httpx.get returning HTML bytes with 200 to trigger wrong_content path
    class _Resp:
        def __init__(self, content: bytes, status_code: int = 200, headers: dict | None = None):
            self.content = content
            self.status_code = status_code
            self.headers = headers or {"content-type": "text/html"}

    html = b"<!doctype html><title>Not Found</title>"
    fake_httpx = SimpleNamespace(get=lambda url, headers=None, timeout=None: _Resp(html, 200))
    monkeypatch.setitem(sys.modules, "httpx", fake_httpx)

    # Fake ollama client (should not be called in this path)
    class _Client:
        def __init__(self, host=None):
            self.calls = []
        def generate(self, **kwargs):  # pragma: no cover
            self.calls.append(kwargs)
            return {"response": "n/a"}

    fake_ollama = SimpleNamespace(Client=lambda base_url=None: _Client())
    monkeypatch.setitem(sys.modules, "ollama", fake_ollama)

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

