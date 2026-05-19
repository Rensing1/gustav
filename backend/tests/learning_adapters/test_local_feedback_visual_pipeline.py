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
import struct
import zlib

import pytest
from PIL import Image, ImageOps

pytest.importorskip("psycopg")

from backend.learning.adapters.ports import FeedbackResult, TokenUsageEvent


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


def _transparent_png_bytes() -> bytes:
    image = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
    image.putpixel((1, 1), (0, 0, 0, 255))
    out = BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


def _png_header_bytes(*, width: int, height: int) -> bytes:
    def _chunk(chunk_type: bytes, payload: bytes) -> bytes:
        crc = zlib.crc32(chunk_type + payload) & 0xFFFFFFFF
        return struct.pack(">I", len(payload)) + chunk_type + payload + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr) + _chunk(b"IEND", b"")


class _ProviderRateLimitError(Exception):
    status_code = 429
    llm_provider = "provider.test"
    model = "visual-model"
    type = "rate_limited"
    code = "1300"


def _usage_event(event_key: str) -> TokenUsageEvent:
    return TokenUsageEvent(
        event_key=event_key,
        model="visual-model",
        stage="analysis",
        modality="visual",
        call_kind="primary",
        usage_known=True,
        input_tokens=7,
        output_tokens=3,
        total_tokens=10,
    )


class _ProviderRateLimitErrorWithUsage(_ProviderRateLimitError):
    def __init__(self, message: str, usage_events: list[TokenUsageEvent]) -> None:
        super().__init__(message)
        self.usage_events = usage_events


def test_provider_safe_jpeg_rendition_composites_transparency_on_white() -> None:
    mod = importlib.import_module("backend.learning.adapters.local_feedback")
    image_b64 = base64.b64encode(_transparent_png_bytes()).decode("ascii")

    fallback_b64 = mod._provider_safe_jpeg_rendition_b64(image_b64=image_b64)  # type: ignore[attr-defined]
    fallback_bytes = base64.b64decode(fallback_b64)

    with Image.open(BytesIO(fallback_bytes)) as image:
        assert image.format == "JPEG"
        rgb = image.convert("RGB")
        transparent_pixel = rgb.getpixel((0, 0))
        dark_stroke_pixel = rgb.getpixel((1, 1))
    assert min(transparent_pixel) >= 245
    assert max(dark_stroke_pixel) <= 40


def test_provider_safe_jpeg_rendition_rejects_large_pixel_count_before_decode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mod = importlib.import_module("backend.learning.adapters.local_feedback")
    image_b64 = base64.b64encode(_png_header_bytes(width=5000, height=5000)).decode("ascii")

    def _fail_if_transposed(image: object) -> object:
        raise AssertionError("large images must be rejected before EXIF transpose")

    monkeypatch.setattr(ImageOps, "exif_transpose", _fail_if_transposed)

    with pytest.raises(mod.FeedbackPermanentError) as exc:  # type: ignore[attr-defined]
        mod._provider_safe_jpeg_rendition_b64(image_b64=image_b64)  # type: ignore[attr-defined]

    assert str(exc.value) == "image_too_complex_for_provider"


def test_provider_image_diagnostics_include_jpeg_dimensions() -> None:
    mod = importlib.import_module("backend.learning.adapters.local_feedback")
    image_b64 = base64.b64encode(_jpeg_bytes()).decode("ascii")

    diagnostics = mod._provider_image_diagnostics(mime="image/jpeg", image_b64=image_b64)  # type: ignore[attr-defined]

    assert diagnostics["mime"] == "image/jpeg"
    assert diagnostics["bytes"] == len(_jpeg_bytes())
    assert diagnostics["base64_chars"] == len(image_b64)
    assert diagnostics["width"] == 1200
    assert diagnostics["height"] == 800
    assert diagnostics["pixels"] == 960000


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


def test_local_feedback_analyze_visual_retries_once_with_jpeg_rendition_after_original_429(
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

    storage_key = "submissions/course/task/student/handwritten.jpg"
    payload_bytes = _jpeg_bytes()
    target = tmp_path / storage_key
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload_bytes)
    sha = hashlib.sha256(payload_bytes).hexdigest()
    submission = {
        "id": "sub-jpeg-fallback",
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
    captured: list[str] = []

    def _fake_analyze_visual_feedback(*, image_data_uri: str, **_: object) -> FeedbackResult:
        captured.append(image_data_uri)
        if len(captured) == 1:
            raise _ProviderRateLimitError("rate_limited")
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
    assert len(captured) == 2
    assert captured[0].startswith("data:image/jpeg;base64,")
    assert base64.b64decode(captured[0].split(",", 1)[1]) == payload_bytes
    assert captured[1].startswith("data:image/jpeg;base64,")
    fallback_bytes = base64.b64decode(captured[1].split(",", 1)[1])
    assert fallback_bytes != payload_bytes
    with Image.open(BytesIO(fallback_bytes)) as image:
        assert image.format == "JPEG"
        assert max(image.size) <= 1280
        assert image.mode == "RGB"
    assert target.read_bytes() == payload_bytes


def test_local_feedback_analyze_visual_preserves_original_usage_events_when_fallback_succeeds(
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

    storage_key = "submissions/course/task/student/usage.jpg"
    payload_bytes = _jpeg_bytes()
    target = tmp_path / storage_key
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload_bytes)
    sha = hashlib.sha256(payload_bytes).hexdigest()
    submission = {
        "id": "sub-usage-fallback",
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

    original_event = _usage_event("original")
    fallback_event = _usage_event("fallback")
    prog = importlib.import_module("backend.learning.adapters.dspy.visual_feedback_program")
    calls: list[str] = []

    def _fake_analyze_visual_feedback(*, image_data_uri: str, **_: object) -> FeedbackResult:
        calls.append(image_data_uri)
        if len(calls) == 1:
            raise _ProviderRateLimitErrorWithUsage("rate_limited", [original_event])
        return FeedbackResult(
            feedback_md="OK",
            analysis_json={"schema": "criteria.v2", "score": 0, "criteria_results": []},
            parse_status="parsed_structured",
            usage_events=[fallback_event],
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

    assert res.usage_events == [original_event, fallback_event]


@pytest.mark.parametrize(
    ("mime_type", "filename", "payload_factory"),
    [
        ("image/png", "visual.png", _large_png_bytes),
        ("image/jpeg", "visual.jpg", _jpeg_bytes),
    ],
)
def test_local_feedback_analyze_visual_maps_fallback_rate_limit_to_complex_image(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    mime_type: str,
    filename: str,
    payload_factory,
) -> None:
    monkeypatch.setenv("STORAGE_VERIFY_ROOT", str(tmp_path))
    monkeypatch.setenv("OPENAI_BASE_URL", "http://example.test/api/v1")
    monkeypatch.setenv("AI_TEXT_MODEL", "text-model")
    monkeypatch.setenv("AI_VISUAL_MODEL", "visual-model")
    dspy_cache = tmp_path / "dspy_cache"
    dspy_cache.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("DSPY_CACHEDIR", str(dspy_cache))

    storage_key = f"submissions/course/task/student/{filename}"
    payload_bytes = payload_factory()
    target = tmp_path / storage_key
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload_bytes)
    sha = hashlib.sha256(payload_bytes).hexdigest()
    submission = {
        "id": "sub-double-429",
        "kind": "image",
        "mime_type": mime_type,
        "storage_key": storage_key,
        "size_bytes": len(payload_bytes),
        "sha256": sha,
        "course_id": "c",
        "task_id": "t",
        "student_sub": "s",
    }
    job_payload = {
        "mime_type": mime_type,
        "storage_key": storage_key,
        "size_bytes": len(payload_bytes),
        "sha256": sha,
    }

    prog = importlib.import_module("backend.learning.adapters.dspy.visual_feedback_program")
    calls: list[str] = []

    def _fake_analyze_visual_feedback(*, image_data_uri: str, **_: object) -> FeedbackResult:
        calls.append(image_data_uri)
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
    assert len(calls) == 2
    assert calls[0].startswith(f"data:{mime_type};base64,")
    assert calls[1].startswith("data:image/jpeg;base64,")
    assert target.read_bytes() == payload_bytes


def test_local_feedback_analyze_visual_preserves_usage_events_when_fallback_rate_limit_fails(
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

    storage_key = "submissions/course/task/student/double-usage.jpg"
    payload_bytes = _jpeg_bytes()
    target = tmp_path / storage_key
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload_bytes)
    sha = hashlib.sha256(payload_bytes).hexdigest()
    submission = {
        "id": "sub-double-usage",
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

    original_event = _usage_event("original")
    fallback_event = _usage_event("fallback")
    prog = importlib.import_module("backend.learning.adapters.dspy.visual_feedback_program")
    calls = 0

    def _fake_analyze_visual_feedback(**_: object) -> FeedbackResult:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise _ProviderRateLimitErrorWithUsage("rate_limited", [original_event])
        raise _ProviderRateLimitErrorWithUsage("rate_limited", [fallback_event])

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
    assert exc.value.usage_events == [original_event, fallback_event]


def test_local_feedback_analyze_visual_preserves_usage_events_when_rendition_pixel_limit_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("OPENAI_BASE_URL", "http://example.test/api/v1")
    monkeypatch.setenv("AI_TEXT_MODEL", "text-model")
    monkeypatch.setenv("AI_VISUAL_MODEL", "visual-model")
    dspy_cache = tmp_path / "dspy_cache"
    dspy_cache.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("DSPY_CACHEDIR", str(dspy_cache))

    image_b64 = base64.b64encode(_png_header_bytes(width=5000, height=5000)).decode("ascii")
    original_event = _usage_event("original")

    vision_mod = importlib.import_module("backend.learning.adapters.local_vision")
    monkeypatch.setattr(vision_mod, "_resolve_submission_image_bytes", lambda **_: image_b64)

    feedback_mod = importlib.import_module("backend.learning.adapters.local_feedback")

    def _fail_if_transposed(image: object) -> object:
        raise AssertionError("large images must be rejected before EXIF transpose")

    monkeypatch.setattr(ImageOps, "exif_transpose", _fail_if_transposed)

    prog = importlib.import_module("backend.learning.adapters.dspy.visual_feedback_program")
    calls: list[str] = []

    def _fake_analyze_visual_feedback(*, image_data_uri: str, **_: object) -> FeedbackResult:
        calls.append(image_data_uri)
        raise _ProviderRateLimitErrorWithUsage("rate_limited", [original_event])

    monkeypatch.setattr(prog, "analyze_visual_feedback", _fake_analyze_visual_feedback)

    adapter = feedback_mod.build()  # type: ignore[attr-defined]

    with pytest.raises(feedback_mod.FeedbackPermanentError) as exc:  # type: ignore[attr-defined]
        adapter.analyze_visual(  # type: ignore[attr-defined]
            submission={"id": "sub-large-pixels", "kind": "image", "mime_type": "image/png"},
            job_payload={"mime_type": "image/png"},
            criteria=["K1"],
            instruction_md="Aufgabe",
            teacher_context_md="Hinweis",
        )

    assert str(exc.value) == "image_too_complex_for_provider"
    assert exc.value.usage_events == [original_event]
    assert len(calls) == 1


def test_local_feedback_analyze_visual_classifies_complex_png_rate_limit(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    caplog.set_level("WARNING", logger="backend.learning.adapters.local_feedback")
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
    logs = "\n".join(record.getMessage() for record in caplog.records)
    assert "provider_error_type=rate_limited" in logs
    assert "provider_error_code=1300" in logs
    assert storage_key not in logs
    assert sha not in logs


def test_local_feedback_analyze_visual_retries_small_png_once_with_jpeg_rendition(
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
    calls: list[str] = []

    def _fake_analyze_visual_feedback(*, image_data_uri: str, **_: object) -> FeedbackResult:
        calls.append(image_data_uri)
        if len(calls) == 1:
            raise _ProviderRateLimitError("rate_limited")
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
    assert len(calls) == 2
    assert calls[0].startswith("data:image/png;base64,")
    assert calls[1].startswith("data:image/jpeg;base64,")


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
