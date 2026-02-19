"""
Local Vision adapter — SB3 evidence extraction (deterministic)

Intent:
    Scratch submissions (`application/x.scratch.sb3`) must NOT go through OCR.
    The Vision adapter should instead parse `project.json` deterministically and
    return a bounded Markdown evidence report (`scratch.evidence.v2`).
"""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import tempfile
import zipfile

import pytest

pytest.importorskip("psycopg")

from backend.learning.workers.process_learning_submission_jobs import VisionResult  # type: ignore
from backend.storage.config import get_submissions_bucket


def _make_valid_sb3_bytes() -> bytes:
    buf = tempfile.SpooledTemporaryFile(max_size=2_000_000)
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "project.json",
            '{"targets":[{"isStage":true,"name":"Stage","blocks":{},"variables":{},"lists":{},"broadcasts":{}}]}',
        )
    buf.seek(0)
    return buf.read()


def test_local_vision_sb3_returns_evidence_markdown(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    sb3_bytes = _make_valid_sb3_bytes()
    digest = sha256(sb3_bytes).hexdigest()

    bucket = get_submissions_bucket()
    submission = {
        "id": "deadbeef-dead-beef-dead-beef000099",
        "kind": "file",
        "text_body": None,
        "course_id": "course-1",
        "task_id": "task-1",
        "student_sub": "student-1",
    }

    storage_root = tmp_path / "storage"
    storage_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("STORAGE_VERIFY_ROOT", str(storage_root))

    storage_key = f"{bucket}/{submission['course_id']}/{submission['task_id']}/{submission['student_sub']}/project.sb3"
    file_path = storage_root / storage_key
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(sb3_bytes)

    job_payload = {
        "mime_type": "application/x.scratch.sb3",
        "storage_key": storage_key,
        "size_bytes": file_path.stat().st_size,
        "sha256": digest,
    }

    import importlib

    mod = importlib.import_module("backend.learning.adapters.local_vision")
    adapter = mod.build()  # type: ignore[attr-defined]

    result: VisionResult = adapter.extract(submission=submission, job_payload=job_payload)
    assert isinstance(result, VisionResult)
    assert "scratch.evidence.v2" in result.text_md
    assert isinstance(result.raw_metadata, dict)
    assert result.raw_metadata.get("adapter") == "local_vision"
    assert result.raw_metadata.get("backend") == "sb3"
