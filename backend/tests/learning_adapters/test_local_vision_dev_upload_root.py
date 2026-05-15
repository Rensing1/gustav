"""
Learning vision adapter — local dev upload root parity.

Why:
    The upload API and the learning worker must resolve the same local
    validation root. Otherwise uploads written by the dev upload stub can pass
    API validation but become invisible to the worker.
"""

from __future__ import annotations

import base64
import hashlib
import importlib
import sys
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

pytest.importorskip("psycopg")

from backend.learning.workers.process_learning_submission_jobs import VisionResult  # type: ignore
from backend.storage.config import get_submissions_bucket
from backend.tests.utils.storage_fixtures import dummy_png_bytes


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


def test_image_uses_dev_upload_stub_root_when_storage_verify_root_is_unset(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("STORAGE_VERIFY_ROOT", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.setenv("ENABLE_DEV_UPLOAD_STUB", "true")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://example/api/v1")
    monkeypatch.setenv("AI_OCR_MODEL", "ocr-model")

    observed: dict = {}
    _install_fake_dspy(monkeypatch, observed=observed)

    bucket = get_submissions_bucket()
    storage_key = f"{bucket}/course-1/task-1/student-1/image.png"
    png = dummy_png_bytes()
    upload_file = tmp_path / ".tmp" / "dev_uploads" / storage_key
    upload_file.parent.mkdir(parents=True, exist_ok=True)
    upload_file.write_bytes(png)

    module = importlib.reload(importlib.import_module("backend.learning.adapters.local_vision"))
    from backend.learning.adapters.dspy import vision_program

    captured: dict = {}

    def _fake_extract(*, image_data_uri: str):  # type: ignore[no-untyped-def]
        captured["image_data_uri"] = image_data_uri
        return ("## OCR\n\nBildtext", {"program": "vision_ocr"})

    monkeypatch.setattr(vision_program, "extract_text_from_image", _fake_extract, raising=False)

    adapter = module.build()  # type: ignore[attr-defined]
    submission = {
        "id": "deadbeef-dead-beef-dead-beef000123",
        "kind": "file",
        "mime_type": "image/png",
        "storage_key": storage_key,
    }
    job_payload = {
        "mime_type": "image/png",
        "storage_key": storage_key,
        "size_bytes": len(png),
        "sha256": hashlib.sha256(png).hexdigest(),
    }

    result: VisionResult = adapter.extract(submission=submission, job_payload=job_payload)

    assert isinstance(result, VisionResult)
    data_uri = str(captured["image_data_uri"])
    assert data_uri.startswith("data:image/png;base64,")
    assert base64.b64decode(data_uri.split(",", 1)[1]) == png
    assert result.raw_metadata.get("bytes_read") == len(png)
