"""
Vision adapter: ensure PDFs are stitched into a single image.

This test simulates a PDF submission whose pages have been rendered to PNGs
under the deterministic derived prefix. The local vision adapter should detect
those derived images, stitch them into a single vertical PNG, and pass exactly
one image to the Ollama client via the `images` param.

We also verify that fenced code blocks returned by the model are unwrapped.
"""
from __future__ import annotations

import sys
import types

from backend.learning.adapters.local_vision import build
from backend.storage.config import get_submissions_bucket
from backend.tests.utils.storage_fixtures import ensure_pdf_derivatives


class _FakeClient:
    def __init__(self, host=None):  # signature compatible
        self.calls: list[dict] = []
        # Expose last instance on the fake module for introspection
        sys.modules.get("ollama").last_instance = self  # type: ignore[attr-defined]

    def generate(self, *, model: str, prompt: str, options: dict, images: list[str] | None = None):  # type: ignore[override]
        # Record parameters for assertions
        self.calls.append({"model": model, "prompt": prompt, "options": options, "images": images or []})
        # Return a fenced markdown response to exercise unwrapping
        return {"response": "```markdown\nPage 1 text\n\nPage 2 text\n```"}


def test_pdf_uses_derived_page_images(tmp_path, monkeypatch):
    # Arrange: create derived page images under the deterministic prefix
    course_id = "course-1"
    task_id = "task-1"
    student_sub = "student-abc"
    submission_id = "sub-xyz"
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.setenv("LEARNING_STORAGE_BUCKET", "submissions")
    bucket = get_submissions_bucket()
    ensure_pdf_derivatives(
        root=tmp_path,
        bucket=bucket,
        course_id=course_id,
        task_id=task_id,
        student_sub=student_sub,
        submission_id=submission_id,
        page_count=2,
    )
    derived_dir = (
        tmp_path / bucket / course_id / task_id / student_sub / "derived" / submission_id
    )
    assert derived_dir.exists(), f"derived dir missing: {derived_dir}"
    derived_files = sorted(p.name for p in derived_dir.iterdir())
    assert derived_files, f"derived dir empty: {derived_dir}"

    monkeypatch.setenv("STORAGE_VERIFY_ROOT", str(tmp_path))
    monkeypatch.setenv("AI_VISION_MODEL", "qwen2.5vl:3b")
    # Inject fake ollama client
    fake = types.SimpleNamespace(Client=_FakeClient, last_instance=None)
    monkeypatch.setitem(sys.modules, "ollama", fake)

    adapter = build()

    submission = {
        "id": submission_id,
        "course_id": course_id,
        "task_id": task_id,
        "student_sub": student_sub,
        "kind": "file",
        "mime_type": "application/pdf",
        # storage_key of the original PDF is irrelevant for derived reads
        "storage_key": f"{bucket}/{course_id}/{task_id}/{student_sub}/{submission_id}.pdf",
        "size_bytes": 10,
    }
    job_payload = {"mime_type": "application/pdf", "storage_key": submission["storage_key"]}

    # Act
    result = adapter.extract(submission=submission, job_payload=job_payload)

    # Assert: model received two images and output was unwrapped
    used = getattr(sys.modules.get("ollama"), "last_instance", None)
    assert used is not None, "ollama.Client was not instantiated"
    calls = getattr(used, "calls", [])
    assert calls, "ollama.Client.generate was not called"
    # Expect one call with a single stitched image argument
    assert len(calls) == 1
    assert isinstance(calls[0].get("images"), list) and len(calls[0]["images"]) == 1
    # Also assert based on result content (unwrapped, contains both pages)
    assert isinstance(result.text_md, str)
    out = result.text_md.strip()
    assert "Page 1 text" in out
    assert "Page 2 text" in out
    # Ensure adapter metadata signals local/ollama backend
    assert result.raw_metadata.get("backend") == "ollama"
