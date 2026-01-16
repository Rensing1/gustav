"""
Unit tests for the local Vision adapter (DSPy-only OCR).

Intent:
    Drive a minimal implementation via TDD:
      - Happy path for JPEG/PNG/PDF returns Markdown and metadata.
      - Timeouts are classified as transient errors.
      - Unsupported MIME types are classified as permanent errors.

Notes:
    We stub DSPy and the vision program to avoid network/model dependencies.
"""

from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("psycopg")

from backend.learning.workers.process_learning_submission_jobs import (  # type: ignore
    VisionPermanentError,
    VisionResult,
    VisionTransientError,
)
from backend.storage.config import get_submissions_bucket
from backend.tests.utils.storage_fixtures import ensure_pdf_derivatives, write_dummy_png


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


@pytest.mark.parametrize("mime", ["image/jpeg", "image/png", "application/pdf"])
def test_local_vision_happy_path_returns_markdown(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    mime: str,
) -> None:
    observed: dict = {}
    _install_fake_dspy(monkeypatch, observed=observed)
    monkeypatch.setenv("OPENAI_BASE_URL", "http://example/api/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("AI_OCR_MODEL", "ocr-model")
    monkeypatch.setenv("AI_OCR_TEMPERATURE", "0.0")

    from backend.learning.adapters.dspy import vision_program

    monkeypatch.setattr(
        vision_program,
        "extract_text_from_image",
        lambda **_: ("## OCR\n\nErkannter Text", {"program": "vision_ocr"}),
    )

    import importlib

    mod = importlib.import_module("backend.learning.adapters.local_vision")
    adapter = mod.build()  # type: ignore[attr-defined]

    bucket = get_submissions_bucket()
    submission = {
        "id": "deadbeef-dead-beef-dead-beef000001",
        "kind": "file",
        "text_body": None,
        "course_id": "course-1",
        "task_id": "task-1",
        "student_sub": "student-1",
    }
    storage_root = tmp_path / "storage"
    storage_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("STORAGE_VERIFY_ROOT", str(storage_root))

    if mime in {"image/jpeg", "image/png"}:
        ext = "jpg" if mime == "image/jpeg" else "png"
        storage_key = (
            f"{bucket}/{submission['course_id']}/{submission['task_id']}/{submission['student_sub']}/img.{ext}"
        )
        file_path = storage_root / storage_key
        file_path.parent.mkdir(parents=True, exist_ok=True)
        if mime == "image/jpeg":
            file_path.write_bytes(b"\xff\xd8\xff" + b"x" * 16)
        else:
            write_dummy_png(file_path)
        job_payload = {
            "mime_type": mime,
            "storage_key": storage_key,
            "size_bytes": file_path.stat().st_size,
        }
    else:
        storage_key = (
            f"{bucket}/{submission['course_id']}/{submission['task_id']}/{submission['student_sub']}/orig/sample.pdf"
        )
        ensure_pdf_derivatives(
            root=storage_root,
            bucket=bucket,
            course_id=submission["course_id"],
            task_id=submission["task_id"],
            student_sub=submission["student_sub"],
            submission_id=submission["id"],
            page_count=2,
        )
        job_payload = {
            "mime_type": mime,
            "storage_key": storage_key,
            "size_bytes": 4096,
        }

    result: VisionResult = adapter.extract(submission=submission, job_payload=job_payload)
    assert isinstance(result, VisionResult)
    assert isinstance(result.text_md, str) and len(result.text_md.strip()) > 0
    # Metadata should indicate a local adapter for observability.
    assert isinstance(result.raw_metadata, dict)
    assert result.raw_metadata.get("adapter") == "local_vision"
    assert result.raw_metadata.get("backend") == "dspy"
    assert result.raw_metadata.get("program") == "vision_ocr"

    lm_calls = observed.get("lm_calls") or []
    assert lm_calls, "Expected OCR LM to be instantiated"
    assert lm_calls[0]["model"] == "openai/ocr-model"
    assert lm_calls[0]["kwargs"].get("base_url") == "http://example/api/v1"

    contexts = observed.get("contexts") or []
    assert contexts and contexts[0].get("disable_history") is True


def test_local_vision_timeout_is_transient(monkeypatch: pytest.MonkeyPatch) -> None:
    observed: dict = {}
    _install_fake_dspy(monkeypatch, observed=observed)
    monkeypatch.setenv("OPENAI_BASE_URL", "http://example/api/v1")
    monkeypatch.setenv("AI_OCR_MODEL", "ocr-model")

    from backend.learning.adapters.dspy import vision_program

    def _timeout(**_kwargs):  # type: ignore[no-untyped-def]
        raise TimeoutError("simulated timeout")

    monkeypatch.setattr(vision_program, "extract_text_from_image", _timeout)

    import importlib

    mod = importlib.import_module("backend.learning.adapters.local_vision")
    adapter = mod.build()  # type: ignore[attr-defined]

    from backend.storage.config import get_submissions_bucket

    bucket = get_submissions_bucket()
    submission = {"id": "deadbeef-dead-beef-dead-beef000002", "kind": "file"}
    # Ensure local bytes exist so the adapter reaches the model call.
    import tempfile
    from pathlib import Path as _Path

    root = _Path(tempfile.mkdtemp(prefix="gustav-test-vision-"))
    monkeypatch.setenv("STORAGE_VERIFY_ROOT", str(root))
    storage_key = f"{bucket}/course/task/student/img.jpg"
    file_path = root / storage_key
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(b"\xff\xd8\xff" + b"x" * 16)
    job_payload = {
        "mime_type": "image/jpeg",
        "storage_key": storage_key,
        "size_bytes": file_path.stat().st_size,
    }

    with pytest.raises(VisionTransientError, match="timeout"):
        adapter.extract(submission=submission, job_payload=job_payload)


def test_local_vision_unsupported_mime_is_permanent(monkeypatch: pytest.MonkeyPatch) -> None:
    observed: dict = {}
    _install_fake_dspy(monkeypatch, observed=observed)

    import importlib

    mod = importlib.import_module("backend.learning.adapters.local_vision")
    adapter = mod.build()  # type: ignore[attr-defined]

    submission = {"id": "deadbeef-dead-beef-dead-beef000003", "kind": "file"}
    job_payload = {"mime_type": "application/zip", "storage_key": "files/ghi789"}

    with pytest.raises(VisionPermanentError):
        adapter.extract(submission=submission, job_payload=job_payload)


def test_local_vision_requires_openai_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    observed: dict = {}
    _install_fake_dspy(monkeypatch, observed=observed)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.setenv("AI_OCR_MODEL", "ocr-model")

    import importlib

    mod = importlib.import_module("backend.learning.adapters.local_vision")
    importlib.reload(mod)

    adapter = mod.build()  # type: ignore[attr-defined]

    from backend.storage.config import get_submissions_bucket

    bucket = get_submissions_bucket()
    # Ensure bytes exist so config validation is reached.
    import tempfile
    from pathlib import Path as _Path

    root = _Path(tempfile.mkdtemp(prefix="gustav-test-vision-"))
    monkeypatch.setenv("STORAGE_VERIFY_ROOT", str(root))
    storage_key = f"{bucket}/course/task/student/img.png"
    file_path = root / storage_key
    file_path.parent.mkdir(parents=True, exist_ok=True)
    write_dummy_png(file_path)
    job_payload = {"mime_type": "image/png", "storage_key": storage_key, "size_bytes": file_path.stat().st_size}

    with pytest.raises(VisionTransientError, match="missing_OPENAI_BASE_URL"):
        adapter.extract(submission={"id": "s", "kind": "file"}, job_payload=job_payload)  # type: ignore[arg-type]


def test_local_vision_requires_ocr_model(monkeypatch: pytest.MonkeyPatch) -> None:
    observed: dict = {}
    _install_fake_dspy(monkeypatch, observed=observed)
    monkeypatch.setenv("OPENAI_BASE_URL", "http://example/api/v1")
    monkeypatch.delenv("AI_OCR_MODEL", raising=False)

    import importlib

    mod = importlib.import_module("backend.learning.adapters.local_vision")
    importlib.reload(mod)

    adapter = mod.build()  # type: ignore[attr-defined]

    from backend.storage.config import get_submissions_bucket

    bucket = get_submissions_bucket()
    import tempfile
    from pathlib import Path as _Path

    root = _Path(tempfile.mkdtemp(prefix="gustav-test-vision-"))
    monkeypatch.setenv("STORAGE_VERIFY_ROOT", str(root))
    storage_key = f"{bucket}/course/task/student/img.png"
    file_path = root / storage_key
    file_path.parent.mkdir(parents=True, exist_ok=True)
    write_dummy_png(file_path)
    job_payload = {"mime_type": "image/png", "storage_key": storage_key, "size_bytes": file_path.stat().st_size}

    with pytest.raises(VisionTransientError, match="missing_AI_OCR_MODEL"):
        adapter.extract(submission={"id": "s", "kind": "file"}, job_payload=job_payload)  # type: ignore[arg-type]


def test_local_vision_prod_disallows_http_openai_base_url_for_remote_hosts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    observed: dict = {}
    _install_fake_dspy(monkeypatch, observed=observed)

    monkeypatch.setenv("GUSTAV_ENV", "prod")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://example.com/api/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("AI_OCR_MODEL", "ocr-model")

    from backend.learning.adapters.dspy import vision_program

    monkeypatch.setattr(
        vision_program,
        "extract_text_from_image",
        lambda **_: ("## OCR\n\nErkannter Text", {"program": "vision_ocr"}),
    )

    import importlib

    mod = importlib.import_module("backend.learning.adapters.local_vision")
    adapter = mod.build()  # type: ignore[attr-defined]

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

    storage_key = f"{bucket}/{submission['course_id']}/{submission['task_id']}/{submission['student_sub']}/img.png"
    file_path = storage_root / storage_key
    file_path.parent.mkdir(parents=True, exist_ok=True)
    write_dummy_png(file_path)
    job_payload = {"mime_type": "image/png", "storage_key": storage_key, "size_bytes": file_path.stat().st_size}

    with pytest.raises(VisionPermanentError, match="insecure_OPENAI_BASE_URL"):
        adapter.extract(submission=submission, job_payload=job_payload)


def test_local_vision_prod_allows_http_openai_base_url_for_loopback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    observed: dict = {}
    _install_fake_dspy(monkeypatch, observed=observed)

    monkeypatch.setenv("GUSTAV_ENV", "prod")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://127.0.0.1:11434/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("AI_OCR_MODEL", "ocr-model")

    from backend.learning.adapters.dspy import vision_program

    monkeypatch.setattr(
        vision_program,
        "extract_text_from_image",
        lambda **_: ("## OCR\n\nErkannter Text", {"program": "vision_ocr"}),
    )

    import importlib

    mod = importlib.import_module("backend.learning.adapters.local_vision")
    adapter = mod.build()  # type: ignore[attr-defined]

    bucket = get_submissions_bucket()
    submission = {
        "id": "deadbeef-dead-beef-dead-beef000100",
        "kind": "file",
        "text_body": None,
        "course_id": "course-1",
        "task_id": "task-1",
        "student_sub": "student-1",
    }
    storage_root = tmp_path / "storage"
    storage_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("STORAGE_VERIFY_ROOT", str(storage_root))

    storage_key = f"{bucket}/{submission['course_id']}/{submission['task_id']}/{submission['student_sub']}/img.png"
    file_path = storage_root / storage_key
    file_path.parent.mkdir(parents=True, exist_ok=True)
    write_dummy_png(file_path)
    job_payload = {"mime_type": "image/png", "storage_key": storage_key, "size_bytes": file_path.stat().st_size}

    result = adapter.extract(submission=submission, job_payload=job_payload)
    assert isinstance(result, VisionResult)

    lm_calls = observed.get("lm_calls") or []
    assert lm_calls, "Expected OCR LM to be instantiated"
    assert lm_calls[0]["kwargs"]["base_url"] == "http://127.0.0.1:11434/v1"


def test_local_vision_prod_allows_http_openai_base_url_for_host_docker_internal(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    observed: dict = {}
    _install_fake_dspy(monkeypatch, observed=observed)

    monkeypatch.setenv("GUSTAV_ENV", "prod")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://host.docker.internal:8111/api/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("AI_OCR_MODEL", "ocr-model")

    from backend.learning.adapters.dspy import vision_program

    monkeypatch.setattr(
        vision_program,
        "extract_text_from_image",
        lambda **_: ("## OCR\n\nErkannter Text", {"program": "vision_ocr"}),
    )

    import importlib

    mod = importlib.import_module("backend.learning.adapters.local_vision")
    adapter = mod.build()  # type: ignore[attr-defined]

    bucket = get_submissions_bucket()
    submission = {
        "id": "deadbeef-dead-beef-dead-beef000101",
        "kind": "file",
        "text_body": None,
        "course_id": "course-1",
        "task_id": "task-1",
        "student_sub": "student-1",
    }
    storage_root = tmp_path / "storage"
    storage_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("STORAGE_VERIFY_ROOT", str(storage_root))

    storage_key = f"{bucket}/{submission['course_id']}/{submission['task_id']}/{submission['student_sub']}/img.png"
    file_path = storage_root / storage_key
    file_path.parent.mkdir(parents=True, exist_ok=True)
    write_dummy_png(file_path)
    job_payload = {"mime_type": "image/png", "storage_key": storage_key, "size_bytes": file_path.stat().st_size}

    result = adapter.extract(submission=submission, job_payload=job_payload)
    assert isinstance(result, VisionResult)

    lm_calls = observed.get("lm_calls") or []
    assert lm_calls, "Expected OCR LM to be instantiated"
    assert lm_calls[0]["kwargs"]["base_url"] == "http://host.docker.internal:8111/api/v1"


def test_local_vision_prod_allows_http_openai_base_url_for_private_ip(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    observed: dict = {}
    _install_fake_dspy(monkeypatch, observed=observed)

    monkeypatch.setenv("GUSTAV_ENV", "prod")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://10.0.0.23:11434/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("AI_OCR_MODEL", "ocr-model")

    from backend.learning.adapters.dspy import vision_program

    monkeypatch.setattr(
        vision_program,
        "extract_text_from_image",
        lambda **_: ("## OCR\n\nErkannter Text", {"program": "vision_ocr"}),
    )

    import importlib

    mod = importlib.import_module("backend.learning.adapters.local_vision")
    adapter = mod.build()  # type: ignore[attr-defined]

    bucket = get_submissions_bucket()
    submission = {
        "id": "deadbeef-dead-beef-dead-beef000102",
        "kind": "file",
        "text_body": None,
        "course_id": "course-1",
        "task_id": "task-1",
        "student_sub": "student-1",
    }
    storage_root = tmp_path / "storage"
    storage_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("STORAGE_VERIFY_ROOT", str(storage_root))

    storage_key = f"{bucket}/{submission['course_id']}/{submission['task_id']}/{submission['student_sub']}/img.png"
    file_path = storage_root / storage_key
    file_path.parent.mkdir(parents=True, exist_ok=True)
    write_dummy_png(file_path)
    job_payload = {"mime_type": "image/png", "storage_key": storage_key, "size_bytes": file_path.stat().st_size}

    result = adapter.extract(submission=submission, job_payload=job_payload)
    assert isinstance(result, VisionResult)

    lm_calls = observed.get("lm_calls") or []
    assert lm_calls, "Expected OCR LM to be instantiated"
    assert lm_calls[0]["kwargs"]["base_url"] == "http://10.0.0.23:11434/v1"


def test_local_vision_sanitizes_unexpected_errors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """
    Security regression: do not propagate raw exception messages (may contain PII).
    """
    observed: dict = {}
    _install_fake_dspy(monkeypatch, observed=observed)
    monkeypatch.setenv("OPENAI_BASE_URL", "http://example/api/v1")
    monkeypatch.setenv("AI_OCR_MODEL", "ocr-model")

    from backend.learning.adapters.dspy import vision_program

    def _boom(**_kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("studentPII: leaked payload")

    monkeypatch.setattr(vision_program, "extract_text_from_image", _boom)

    import importlib

    mod = importlib.import_module("backend.learning.adapters.local_vision")
    adapter = mod.build()  # type: ignore[attr-defined]

    bucket = get_submissions_bucket()
    storage_root = tmp_path / "storage"
    storage_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("STORAGE_VERIFY_ROOT", str(storage_root))

    storage_key = f"{bucket}/course/task/student/img.jpg"
    file_path = storage_root / storage_key
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(b"\xff\xd8\xff" + b"x" * 16)

    submission = {"id": "s", "kind": "file"}
    job_payload = {
        "mime_type": "image/jpeg",
        "storage_key": storage_key,
        "size_bytes": file_path.stat().st_size,
    }

    with pytest.raises(VisionTransientError) as exc:
        adapter.extract(submission=submission, job_payload=job_payload)
    assert str(exc.value) == "vision_failed"
