"""
Unit test: local Feedback adapter supports Visual tasks via DSPy image pipeline.

Intent:
    - `analyze_visual(...)` must load the uploaded image from STORAGE_VERIFY_ROOT,
      convert it to a data-URI, and call the Visual DSPy program.
    - Keep the test deterministic by stubbing the DSPy program entry point.
"""

from __future__ import annotations

import base64
import hashlib
import importlib
from io import BytesIO
from pathlib import Path
import random

import pytest
from PIL import Image

pytest.importorskip("psycopg")

from backend.learning.adapters.ports import FeedbackResult


def _png_bytes() -> bytes:
    out = BytesIO()
    Image.new("RGB", (1, 1), (255, 0, 0)).save(out, format="PNG")
    return out.getvalue()


def _large_png_bytes() -> bytes:
    out = BytesIO()
    size = (1400, 900)
    pixels = random.Random(20260514).randbytes(size[0] * size[1] * 3)
    Image.frombytes("RGB", size, pixels).save(out, format="PNG")
    return out.getvalue()


def _stitched_pdf_png_bytes(*, width: int = 2480, height: int = 7016) -> bytes:
    out = BytesIO()
    Image.new("L", (width, height), 255).save(out, format="PNG")
    return out.getvalue()


def _jpeg_bytes() -> bytes:
    out = BytesIO()
    Image.new("RGB", (1200, 800), (240, 240, 240)).save(out, format="JPEG")
    return out.getvalue()


class _ProviderRateLimitError(Exception):
    status_code = 429
    llm_provider = "provider.test"
    model = "visual-model"


def test_local_feedback_analyze_visual_calls_visual_program(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("STORAGE_VERIFY_ROOT", str(tmp_path))
    monkeypatch.setenv("OPENAI_BASE_URL", "http://example.test/api/v1")
    monkeypatch.setenv("AI_TEXT_MODEL", "text-model")
    monkeypatch.setenv("AI_VISUAL_MODEL", "visual-model")
    # DSPy defaults to $HOME/.dspy_cache. In some CI/sandbox setups $HOME may be
    # read-only, so force a writable cache dir under pytest's tmp_path.
    dspy_cache = tmp_path / "dspy_cache"
    dspy_cache.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("DSPY_CACHEDIR", str(dspy_cache))

    storage_key = "submissions/course/task/student/visual.png"
    payload_bytes = _png_bytes()
    target = tmp_path / storage_key
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload_bytes)
    sha = hashlib.sha256(payload_bytes).hexdigest()

    submission = {
        "id": "sub-1",
        "kind": "image",
        "mime_type": "image/png",
        "storage_key": storage_key,
        "size_bytes": len(payload_bytes),
        "sha256": sha,
        # IDs used by PDF helpers (not needed for this image test)
        "course_id": "c",
        "task_id": "t",
        "student_sub": "s",
    }
    job_payload = {
        "mime_type": "image/png",
        "storage_key": storage_key,
        "size_bytes": len(payload_bytes),
        "sha256": sha,
    }

    prog = importlib.import_module("backend.learning.adapters.dspy.visual_feedback_program")

    captured: dict[str, str] = {}

    def _fake_analyze_visual_feedback(*, image_data_uri: str, **_: object) -> FeedbackResult:
        captured["uri"] = image_data_uri
        return FeedbackResult(
            feedback_md="OK",
            analysis_json={"schema": "criteria.v2", "score": 0, "criteria_results": []},
            parse_status="parsed_structured",
        )

    monkeypatch.setattr(prog, "analyze_visual_feedback", _fake_analyze_visual_feedback)

    mod = importlib.import_module("backend.learning.adapters.local_feedback")
    adapter = mod.build()  # type: ignore[attr-defined]

    res = adapter.analyze_visual(  # type: ignore[attr-defined]
        submission=submission,
        job_payload=job_payload,
        criteria=["K1"],
        instruction_md="Aufgabe",
        teacher_context_md="Hinweis",
    )

    assert res.feedback_md == "OK"
    assert captured["uri"].startswith("data:image/png;base64,")


def test_local_feedback_analyze_visual_keeps_large_png_unmodified_for_provider_diagnosis(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("STORAGE_VERIFY_ROOT", str(tmp_path))
    monkeypatch.setenv("OPENAI_BASE_URL", "http://example.test/api/v1")
    monkeypatch.setenv("AI_TEXT_MODEL", "text-model")
    monkeypatch.setenv("AI_VISUAL_MODEL", "visual-model")
    dspy_cache = tmp_path / "dspy_cache"
    dspy_cache.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("DSPY_CACHEDIR", str(dspy_cache))

    storage_key = "submissions/course/task/student/large-visual.png"
    payload_bytes = _large_png_bytes()
    target = tmp_path / storage_key
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload_bytes)
    sha = hashlib.sha256(payload_bytes).hexdigest()

    submission = {
        "id": "sub-large-png",
        "kind": "image",
        "mime_type": "image/png",
        "storage_key": storage_key,
        "size_bytes": len(payload_bytes),
        "sha256": sha,
        "course_id": "c",
        "task_id": "t",
        "student_sub": "s",
    }
    job_payload = {
        "mime_type": "image/png",
        "storage_key": storage_key,
        "size_bytes": len(payload_bytes),
        "sha256": sha,
    }

    prog = importlib.import_module("backend.learning.adapters.dspy.visual_feedback_program")
    captured: dict[str, str] = {}

    def _fake_analyze_visual_feedback(*, image_data_uri: str, **_: object) -> FeedbackResult:
        captured["uri"] = image_data_uri
        return FeedbackResult(
            feedback_md="OK",
            analysis_json={"schema": "criteria.v2", "score": 0, "criteria_results": []},
            parse_status="parsed_structured",
        )

    monkeypatch.setattr(prog, "analyze_visual_feedback", _fake_analyze_visual_feedback)

    mod = importlib.import_module("backend.learning.adapters.local_feedback")
    adapter = mod.build()  # type: ignore[attr-defined]

    res = adapter.analyze_visual(  # type: ignore[attr-defined]
        submission=submission,
        job_payload=job_payload,
        criteria=["K1"],
        instruction_md="Aufgabe",
        teacher_context_md="Hinweis",
    )

    assert res.feedback_md == "OK"
    assert captured["uri"].startswith("data:image/png;base64,")
    assert base64.b64decode(captured["uri"].split(",", 1)[1]) == payload_bytes


def test_local_feedback_analyze_visual_classifies_complex_png_rate_limit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("STORAGE_VERIFY_ROOT", str(tmp_path))
    monkeypatch.setenv("OPENAI_BASE_URL", "http://example.test/api/v1")
    monkeypatch.setenv("AI_TEXT_MODEL", "text-model")
    monkeypatch.setenv("AI_VISUAL_MODEL", "visual-model")
    dspy_cache = tmp_path / "dspy_cache"
    dspy_cache.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("DSPY_CACHEDIR", str(dspy_cache))

    storage_key = "submissions/course/task/student/desktop-screenshot.png"
    payload_bytes = _large_png_bytes()
    target = tmp_path / storage_key
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload_bytes)
    sha = hashlib.sha256(payload_bytes).hexdigest()

    submission = {
        "id": "sub-complex-png",
        "kind": "image",
        "mime_type": "image/png",
        "storage_key": storage_key,
        "size_bytes": len(payload_bytes),
        "sha256": sha,
        "course_id": "c",
        "task_id": "t",
        "student_sub": "s",
    }
    job_payload = {
        "mime_type": "image/png",
        "storage_key": storage_key,
        "size_bytes": len(payload_bytes),
        "sha256": sha,
    }

    prog = importlib.import_module("backend.learning.adapters.dspy.visual_feedback_program")

    def _fake_analyze_visual_feedback(**_: object) -> FeedbackResult:
        raise _ProviderRateLimitError("rate_limited")

    monkeypatch.setattr(prog, "analyze_visual_feedback", _fake_analyze_visual_feedback)

    mod = importlib.import_module("backend.learning.adapters.local_feedback")
    adapter = mod.build()  # type: ignore[attr-defined]

    with pytest.raises(mod.FeedbackPermanentError) as exc:  # type: ignore[attr-defined]
        adapter.analyze_visual(  # type: ignore[attr-defined]
            submission=submission,
            job_payload=job_payload,
            criteria=["K1"],
            instruction_md="Aufgabe",
            teacher_context_md="Hinweis",
        )

    assert str(exc.value) == "image_too_complex_for_provider"


def test_local_feedback_analyze_visual_keeps_small_png_rate_limit_transient(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("STORAGE_VERIFY_ROOT", str(tmp_path))
    monkeypatch.setenv("OPENAI_BASE_URL", "http://example.test/api/v1")
    monkeypatch.setenv("AI_TEXT_MODEL", "text-model")
    monkeypatch.setenv("AI_VISUAL_MODEL", "visual-model")
    dspy_cache = tmp_path / "dspy_cache"
    dspy_cache.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("DSPY_CACHEDIR", str(dspy_cache))

    storage_key = "submissions/course/task/student/small.png"
    payload_bytes = _png_bytes()
    target = tmp_path / storage_key
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload_bytes)
    sha = hashlib.sha256(payload_bytes).hexdigest()

    submission = {
        "id": "sub-small-png",
        "kind": "image",
        "mime_type": "image/png",
        "storage_key": storage_key,
        "size_bytes": len(payload_bytes),
        "sha256": sha,
        "course_id": "c",
        "task_id": "t",
        "student_sub": "s",
    }
    job_payload = {
        "mime_type": "image/png",
        "storage_key": storage_key,
        "size_bytes": len(payload_bytes),
        "sha256": sha,
    }

    prog = importlib.import_module("backend.learning.adapters.dspy.visual_feedback_program")

    def _fake_analyze_visual_feedback(**_: object) -> FeedbackResult:
        raise _ProviderRateLimitError("rate_limited")

    monkeypatch.setattr(prog, "analyze_visual_feedback", _fake_analyze_visual_feedback)

    mod = importlib.import_module("backend.learning.adapters.local_feedback")
    adapter = mod.build()  # type: ignore[attr-defined]

    with pytest.raises(mod.FeedbackTransientError) as exc:  # type: ignore[attr-defined]
        adapter.analyze_visual(  # type: ignore[attr-defined]
            submission=submission,
            job_payload=job_payload,
            criteria=["K1"],
            instruction_md="Aufgabe",
            teacher_context_md="Hinweis",
        )

    assert str(exc.value) == "provider_rate_limited"


def test_local_feedback_analyze_visual_keeps_stitched_pdf_png_out_of_rate_limit_normalization(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("OPENAI_BASE_URL", "http://example.test/api/v1")
    monkeypatch.setenv("AI_TEXT_MODEL", "text-model")
    monkeypatch.setenv("AI_VISUAL_MODEL", "visual-model")
    dspy_cache = tmp_path / "dspy_cache"
    dspy_cache.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("DSPY_CACHEDIR", str(dspy_cache))

    stitched_png = _stitched_pdf_png_bytes()
    submission = {
        "id": "sub-pdf",
        "kind": "file",
        "mime_type": "application/pdf",
        "storage_key": "submissions/course/task/student/visual.pdf",
        "size_bytes": 1024,
        "sha256": "a" * 64,
        "course_id": "c",
        "task_id": "t",
        "student_sub": "s",
    }
    job_payload = {
        "mime_type": "application/pdf",
        "storage_key": submission["storage_key"],
        "size_bytes": submission["size_bytes"],
        "sha256": submission["sha256"],
    }

    vision_mod = importlib.import_module("backend.learning.adapters.local_vision")

    def _fake_stitched_png(self: object, *, submission: dict, job_payload: dict) -> bytes:
        return stitched_png

    monkeypatch.setattr(vision_mod._LocalVisionAdapter, "_ensure_pdf_stitched_png", _fake_stitched_png)

    prog = importlib.import_module("backend.learning.adapters.dspy.visual_feedback_program")
    captured: dict[str, str] = {}

    def _fake_analyze_visual_feedback(*, image_data_uri: str, **_: object) -> FeedbackResult:
        captured["uri"] = image_data_uri
        return FeedbackResult(
            feedback_md="OK",
            analysis_json={"schema": "criteria.v2", "score": 0, "criteria_results": []},
            parse_status="parsed_structured",
        )

    monkeypatch.setattr(prog, "analyze_visual_feedback", _fake_analyze_visual_feedback)

    mod = importlib.import_module("backend.learning.adapters.local_feedback")
    adapter = mod.build()  # type: ignore[attr-defined]

    res = adapter.analyze_visual(  # type: ignore[attr-defined]
        submission=submission,
        job_payload=job_payload,
        criteria=["K1"],
        instruction_md="Aufgabe",
        teacher_context_md="Hinweis",
    )

    assert res.feedback_md == "OK"
    assert captured["uri"].startswith("data:image/png;base64,")
    assert base64.b64decode(captured["uri"].split(",", 1)[1]) == stitched_png


def test_local_feedback_analyze_visual_keeps_jpeg_for_provider(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("STORAGE_VERIFY_ROOT", str(tmp_path))
    monkeypatch.setenv("OPENAI_BASE_URL", "http://example.test/api/v1")
    monkeypatch.setenv("AI_TEXT_MODEL", "text-model")
    monkeypatch.setenv("AI_VISUAL_MODEL", "visual-model")
    dspy_cache = tmp_path / "dspy_cache"
    dspy_cache.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("DSPY_CACHEDIR", str(dspy_cache))

    storage_key = "submissions/course/task/student/visual.jpg"
    payload_bytes = _jpeg_bytes()
    target = tmp_path / storage_key
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload_bytes)
    sha = hashlib.sha256(payload_bytes).hexdigest()

    submission = {
        "id": "sub-jpeg",
        "kind": "image",
        "mime_type": "image/jpeg",
        "storage_key": storage_key,
        "size_bytes": len(payload_bytes),
        "sha256": sha,
        "course_id": "c",
        "task_id": "t",
        "student_sub": "s",
    }
    job_payload = {
        "mime_type": "image/jpeg",
        "storage_key": storage_key,
        "size_bytes": len(payload_bytes),
        "sha256": sha,
    }

    prog = importlib.import_module("backend.learning.adapters.dspy.visual_feedback_program")
    captured: dict[str, str] = {}

    def _fake_analyze_visual_feedback(*, image_data_uri: str, **_: object) -> FeedbackResult:
        captured["uri"] = image_data_uri
        return FeedbackResult(
            feedback_md="OK",
            analysis_json={"schema": "criteria.v2", "score": 0, "criteria_results": []},
            parse_status="parsed_structured",
        )

    monkeypatch.setattr(prog, "analyze_visual_feedback", _fake_analyze_visual_feedback)

    mod = importlib.import_module("backend.learning.adapters.local_feedback")
    adapter = mod.build()  # type: ignore[attr-defined]

    res = adapter.analyze_visual(  # type: ignore[attr-defined]
        submission=submission,
        job_payload=job_payload,
        criteria=["K1"],
        instruction_md="Aufgabe",
        teacher_context_md="Hinweis",
    )

    assert res.feedback_md == "OK"
    assert captured["uri"].startswith("data:image/jpeg;base64,")


def test_local_feedback_analyze_visual_rejects_wrong_image_content(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("STORAGE_VERIFY_ROOT", str(tmp_path))
    monkeypatch.setenv("OPENAI_BASE_URL", "http://example.test/api/v1")
    monkeypatch.setenv("AI_TEXT_MODEL", "text-model")
    monkeypatch.setenv("AI_VISUAL_MODEL", "visual-model")
    dspy_cache = tmp_path / "dspy_cache"
    dspy_cache.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("DSPY_CACHEDIR", str(dspy_cache))

    storage_key = "submissions/course/task/student/visual.png"
    payload_bytes = b"PK\x03\x04not-a-png"
    target = tmp_path / storage_key
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload_bytes)
    sha = hashlib.sha256(payload_bytes).hexdigest()

    submission = {
        "id": "sub-wrong",
        "kind": "image",
        "mime_type": "image/png",
        "storage_key": storage_key,
        "size_bytes": len(payload_bytes),
        "sha256": sha,
        "course_id": "c",
        "task_id": "t",
        "student_sub": "s",
    }
    job_payload = {
        "mime_type": "image/png",
        "storage_key": storage_key,
        "size_bytes": len(payload_bytes),
        "sha256": sha,
    }

    mod = importlib.import_module("backend.learning.adapters.local_feedback")
    adapter = mod.build()  # type: ignore[attr-defined]

    with pytest.raises(mod.FeedbackPermanentError) as exc:  # type: ignore[attr-defined]
        adapter.analyze_visual(  # type: ignore[attr-defined]
            submission=submission,
            job_payload=job_payload,
            criteria=["K1"],
            instruction_md="Aufgabe",
            teacher_context_md="Hinweis",
        )

    assert "invalid_upload_content" in str(exc.value)
