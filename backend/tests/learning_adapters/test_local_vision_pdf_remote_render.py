"""
Vision adapter — remote fetch of original PDF from Supabase and render+stitch.

Scenario:
    - No local derived images and no local original PDF present under
      STORAGE_VERIFY_ROOT.
    - Adapter should fetch the original PDF via Supabase service-role,
      render pages, stitch into a single image, and call the model once with
      images=[<stitched>].
"""

from __future__ import annotations

import base64
import importlib
from io import BytesIO
from types import SimpleNamespace
import sys

import pytest
from PIL import Image


def _png_bytes(w: int, h: int, gray: int) -> bytes:
    im = Image.new("L", (w, h), color=gray)
    buf = BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


class _CapturingClient:
    def __init__(self, host=None):
        self.calls: list[dict] = []

    def generate(self, *, model: str, prompt: str, options: dict, images: list[str] | None = None):  # type: ignore[override]
        self.calls.append({"model": model, "prompt": prompt, "options": options, "images": images or []})
        return {"response": "ok"}


def test_pdf_remote_fetch_and_render_stitch(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Provide a local root but without any PDF or derived pages
    monkeypatch.setenv("STORAGE_VERIFY_ROOT", str(tmp_path))
    monkeypatch.setenv("AI_VISION_MODEL", "qwen2.5vl:3b")
    # Supabase service-role access
    monkeypatch.setenv("SUPABASE_URL", "http://supabase.local:54321")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "srk")

    # Fake PDF bytes returned by httpx.get
    pdf_bytes = b"%PDF-1.4\n% dummy remote"

    # Fake httpx.get
    class _Resp:
        def __init__(self, content: bytes, status_code: int = 200):
            self.content = content
            self.status_code = status_code

    fake_httpx = SimpleNamespace(get=lambda url, headers=None, timeout=None: _Resp(pdf_bytes, 200))
    monkeypatch.setitem(sys.modules, "httpx", fake_httpx)

    # Monkeypatch pipeline.process_pdf_bytes to return two PNG-like pages
    class _Page:
        def __init__(self, data: bytes):
            self.data = data

    def _fake_process_pdf_bytes(_: bytes):
        return ([_Page(_png_bytes(10, 5, 10)), _Page(_png_bytes(10, 7, 200))], SimpleNamespace())

    import backend.learning.adapters.local_vision as local_vision  # type: ignore
    monkeypatch.setattr(local_vision, "process_pdf_bytes", _fake_process_pdf_bytes)

    # Fake ollama client
    client = _CapturingClient()
    fake_ollama = SimpleNamespace(Client=lambda base_url=None: client)
    monkeypatch.setitem(sys.modules, "ollama", fake_ollama)

    mod = importlib.import_module("backend.learning.adapters.local_vision")
    adapter = mod.build()  # type: ignore[attr-defined]

    submission = {
        "id": "sub-remote",
        "course_id": "c1",
        "task_id": "t1",
        "student_sub": "s1",
        "kind": "file",
        "mime_type": "application/pdf",
        "storage_key": "submissions/c1/t1/s1/sub-remote.pdf",
    }
    job_payload = {"mime_type": "application/pdf", "storage_key": submission["storage_key"]}

    res = adapter.extract(submission=submission, job_payload=job_payload)
    # Model must be called exactly once with a single stitched image
    assert isinstance(res.get("text_md", ""), str) if isinstance(res, dict) else isinstance(getattr(res, "text_md", ""), str)
    assert len(client.calls) == 1
    images = client.calls[0].get("images")
    assert isinstance(images, list) and len(images) == 1
    stitched = base64.b64decode(images[0])
    assert stitched.startswith(b"\x89PNG")

