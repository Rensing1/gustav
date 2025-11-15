"""
Vision adapter — remote fetch from Supabase when local file missing.

Why:
    In proxy mode files land in Supabase Storage and are not available under
    STORAGE_VERIFY_ROOT. The adapter should fetch image bytes via service-role
    to provide `images=[<b64>]` to the model.

Approach:
    - Do NOT set STORAGE_VERIFY_ROOT.
    - Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.
    - Monkeypatch httpx.Client to return PNG bytes via streaming; patch ollama.Client to capture
      `images` parameter.
"""

from __future__ import annotations

import base64
import importlib
from types import SimpleNamespace
import sys

import pytest

pytest.importorskip("psycopg")

from backend.learning.workers.process_learning_submission_jobs import (  # type: ignore
    VisionResult,
    VisionTransientError,
)


class _CapturingClient:
    def __init__(self) -> None:
        self.last_images = None

    def generate(self, *, model: str, prompt: str, options: dict | None = None, images: list[str] | None = None, **_: object) -> dict:  # type: ignore[override]
        self.last_images = images
        return {"response": "ok"}


class _FakeHttpxStream:
    def __init__(self, data: bytes, status_code: int = 200):
        self._data = data
        self.status_code = status_code

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def iter_bytes(self):  # type: ignore[no-untyped-def]
        yield self._data


class _FakeHttpxClient:
    def __init__(self, data: bytes, status_code: int = 200):
        self._data = data
        self._status_code = status_code

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def stream(self, *_args, **_kwargs):  # type: ignore[no-untyped-def]
        return _FakeHttpxStream(self._data, self._status_code)


def _install_fake_httpx_and_ollama(monkeypatch: pytest.MonkeyPatch, data: bytes, client: _CapturingClient, status_code: int = 200) -> None:
    fake_httpx = SimpleNamespace(Client=lambda timeout=None, follow_redirects=None: _FakeHttpxClient(data, status_code))
    monkeypatch.setitem(sys.modules, "httpx", fake_httpx)
    fake_ollama = SimpleNamespace(Client=lambda base_url=None: client)
    monkeypatch.setitem(sys.modules, "ollama", fake_ollama)


def test_remote_fetches_image_and_sends_to_model(monkeypatch: pytest.MonkeyPatch) -> None:
    # No local storage root
    monkeypatch.delenv("STORAGE_VERIFY_ROOT", raising=False)
    # Supabase service-role access
    monkeypatch.setenv("SUPABASE_URL", "http://supabase.local:54321")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "srk")

    # Prepare a tiny PNG payload returned by the fake httpx client
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


def test_remote_fetch_rejects_invalid_supabase_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STORAGE_VERIFY_ROOT", raising=False)
    # Invalid scheme must short-circuit before issuing HTTP requests
    monkeypatch.setenv("SUPABASE_URL", "ftp://supabase.local/storage")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "srk")

    def _fail_client(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("httpx.Client must not be instantiated for invalid SUPABASE_URL")

    fake_httpx = SimpleNamespace(Client=_fail_client)
    monkeypatch.setitem(sys.modules, "httpx", fake_httpx)

    fake_ollama = SimpleNamespace(Client=lambda base_url=None: _CapturingClient())
    monkeypatch.setitem(sys.modules, "ollama", fake_ollama)

    mod = importlib.import_module("backend.learning.adapters.local_vision")
    adapter = mod.build()  # type: ignore[attr-defined]

    submission = {"id": "untrusted-host", "kind": "file"}
    job_payload = {
        "mime_type": "image/png",
        "storage_key": "submissions/course/task/student/file.png",
        "size_bytes": 1024,
        "sha256": None,
    }

    with pytest.raises(VisionTransientError):
        adapter.extract(submission=submission, job_payload=job_payload)


def test_storage_base_hosts_include_port(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://supabase.local:54321")
    monkeypatch.delenv("SUPABASE_PUBLIC_URL", raising=False)

    mod = importlib.import_module("backend.learning.adapters.local_vision")
    base_url, hosts = mod._storage_base_and_hosts()  # type: ignore[attr-defined]
    assert base_url == "https://supabase.local:54321"
    assert "supabase.local:54321" in hosts


def test_download_rejects_http_for_remote_hosts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STORAGE_VERIFY_ROOT", raising=False)
    monkeypatch.setenv("SUPABASE_URL", "http://supabase.cloud:8080")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "srk")
    mod = importlib.import_module("backend.learning.adapters.local_vision")

    def _fail_client(*_args, **_kwargs):
        raise AssertionError("httpx.Client must not run for remote http base")

    monkeypatch.setitem(sys.modules, "httpx", SimpleNamespace(Client=_fail_client))

    data, reason = mod._download_supabase_object(  # type: ignore[attr-defined]
        bucket="submissions",
        object_key="course/task/student/file.png",
        srk="srk",
        max_bytes=16,
    )
    assert data is None
    assert reason == "untrusted_host"


def test_download_reports_http_status_code(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STORAGE_VERIFY_ROOT", raising=False)
    monkeypatch.setenv("SUPABASE_URL", "https://supabase.local:54321")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "srk")
    mod = importlib.import_module("backend.learning.adapters.local_vision")

    class _Client:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def stream(self, *_args, **_kwargs):  # type: ignore[no-untyped-def]
            return _FakeHttpxStream(b"", status_code=403)

    monkeypatch.setitem(sys.modules, "httpx", SimpleNamespace(Client=lambda **_: _Client()))

    data, reason = mod._download_supabase_object(  # type: ignore[attr-defined]
        bucket="submissions",
        object_key="course/task/student/file.png",
        srk="srk",
        max_bytes=64,
    )
    assert data is None
    assert reason == "http_error:403"



def test_remote_fetch_aborts_when_download_exceeds_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STORAGE_VERIFY_ROOT", raising=False)
    monkeypatch.setenv("SUPABASE_URL", "http://supabase.local:54321")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "srk")
    monkeypatch.setenv("LEARNING_MAX_UPLOAD_BYTES", "32")

    # Prepare payload larger than limit (64 bytes)
    payload = b"\x89PNG\r\n\x1a\n" + (b"z" * 56)
    client = _CapturingClient()
    _install_fake_httpx_and_ollama(monkeypatch, payload, client)

    mod = importlib.import_module("backend.learning.adapters.local_vision")
    adapter = mod.build()  # type: ignore[attr-defined]

    submission = {"id": "too-big-fetch", "kind": "file"}
    job_payload = {
        "mime_type": "image/png",
        "storage_key": "submissions/course/task/student/file.png",
        "size_bytes": 8,
        "sha256": None,
    }

    with pytest.raises(VisionTransientError):
        adapter.extract(submission=submission, job_payload=job_payload)


def test_remote_fetch_logs_success_without_pii(monkeypatch: pytest.MonkeyPatch, caplog) -> None:
    monkeypatch.delenv("STORAGE_VERIFY_ROOT", raising=False)
    monkeypatch.setenv("SUPABASE_URL", "http://supabase.local:54321")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "srk")
    caplog.set_level("INFO")

    png = b"\x89PNG\r\n\x1a\n" + b"y" * 32
    client = _CapturingClient()
    _install_fake_httpx_and_ollama(monkeypatch, png, client)

    mod = importlib.import_module("backend.learning.adapters.local_vision")
    adapter = mod.build()  # type: ignore[attr-defined]

    submission = {
        "id": "sub-log-success",
        "course_id": "course-log",
        "task_id": "task-log",
        "student_sub": "studentPii",
        "kind": "file",
        "mime_type": "image/png",
    }
    job_payload = {
        "mime_type": "image/png",
        "storage_key": "submissions/course-log/task-log/studentPii/remote.png",
        "size_bytes": len(png),
    }

    adapter.extract(submission=submission, job_payload=job_payload)
    logs = "\n".join(r.getMessage() for r in caplog.records)
    assert "action=fetch_remote_image" in logs
    assert "studentPii" not in logs
    assert "course-log/task-log" not in logs


def test_remote_fetch_redirect_raises_transient(monkeypatch: pytest.MonkeyPatch, caplog) -> None:
    monkeypatch.delenv("STORAGE_VERIFY_ROOT", raising=False)
    monkeypatch.setenv("SUPABASE_URL", "https://supabase.local:54321")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "srk")
    caplog.set_level("INFO")

    client = _CapturingClient()
    _install_fake_httpx_and_ollama(monkeypatch, b"", client, status_code=302)

    mod = importlib.import_module("backend.learning.adapters.local_vision")
    adapter = mod.build()  # type: ignore[attr-defined]

    submission = {
        "id": "sub-redirect-img",
        "course_id": "course-log",
        "task_id": "task-log",
        "student_sub": "studentPii",
        "kind": "file",
        "mime_type": "image/png",
    }
    job_payload = {
        "mime_type": "image/png",
        "storage_key": "submissions/course-log/task-log/studentPii/remote.png",
        "size_bytes": 12,
    }

    with pytest.raises(VisionTransientError) as exc:
        adapter.extract(submission=submission, job_payload=job_payload)
    assert "remote_fetch_failed" in str(exc.value)

    logs = "\n".join(r.getMessage() for r in caplog.records)
    assert "action=remote_fetch_failed" in logs
    assert "reason=redirect" in logs


def test_resolve_image_bytes_prefers_local_and_returns_meta(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    from backend.learning.adapters import local_vision

    helper = local_vision._resolve_submission_image_bytes  # type: ignore[attr-defined]
    storage_root = tmp_path / "root"
    storage_root.mkdir()
    data_path = storage_root / "submissions/course/task/student/image.png"
    data_path.parent.mkdir(parents=True, exist_ok=True)
    data = b"\x89PNG\r\n\x1a\n" + b"a" * 8
    data_path.write_bytes(data)

    monkeypatch.setenv("STORAGE_VERIFY_ROOT", str(storage_root))
    submission = {"id": "sub-local", "course_id": "course", "task_id": "task", "student_sub": "student"}
    job_payload = {"mime_type": "image/png", "storage_key": str(data_path.relative_to(storage_root))}

    meta: Dict = {}
    image_b64 = helper(
        submission=submission,
        job_payload=job_payload,
        bucket="submissions",
        max_download_bytes=1024,
        meta=meta,
    )
    assert image_b64 is not None
    assert base64.b64decode(image_b64) == data
    assert meta.get("bytes_read") == len(data)
