"""
Local Vision adapter -- Filius FLS extraction (deterministic).

Intent:
    Filius submissions (`application/x.filius.fls`) must not go through OCR.
    The adapter should extract deterministic Markdown evidence instead.
"""

from __future__ import annotations

from hashlib import sha256
import io
from pathlib import Path
import zipfile

import pytest

pytest.importorskip("psycopg")

from backend.learning.workers.process_learning_submission_jobs import VisionResult  # type: ignore
from backend.storage.config import get_submissions_bucket


FILIUS_MIME = "application/x.filius.fls"
XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<java version="17" class="java.beans.XMLDecoder">
  <string>2.5</string>
</java>
"""


def _fls_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("projekt/konfiguration.xml", XML)
    return buf.getvalue()


def test_local_vision_filius_fls_returns_evidence_markdown(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fls_bytes = _fls_bytes()
    digest = sha256(fls_bytes).hexdigest()

    bucket = get_submissions_bucket()
    submission = {
        "id": "deadbeef-dead-beef-dead-beef0000ff01",
        "kind": "file",
        "text_body": None,
        "course_id": "course-1",
        "task_id": "task-1",
        "student_sub": "student-1",
    }

    storage_root = tmp_path / "storage"
    storage_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("STORAGE_VERIFY_ROOT", str(storage_root))

    storage_key = f"{bucket}/{submission['course_id']}/{submission['task_id']}/{submission['student_sub']}/project.fls"
    file_path = storage_root / storage_key
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(fls_bytes)

    job_payload = {
        "mime_type": FILIUS_MIME,
        "storage_key": storage_key,
        "size_bytes": file_path.stat().st_size,
        "sha256": digest,
    }

    import importlib

    mod = importlib.import_module("backend.learning.adapters.local_vision")
    adapter = mod.build()  # type: ignore[attr-defined]

    result: VisionResult = adapter.extract(submission=submission, job_payload=job_payload)
    assert isinstance(result, VisionResult)
    assert "filius.evidence.v1" in result.text_md
    assert isinstance(result.raw_metadata, dict)
    assert result.raw_metadata.get("backend") == "filius_fls"


def test_local_vision_filius_fls_returns_topology_evidence_for_real_fixture(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fls_bytes = Path("backend/tests/fixtures/filius/inf-schule-clientserver/filius_ClientServer.fls").read_bytes()
    digest = sha256(fls_bytes).hexdigest()

    bucket = get_submissions_bucket()
    submission = {
        "id": "deadbeef-dead-beef-dead-beef0000ff02",
        "kind": "file",
        "text_body": None,
        "course_id": "course-1",
        "task_id": "task-1",
        "student_sub": "student-1",
    }

    storage_root = tmp_path / "storage"
    storage_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("STORAGE_VERIFY_ROOT", str(storage_root))

    storage_key = f"{bucket}/{submission['course_id']}/{submission['task_id']}/{submission['student_sub']}/project.fls"
    file_path = storage_root / storage_key
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(fls_bytes)

    job_payload = {
        "mime_type": FILIUS_MIME,
        "storage_key": storage_key,
        "size_bytes": file_path.stat().st_size,
        "sha256": digest,
    }

    import importlib

    mod = importlib.import_module("backend.learning.adapters.local_vision")
    adapter = mod.build()  # type: ignore[attr-defined]

    result: VisionResult = adapter.extract(submission=submission, job_payload=job_payload)

    assert "## Nodes" in result.text_md
    assert "## Links" in result.text_md
    assert "192.168.0.0/24" in result.text_md
    assert "GUIKnotenItem" in result.text_md
