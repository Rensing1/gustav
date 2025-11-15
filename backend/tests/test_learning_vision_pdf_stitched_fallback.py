"""
Vision adapter PDF fallback behavior tests.

Expectations:
- For PDFs, the adapter must never call the model without images.
- If no stitched image exists and original PDF is unavailable, raise transient error.
- If stitched is absent but original exists, render via process_pdf_bytes, stitch, and call once with one image.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from io import BytesIO
import types
import pytest
from PIL import Image

from backend.learning.adapters.local_vision import build


class _RecordingClient:
    def __init__(self, host=None):
        self.calls: list[dict] = []
        sys.modules.get("ollama").last_instance = self  # type: ignore[attr-defined]

    def generate(self, *, model: str, prompt: str, options: dict, images: list[str] | None = None):  # type: ignore[override]
        self.calls.append({"model": model, "prompt": prompt, "options": options, "images": images or []})
        return {"response": "ok"}


def _png_bytes(w: int, h: int, gray: int) -> bytes:
    im = Image.new("L", (w, h), color=gray)
    buf = BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def test_pdf_without_stitched_or_original_raises_transient(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_VERIFY_ROOT", str(tmp_path))
    monkeypatch.setenv("AI_VISION_MODEL", "qwen2.5vl:3b")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

    # Inject fake ollama client; should not be called
    fake = types.SimpleNamespace(Client=_RecordingClient, last_instance=None)
    monkeypatch.setitem(sys.modules, "ollama", fake)

    adapter = build()
    submission = {
        "id": "sub-1",
        "course_id": "c1",
        "task_id": "t1",
        "student_sub": "s1",
        "kind": "file",
        "mime_type": "application/pdf",
        "storage_key": "submissions/c1/t1/s1/sub-1.pdf",
    }
    job_payload = {"mime_type": "application/pdf", "storage_key": submission["storage_key"]}

    with pytest.raises(Exception) as exc:
        adapter.extract(submission=submission, job_payload=job_payload)
    assert "pdf_images_unavailable" in str(exc.value)
    used = getattr(sys.modules.get("ollama"), "last_instance", None)
    if used is not None:
        assert getattr(used, "calls", []) == []


def test_pdf_remote_page_fetch_untrusted_host_degrades_to_unavailable(tmp_path, monkeypatch):
    """Remote derived fetch failures must surface as pdf_images_unavailable."""

    monkeypatch.setenv("STORAGE_VERIFY_ROOT", str(tmp_path))
    monkeypatch.setenv("AI_VISION_MODEL", "qwen2.5vl:3b")
    # Force remote fetch path but make Supabase base URL untrusted (http + remote host)
    monkeypatch.setenv("SUPABASE_URL", "http://supabase.cloud:54321")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "srk-test")

    fake = types.SimpleNamespace(Client=_RecordingClient, last_instance=None)
    monkeypatch.setitem(sys.modules, "ollama", fake)

    adapter = build()
    submission = {
        "id": "sub-untrusted",
        "course_id": "course",
        "task_id": "task",
        "student_sub": "student",
        "kind": "file",
        "mime_type": "application/pdf",
        "storage_key": "submissions/course/task/student/sub-untrusted.pdf",
    }
    job_payload = {"mime_type": "application/pdf", "storage_key": submission["storage_key"]}

    with pytest.raises(Exception) as exc:
        adapter.extract(submission=submission, job_payload=job_payload)
    assert "pdf_images_unavailable" in str(exc.value)


def test_pdf_renders_and_stitches_from_original(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_VERIFY_ROOT", str(tmp_path))
    monkeypatch.setenv("AI_VISION_MODEL", "qwen2.5vl:3b")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

    # Create fake original PDF bytes (content irrelevant; we will mock process_pdf_bytes)
    course_id = "c1"
    task_id = "t1"
    student_sub = "s1"
    submission_id = "sub-2"
    storage_key = f"submissions/{course_id}/{task_id}/{student_sub}/{submission_id}.pdf"
    pdf_path = tmp_path / storage_key
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_bytes = b"%PDF-1.4\n% dummy"
    pdf_path.write_bytes(pdf_bytes)
    import hashlib
    sha = hashlib.sha256(pdf_bytes).hexdigest()

    # Monkeypatch pipeline.process_pdf_bytes to return two PNG-like pages

    class _Page:
        def __init__(self, data: bytes):
            self.data = data

    def _fake_process_pdf_bytes(_: bytes):
        return ([_Page(_png_bytes(10, 5, 10)), _Page(_png_bytes(10, 7, 200))], types.SimpleNamespace())

    # Patch the imported name used inside the adapter module
    import backend.learning.adapters.local_vision as local_vision  # type: ignore
    monkeypatch.setattr(local_vision, "process_pdf_bytes", _fake_process_pdf_bytes)

    # Inject fake ollama client
    fake = types.SimpleNamespace(Client=_RecordingClient, last_instance=None)
    monkeypatch.setitem(sys.modules, "ollama", fake)

    adapter = build()
    submission = {
        "id": submission_id,
        "course_id": course_id,
        "task_id": task_id,
        "student_sub": student_sub,
        "kind": "file",
        "mime_type": "application/pdf",
        "storage_key": storage_key,
        "size_bytes": len(pdf_bytes),
        "sha256": sha,
    }
    job_payload = {"mime_type": "application/pdf", "storage_key": storage_key, "size_bytes": len(pdf_bytes), "sha256": sha}

    # First, ensure the stitched is produced via the helper
    stitched = adapter._ensure_pdf_stitched_png(submission=submission, job_payload=job_payload)  # type: ignore[attr-defined]
    assert isinstance(stitched, (bytes, bytearray)) and len(stitched) > 0
    # Then extract should call the model once with a single image
    result = adapter.extract(submission=submission, job_payload=job_payload)
    assert isinstance(result.text_md, str)
    used = getattr(sys.modules.get("ollama"), "last_instance", None)
    calls = getattr(used, "calls", [])
    assert len(calls) == 1
    assert isinstance(calls[0].get("images"), list) and len(calls[0]["images"]) == 1
