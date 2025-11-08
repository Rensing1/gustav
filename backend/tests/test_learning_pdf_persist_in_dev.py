"""Dev hook integration: PDF submission triggers rendering and persistence.

We call the internal `_dev_try_process_pdf` helper with a temporary storage
root and verify that page PNGs are written and the repo is marked extracted.
"""
from __future__ import annotations

import os
from pathlib import Path


class _FakeRepo:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[str]]] = []

    # Matches the AnalysisStatusRepo protocol expected by persistence
    def mark_extracted(self, *, submission_id: str, page_keys: list[str]) -> None:
        self.calls.append((submission_id, list(page_keys)))


def test_dev_try_process_pdf_renders_and_persists(tmp_path, monkeypatch):
    # Arrange: create a dummy PDF file (content doesn't matter; we stub rendering)
    root = tmp_path / "storage"
    bucket = "learning-submissions"
    storage_key = "submissions/C/T/S/123-file.pdf"
    pdf_path = root / storage_key
    pdf_path.parent.mkdir(parents=True)
    pdf_path.write_bytes(b"%PDF-1.4\n...")

    # Stub process_pdf_bytes to return two pages with bytes
    class _Page:
        def __init__(self, data: bytes) -> None:
            self.png_bytes = data
            self.width = 10
            self.height = 10

    def _fake_process(data: bytes):  # noqa: ARG001 - signature parity
        return ([_Page(b"A"), _Page(b"B")], {"pages": 2})

    fake_repo = _FakeRepo()

    # Patch imports used inside the helper
    monkeypatch.setenv("STORAGE_VERIFY_ROOT", str(root))
    monkeypatch.setenv("LEARNING_SUBMISSIONS_BUCKET", bucket)
    monkeypatch.setitem(os.environ, "LEARNING_SUBMISSIONS_BUCKET", bucket)
    monkeypatch.setenv("SUPABASE_URL", "")  # ensure no external wiring

    import importlib
    from backend.web import routes as _routes
    learning = importlib.import_module("backend.web.routes.learning")

    # Wire helper dependencies: bucket resolver and repo
    monkeypatch.setattr(learning, "_storage_bucket", lambda: bucket)
    monkeypatch.setattr(learning, "_get_repo", lambda: fake_repo)

    # Monkeypatch the vision pipeline function imported lazily inside the helper
    import types
    monkeypatch.setitem(
        __import__("sys").modules,
        "backend.vision.pipeline",
        types.SimpleNamespace(process_pdf_bytes=_fake_process),
    )

    # Act: invoke the helper directly
    learning._dev_try_process_pdf(
        root=str(root),
        storage_key=storage_key,
        submission_id="00000000-0000-0000-0000-00000000abcd",
        course_id="C",
        task_id="T",
        student_sub="S",
    )

    # Assert: two files are written and repo marked
    out1 = root / bucket / "submissions/C/T/S/derived/00000000-0000-0000-0000-00000000abcd/page_0001.png"
    out2 = root / bucket / "submissions/C/T/S/derived/00000000-0000-0000-0000-00000000abcd/page_0002.png"
    assert out1.exists() and out2.exists()
    assert out1.read_bytes() == b"A" and out2.read_bytes() == b"B"

    assert fake_repo.calls, "mark_extracted was not called"
    sub_id, keys = fake_repo.calls[-1]
    assert sub_id == "00000000-0000-0000-0000-00000000abcd"
    assert keys[-2].endswith("/page_0001.png") and keys[-1].endswith("/page_0002.png")

