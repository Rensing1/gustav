"""
Learning routes should use centralized storage config, not read env directly.

TDD: This test monkeypatches the central config getter to a sentinel value that
differs from the environment. It expects the learning adapter's `_storage_bucket()`
to reflect the centralized config.

Expected to fail until learning routes delegate to backend.storage.config.
"""
from __future__ import annotations

import importlib
import os
import sys


def test_learning_storage_bucket_prefers_central_config(monkeypatch):
    # Set env to a different value than our sentinel
    monkeypatch.setenv("LEARNING_STORAGE_BUCKET", "subs-env")

    # Prepare central config with a sentinel return value
    import backend.storage.config as cfg
    monkeypatch.setattr(cfg, "get_submissions_bucket", lambda: "subs-cfg", raising=True)

    # Reload learning routes to pick up behavior. Use alias-friendly name
    # because the module registers both `routes.learning` and
    # `backend.web.routes.learning`.
    if "routes.learning" in importlib.sys.modules:
        importlib.reload(importlib.import_module("routes.learning"))
    import routes.learning as learning

    # Expect the learning adapter to use central config value
    assert learning._storage_bucket() == "subs-cfg"


def test_local_vision_adapter_uses_configured_bucket(monkeypatch, tmp_path):
    """Vision adapter must build remote URLs with the centralized bucket."""
    monkeypatch.setenv("STORAGE_VERIFY_ROOT", str(tmp_path))
    monkeypatch.setenv("SUPABASE_URL", "https://supabase.local")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "srk")
    monkeypatch.setenv("LEARNING_STORAGE_BUCKET", "subs-env")

    import backend.storage.config as cfg

    monkeypatch.setattr(cfg, "get_submissions_bucket", lambda: "subs-cfg", raising=True)

    # Patch httpx before importing the adapter so remote fetches use the sentinel.
    class _Stream:
        def __init__(self, tracker: list[str], data: bytes):
            self._tracker = tracker
            self._data = data
            self.status_code = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def iter_bytes(self):  # type: ignore[no-untyped-def]
            yield self._data

    class _Client:
        def __init__(self, tracker: list[str], data: bytes):
            self._tracker = tracker
            self._data = data

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def stream(self, method: str, url: str, headers=None):  # type: ignore[no-untyped-def]
            self._tracker.append(url)
            return _Stream(self._tracker, self._data)

    class _HttpxModule:
        def __init__(self) -> None:
            self.urls: list[str] = []
            self._data = b"%PDF-1.4\n"

        def Client(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            return _Client(self.urls, self._data)

    fake_httpx = _HttpxModule()
    monkeypatch.setitem(sys.modules, "httpx", fake_httpx)

    import backend.learning.adapters.local_vision as local_vision

    importlib.reload(local_vision)

    adapter = local_vision.build()

    submission = {
        "id": "sub-123",
        "course_id": "course-1",
        "task_id": "task-1",
        "student_sub": "student-1",
        "storage_key": "submissions/course-1/task-1/student-1/original.pdf",
    }
    job_payload = {"mime_type": "application/pdf", "storage_key": submission["storage_key"]}

    adapter._ensure_pdf_stitched_png(submission=submission, job_payload=job_payload)

    assert fake_httpx.urls, "expected remote fetch attempt"
    url = fake_httpx.urls[0]
    assert "/storage/v1/object/subs-cfg/" in url, f"expected configured bucket in URL, got: {url}"
