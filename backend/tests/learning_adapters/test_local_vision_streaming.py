"""
Unit tests for Vision adapter: streaming from storage + validation.

Why:
    Ensure the local Vision adapter verifies storage-backed inputs before
    calling the model and streams bytes safely (no path escape), with strict
    MIME/size/hash checks.

Design:
    - Uses a temporary directory as STORAGE_VERIFY_ROOT.
    - Builds files at a nested storage_key path and computes sha256.
    - Asserts: happy path returns VisionResult and records bytes_read in meta.
    - Asserts: size/hash/missing-file issues raise VisionPermanentError.

Notes:
    We stub DSPy + the vision program to avoid network/model dependencies.
    Text submissions skip storage validation entirely to keep the flow consistent.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import sys
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

pytest.importorskip("psycopg")

from backend.learning.workers.process_learning_submission_jobs import (  # type: ignore
    VisionPermanentError,
    VisionResult,
)


def _install_fake_dspy(monkeypatch: pytest.MonkeyPatch, *, observed: dict) -> None:
    class _FakeLM:
        def __init__(self, model: str, **kwargs) -> None:
            observed.setdefault("lm_calls", []).append({"model": model, "kwargs": dict(kwargs)})

    class _FakeJSONAdapter:
        pass

    @contextmanager
    def _ctx(**kwargs):  # type: ignore[no-untyped-def]
        observed.setdefault("contexts", []).append(dict(kwargs))
        yield

    monkeypatch.setitem(
        sys.modules,
        "dspy",
        SimpleNamespace(
            __version__="0.0-test",
            LM=_FakeLM,
            JSONAdapter=_FakeJSONAdapter,
            context=_ctx,
        ),
    )


def _write_file(root: Path, storage_key: str, data: bytes) -> tuple[int, str, Path]:
    target = (root / storage_key)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    size = target.stat().st_size
    h = hashlib.sha256(data).hexdigest()
    return size, h, target


def _build_adapter(monkeypatch: pytest.MonkeyPatch):
    observed: dict = {}
    _install_fake_dspy(monkeypatch, observed=observed)
    monkeypatch.setenv("OPENAI_BASE_URL", "http://example/api/v1")
    monkeypatch.setenv("AI_OCR_MODEL", "ocr-model")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_PUBLIC_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

    from backend.learning.adapters.dspy import vision_program

    monkeypatch.setattr(
        vision_program,
        "extract_text_from_image",
        lambda **_: ("# OCR\n\ntext from bytes", {"program": "vision_ocr"}),
    )
    import importlib

    mod = importlib.import_module("backend.learning.adapters.local_vision")
    return mod.build()  # type: ignore[attr-defined]


def test_stream_happy_path_validates_and_sets_meta(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    os.environ["STORAGE_VERIFY_ROOT"] = str(tmp_path)
    adapter = _build_adapter(monkeypatch)

    # Prepare file content
    storage_key = "submissions/course/task/student/2025-11-04/img-1.jpg"
    size, sha, _ = _write_file(tmp_path, storage_key, b"hello world\n")

    submission = {"id": "11111111-1111-1111-1111-111111111111", "kind": "file"}
    job_payload = {
        "mime_type": "image/jpeg",
        "storage_key": storage_key,
        "size_bytes": size,
        "sha256": sha,
    }

    res: VisionResult = adapter.extract(submission=submission, job_payload=job_payload)
    assert isinstance(res, VisionResult)
    assert res.text_md.strip().startswith("# ")
    assert isinstance(res.raw_metadata, dict)
    # Adapter should expose how many bytes were read for observability
    assert res.raw_metadata.get("bytes_read") == size
    assert res.raw_metadata.get("program") == "vision_ocr"


def test_stream_size_mismatch_is_permanent(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    os.environ["STORAGE_VERIFY_ROOT"] = str(tmp_path)
    adapter = _build_adapter(monkeypatch)

    storage_key = "submissions/x/y/z/file.pdf"
    size, sha, _ = _write_file(tmp_path, storage_key, b"abc")

    submission = {"id": "22222222-2222-2222-2222-222222222222", "kind": "file"}
    job_payload = {
        "mime_type": "application/pdf",
        "storage_key": storage_key,
        "size_bytes": size + 1,  # wrong size
        "sha256": sha,
    }

    with pytest.raises(VisionPermanentError):
        adapter.extract(submission=submission, job_payload=job_payload)


def test_stream_hash_mismatch_is_permanent(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    os.environ["STORAGE_VERIFY_ROOT"] = str(tmp_path)
    adapter = _build_adapter(monkeypatch)

    storage_key = "submissions/a/b/c/file.png"
    size, sha, _ = _write_file(tmp_path, storage_key, b"payload")

    submission = {"id": "33333333-3333-3333-3333-333333333333", "kind": "file"}
    job_payload = {
        "mime_type": "image/png",
        "storage_key": storage_key,
        "size_bytes": size,
        "sha256": "0" * 64,  # wrong hash
    }

    with pytest.raises(VisionPermanentError):
        adapter.extract(submission=submission, job_payload=job_payload)


def test_stream_missing_file_is_transient(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    os.environ["STORAGE_VERIFY_ROOT"] = str(tmp_path)
    adapter = _build_adapter(monkeypatch)

    storage_key = "submissions/missing/file.jpg"

    submission = {"id": "44444444-4444-4444-4444-444444444444", "kind": "file"}
    job_payload = {
        "mime_type": "image/jpeg",
        "storage_key": storage_key,
        "size_bytes": 10,
        "sha256": "f" * 64,
    }

    from backend.learning.workers.process_learning_submission_jobs import VisionTransientError  # type: ignore

    with pytest.raises(VisionTransientError):
        adapter.extract(submission=submission, job_payload=job_payload)


def test_text_submission_skips_storage_validation(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    os.environ["STORAGE_VERIFY_ROOT"] = str(tmp_path)
    adapter = _build_adapter(monkeypatch)

    submission = {
        "id": "55555555-5555-5555-5555-555555555555",
        "kind": "text",
        "text_body": "Meine Lösung als Text.",
    }
    job_payload = {"mime_type": "", "storage_key": "", "size_bytes": None, "sha256": ""}

    res: VisionResult = adapter.extract(submission=submission, job_payload=job_payload)
    assert isinstance(res, VisionResult)
    assert "Meine Lösung" in res.text_md
