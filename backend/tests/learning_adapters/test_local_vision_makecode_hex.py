"""
Local Vision adapter — MakeCode HEX extraction (deterministic)

Intent:
    Calliope submissions (`application/x.makecode.hex`) must NOT go through OCR.
    The Vision adapter should instead extract MakeCode sources deterministically
    and return a bounded Markdown evidence report (`makecode.evidence.v1`).
"""

from __future__ import annotations

from hashlib import sha256
import json
import lzma
from pathlib import Path
import struct

import pytest

pytest.importorskip("psycopg")

from backend.learning.workers.process_learning_submission_jobs import VisionResult  # type: ignore
from backend.storage.config import get_submissions_bucket


def _hex_record(*, addr: int, record_type: int, data: bytes) -> str:
    ll = len(data)
    total = ll + ((addr >> 8) & 0xFF) + (addr & 0xFF) + (record_type & 0xFF) + sum(data)
    checksum = (-total) & 0xFF
    return f":{ll:02X}{addr:04X}{record_type:02X}{data.hex().upper()}{checksum:02X}"


def _make_hex_with_embedded_source(*, eurl: str, record_type: int = 0x0E, place_after_eof: bool = True) -> bytes:
    files = {
        "main.ts": 'basic.showString("Hi")\n',
        "pxt.json": json.dumps({"name": "test-project", "dependencies": {}}, separators=(",", ":")),
    }
    extra_header_json = json.dumps({"name": "test-project"}, separators=(",", ":"))
    files_json = json.dumps(files, separators=(",", ":"))
    text = (extra_header_json + files_json).encode("utf-8")
    compressed = lzma.compress(text, format=lzma.FORMAT_ALONE)

    header = {
        "eURL": eurl,
        "compression": "LZMA",
        "headerSize": len(extra_header_json),
        "textSize": len(text.decode("utf-8")),
    }
    header_bytes = json.dumps(header, separators=(",", ":")).encode("utf-8")
    magic = b"\x41\x14\x0E\x2F\xB8\x2F\xA2\xBB"
    blob = magic + struct.pack("<H", len(header_bytes)) + struct.pack("<I", len(compressed)) + b"\x00\x00"
    blob += header_bytes + compressed

    lines: list[str] = []
    if place_after_eof:
        # Real MakeCode Calliope downloads may append the embedded source after
        # the EOF record because flashing tools stop at EOF.
        lines.append(_hex_record(addr=0, record_type=0x01, data=b""))
        lines.append("")
    for i in range(0, len(blob), 16):
        lines.append(_hex_record(addr=i, record_type=record_type, data=blob[i : i + 16]))
    if not place_after_eof:
        lines.append(_hex_record(addr=0, record_type=0x01, data=b""))
    return ("\n".join(lines) + "\n").encode("ascii")


def _make_hex_without_magic() -> bytes:
    blob = b"\x00" * 64
    lines: list[str] = []
    for i in range(0, len(blob), 16):
        lines.append(_hex_record(addr=i, record_type=0x00, data=blob[i : i + 16]))
    lines.append(_hex_record(addr=0, record_type=0x01, data=b""))
    return ("\n".join(lines) + "\n").encode("ascii")


def _write_hex_fixture(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, hex_bytes: bytes) -> tuple[dict, dict]:
    digest = sha256(hex_bytes).hexdigest()
    bucket = get_submissions_bucket()
    submission = {
        "id": "deadbeef-dead-beef-dead-beef0000aa01",
        "kind": "file",
        "text_body": None,
        "course_id": "course-1",
        "task_id": "task-1",
        "student_sub": "student-1",
    }

    storage_root = tmp_path / "storage"
    storage_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("STORAGE_VERIFY_ROOT", str(storage_root))

    storage_key = f"{bucket}/{submission['course_id']}/{submission['task_id']}/{submission['student_sub']}/project.hex"
    file_path = storage_root / storage_key
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(hex_bytes)

    job_payload = {
        "task_kind": "calliope",
        "mime_type": "application/x.makecode.hex",
        "storage_key": storage_key,
        "size_bytes": file_path.stat().st_size,
        "sha256": digest,
    }
    return submission, job_payload


def test_local_vision_makecode_hex_returns_evidence_markdown(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    hex_bytes = _make_hex_with_embedded_source(eurl="https://makecode.calliope.cc/#editor")
    submission, job_payload = _write_hex_fixture(monkeypatch, tmp_path, hex_bytes)

    import importlib

    mod = importlib.import_module("backend.learning.adapters.local_vision")
    adapter = mod.build()  # type: ignore[attr-defined]

    result: VisionResult = adapter.extract(submission=submission, job_payload=job_payload)
    assert isinstance(result, VisionResult)
    assert "makecode.evidence.v1" in result.text_md
    assert isinstance(result.raw_metadata, dict)
    assert result.raw_metadata.get("adapter") == "local_vision"


def test_local_vision_makecode_hex_missing_source_returns_fallback_evidence(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    submission, job_payload = _write_hex_fixture(monkeypatch, tmp_path, _make_hex_without_magic())

    import importlib

    mod = importlib.import_module("backend.learning.adapters.local_vision")
    adapter = mod.build()  # type: ignore[attr-defined]

    result: VisionResult = adapter.extract(submission=submission, job_payload=job_payload)

    assert "# makecode.evidence.v1" in result.text_md
    assert "extraction_status: source_unavailable" in result.text_md
    assert "extraction_error: missing_makecode_source" in result.text_md
    assert "### file:" not in result.text_md
    assert result.raw_metadata.get("soft_error_code") == "missing_makecode_source"


def test_local_vision_makecode_hex_invalid_file_returns_fallback_evidence(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    submission, job_payload = _write_hex_fixture(monkeypatch, tmp_path, b":00000001FE\n")

    import importlib

    mod = importlib.import_module("backend.learning.adapters.local_vision")
    adapter = mod.build()  # type: ignore[attr-defined]

    result: VisionResult = adapter.extract(submission=submission, job_payload=job_payload)

    assert "# makecode.evidence.v1" in result.text_md
    assert "extraction_status: source_unavailable" in result.text_md
    assert "extraction_error: invalid_hex_file" in result.text_md
    assert "### file:" not in result.text_md
    assert result.raw_metadata.get("soft_error_code") == "invalid_hex_file"


def test_local_vision_makecode_hex_invalid_file_stays_hard_for_non_calliope(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    submission, job_payload = _write_hex_fixture(monkeypatch, tmp_path, b":00000001FE\n")
    job_payload["task_kind"] = "native"

    import importlib

    mod = importlib.import_module("backend.learning.adapters.local_vision")
    adapter = mod.build()  # type: ignore[attr-defined]

    with pytest.raises(mod.VisionPermanentError) as exc:  # type: ignore[attr-defined]
        adapter.extract(submission=submission, job_payload=job_payload)
    assert str(exc.value) == "invalid_hex_file"
