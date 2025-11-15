"""
Vision adapter — PDF helpers (cached stitched, page keys, redirect handling).

Why:
    Must-Fix 1 verlangt kleinere Helfer + klare Logging-Pfade rund um die PDF-
    Pipeline. Diese Tests beschreiben den erwarteten Vertrag, bevor wir den
    Adapter refaktorieren (Red-Schritt im TDD-Kreis).
"""

from __future__ import annotations

import base64
import importlib
from io import BytesIO
from types import SimpleNamespace
import sys

import pytest
from PIL import Image

pytest.importorskip("psycopg")

from backend.learning.workers.process_learning_submission_jobs import (  # type: ignore
    VisionResult,
    VisionTransientError,
)


def _png_bytes(width: int, height: int, gray: int) -> bytes:
    img = Image.new("L", (width, height), color=gray)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class _CapturingClient:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def generate(self, *, model: str, prompt: str, options: dict, images: list[str] | None = None, **_: object) -> dict:  # type: ignore[override]
        self.calls.append({"model": model, "prompt": prompt, "options": options, "images": images or []})
        return {"response": "ok"}


def _reload_adapter():
    # Ensure fresh module state per test (env vars differ per scenario).
    import backend.learning.adapters.local_vision as local_vision  # type: ignore
    return importlib.reload(local_vision)


def test_pdf_prefers_cached_stitched_png(monkeypatch: pytest.MonkeyPatch, tmp_path, caplog) -> None:
    monkeypatch.setenv("STORAGE_VERIFY_ROOT", str(tmp_path))
    monkeypatch.setenv("AI_VISION_MODEL", "vision-mini")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    caplog.set_level("INFO")

    derived_dir = tmp_path / "submissions/courseA/taskB/student1/derived/sub-cache"
    derived_dir.mkdir(parents=True, exist_ok=True)
    stitched_png = _png_bytes(12, 6, 80)
    (derived_dir / "stitched.png").write_bytes(stitched_png)

    module = _reload_adapter()

    def _fail_remote(**_kwargs):
        raise AssertionError("remote fetch must not run when stitched cache exists")

    monkeypatch.setattr(module, "_download_supabase_object", _fail_remote, raising=False)

    client = _CapturingClient()
    monkeypatch.setitem(sys.modules, "ollama", SimpleNamespace(Client=lambda base_url=None: client))

    adapter = module.build()  # type: ignore[attr-defined]
    submission = {
        "id": "sub-cache",
        "course_id": "courseA",
        "task_id": "taskB",
        "student_sub": "student1",
        "kind": "file",
        "mime_type": "application/pdf",
        "storage_key": "submissions/courseA/taskB/student1/sub-cache.pdf",
    }
    job_payload = {"mime_type": "application/pdf", "storage_key": submission["storage_key"]}

    res: VisionResult = adapter.extract(submission=submission, job_payload=job_payload)
    assert isinstance(res, VisionResult)
    assert len(client.calls) == 1
    images = client.calls[0]["images"]
    assert isinstance(images, list) and len(images) == 1
    assert base64.b64decode(images[0]) == stitched_png

    logs = "\n".join(rec.getMessage() for rec in caplog.records)
    assert "action=cached_stitched" in logs
    assert "student1" not in logs
    assert "courseA/taskB" not in logs


def test_pdf_uses_page_keys_and_persists_stitched(monkeypatch: pytest.MonkeyPatch, tmp_path, caplog) -> None:
    monkeypatch.setenv("STORAGE_VERIFY_ROOT", str(tmp_path))
    monkeypatch.setenv("AI_VISION_MODEL", "vision-mini")
    caplog.set_level("INFO")

    base_dir = tmp_path / "submissions/courseB/taskC/student2/derived/sub-pages"
    base_dir.mkdir(parents=True, exist_ok=True)
    page1 = base_dir / "page_0001.png"
    page2 = base_dir / "page_0002.png"
    page1.write_bytes(_png_bytes(4, 4, 20))
    page2.write_bytes(_png_bytes(4, 5, 200))

    module = _reload_adapter()

    def _fail_remote(**_kwargs):
        raise AssertionError("remote fetch must not run when page keys exist")

    monkeypatch.setattr(module, "_download_supabase_object", _fail_remote, raising=False)

    stitched_bytes = b"stitched-from-page-keys"

    def _fake_stitch(pages: list[bytes]) -> bytes:
        assert len(pages) == 2
        return stitched_bytes

    monkeypatch.setattr(module, "stitch_images_vertically", _fake_stitch, raising=False)

    client = _CapturingClient()
    monkeypatch.setitem(sys.modules, "ollama", SimpleNamespace(Client=lambda base_url=None: client))

    adapter = module.build()  # type: ignore[attr-defined]
    submission = {
        "id": "sub-pages",
        "course_id": "courseB",
        "task_id": "taskC",
        "student_sub": "student2",
        "kind": "file",
        "mime_type": "application/pdf",
        "storage_key": "submissions/courseB/taskC/student2/sub-pages.pdf",
        "internal_metadata": {"page_keys": [str(page1.relative_to(tmp_path)), str(page2.relative_to(tmp_path))]},
    }
    job_payload = {"mime_type": "application/pdf", "storage_key": submission["storage_key"]}

    res: VisionResult = adapter.extract(submission=submission, job_payload=job_payload)
    assert isinstance(res, VisionResult)
    assert len(client.calls) == 1
    images = client.calls[0]["images"]
    assert base64.b64decode(images[0]) == stitched_bytes

    stitched_file = base_dir / "stitched.png"
    assert stitched_file.exists() and stitched_file.read_bytes() == stitched_bytes

    logs = "\n".join(rec.getMessage() for rec in caplog.records)
    assert "action=stitch_from_page_keys" in logs
    assert "student2" not in logs


def test_pdf_remote_fetch_redirect_logs_reason(monkeypatch: pytest.MonkeyPatch, tmp_path, caplog) -> None:
    monkeypatch.setenv("STORAGE_VERIFY_ROOT", str(tmp_path))
    monkeypatch.setenv("SUPABASE_URL", "https://supabase.example.com")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "srk")
    caplog.set_level("INFO")

    class _HttpxStream:
        def __init__(self):
            self.status_code = 302
            self.headers = {"location": "https://redirect.example.com"}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def iter_bytes(self):  # type: ignore[no-untyped-def]
            yield b""

    class _HttpxClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def stream(self, *_args, **_kwargs):  # type: ignore[no-untyped-def]
            return _HttpxStream()

    monkeypatch.setitem(sys.modules, "httpx", SimpleNamespace(Client=lambda **_: _HttpxClient()))

    module = _reload_adapter()

    # process_pdf_bytes should not run when download already fails
    def _fail_process(_: bytes):
        raise AssertionError("process_pdf_bytes must not run after redirect failure")

    monkeypatch.setattr(module, "process_pdf_bytes", _fail_process, raising=False)

    client = _CapturingClient()
    monkeypatch.setitem(sys.modules, "ollama", SimpleNamespace(Client=lambda base_url=None: client))

    adapter = module.build()  # type: ignore[attr-defined]
    submission = {
        "id": "sub-redirect",
        "course_id": "courseC",
        "task_id": "taskD",
        "student_sub": "student3",
        "kind": "file",
        "mime_type": "application/pdf",
        "storage_key": "submissions/courseC/taskD/student3/sub-redirect.pdf",
    }
    job_payload = {"mime_type": "application/pdf", "storage_key": submission["storage_key"]}

    with pytest.raises(VisionTransientError) as exc:
        adapter.extract(submission=submission, job_payload=job_payload)
    assert "remote_fetch_failed" in str(exc.value)

    logs = "\n".join(rec.getMessage() for rec in caplog.records)
    assert "action=remote_fetch_failed" in logs
    assert "reason=redirect" in logs
    assert "student3" not in logs
