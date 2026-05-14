"""
Unit test: local Feedback adapter supports Visual tasks via DSPy image pipeline.

Intent:
    - `analyze_visual(...)` must load the uploaded image from STORAGE_VERIFY_ROOT,
      convert it to a data-URI, and call the Visual DSPy program.
    - Keep the test deterministic by stubbing the DSPy program entry point.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import importlib
from io import BytesIO
from pathlib import Path
import random
import struct
import warnings
import zlib

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


def _large_transparent_png_bytes() -> bytes:
    out = BytesIO()
    image = Image.new("RGBA", (1400, 900), (0, 0, 0, 0))
    for x in range(600, 800):
        for y in range(400, 500):
            image.putpixel((x, y), (20, 20, 20, 255))
    image.save(out, format="PNG")
    return out.getvalue()


def _stitched_pdf_png_bytes(*, width: int = 2480, height: int = 7016) -> bytes:
    out = BytesIO()
    Image.new("L", (width, height), 255).save(out, format="PNG")
    return out.getvalue()


def _high_pixel_png_bytes(*, width: int = 5000, height: int = 4000) -> bytes:
    """Build a valid, tiny-on-disk PNG whose dimensions exceed the pixel budget."""

    def _chunk(kind: bytes, data: bytes) -> bytes:
        crc = binascii.crc32(kind + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", crc)

    # 1-bit grayscale keeps the compressed payload tiny while still expanding
    # to many pixels if a decoder loads the full raster.
    row = b"\x00" + (b"\x00" * ((width + 7) // 8))
    compressor = zlib.compressobj(level=9)
    compressed = BytesIO()
    for _ in range(height):
        compressed.write(compressor.compress(row))
    compressed.write(compressor.flush())

    return b"".join(
        [
            b"\x89PNG\r\n\x1a\n",
            _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 1, 0, 0, 0, 0)),
            _chunk(b"IDAT", compressed.getvalue()),
            _chunk(b"IEND", b""),
        ]
    )


def _jpeg_bytes() -> bytes:
    out = BytesIO()
    Image.new("RGB", (1200, 800), (240, 240, 240)).save(out, format="JPEG")
    return out.getvalue()


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


def test_local_feedback_analyze_visual_normalizes_large_png_for_provider(
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

    original_uri_length = len("data:image/png;base64," + base64.b64encode(payload_bytes).decode("ascii"))
    assert res.feedback_md == "OK"
    assert captured["uri"].startswith("data:image/jpeg;base64,")
    assert len(captured["uri"]) < original_uri_length

    normalized = base64.b64decode(captured["uri"].split(",", 1)[1])
    with Image.open(BytesIO(normalized)) as image:
        assert image.format == "JPEG"
        assert image.mode == "RGB"
        assert max(image.size) <= 1280


def test_local_feedback_analyze_visual_normalizes_stitched_pdf_png_for_provider(
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
    assert captured["uri"].startswith("data:image/jpeg;base64,")

    normalized = base64.b64decode(captured["uri"].split(",", 1)[1])
    with Image.open(BytesIO(normalized)) as image:
        assert image.format == "JPEG"
        assert image.mode == "RGB"
        assert max(image.size) <= 1280


def test_local_feedback_rejects_extreme_stitched_pdf_png_before_provider_normalization() -> None:
    """Extremely large PDF stitches stay bounded even though normal stitches can downscale."""

    mod = importlib.import_module("backend.learning.adapters.local_feedback")
    payload_b64 = base64.b64encode(_stitched_pdf_png_bytes(width=8000, height=9000)).decode("ascii")

    with pytest.raises(mod.FeedbackPermanentError) as exc:  # type: ignore[attr-defined]
        mod._normalize_png_for_provider(  # type: ignore[attr-defined]
            mime="image/png",
            image_b64=payload_b64,
            max_pixels=64_000_000,
        )

    assert str(exc.value) == "input_too_large"


def test_local_feedback_rejects_high_pixel_png_before_provider_normalization() -> None:
    """High-pixel PNGs must be rejected before full raster decoding can happen."""

    mod = importlib.import_module("backend.learning.adapters.local_feedback")
    payload_b64 = base64.b64encode(_high_pixel_png_bytes()).decode("ascii")

    with pytest.raises(mod.FeedbackPermanentError) as exc:  # type: ignore[attr-defined]
        mod._normalize_png_for_provider(mime="image/png", image_b64=payload_b64)  # type: ignore[attr-defined]

    assert str(exc.value) == "input_too_large"


def test_local_feedback_treats_decompression_bomb_warning_as_input_too_large() -> None:
    """Pillow decompression warnings promoted to errors must not bypass the size guard."""

    mod = importlib.import_module("backend.learning.adapters.local_feedback")
    payload_b64 = base64.b64encode(_high_pixel_png_bytes(width=12000, height=8000)).decode("ascii")

    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with pytest.raises(mod.FeedbackPermanentError) as exc:  # type: ignore[attr-defined]
            mod._normalize_png_for_provider(mime="image/png", image_b64=payload_b64)  # type: ignore[attr-defined]

    assert str(exc.value) == "input_too_large"


def test_local_feedback_composites_transparent_png_on_white_before_jpeg() -> None:
    """Transparent PNG backgrounds should stay readable after JPEG normalization."""

    mod = importlib.import_module("backend.learning.adapters.local_feedback")
    payload_b64 = base64.b64encode(_large_transparent_png_bytes()).decode("ascii")

    normalized_mime, normalized_b64 = mod._normalize_png_for_provider(  # type: ignore[attr-defined]
        mime="image/png",
        image_b64=payload_b64,
    )

    assert normalized_mime == "image/jpeg"
    normalized = base64.b64decode(normalized_b64)
    with Image.open(BytesIO(normalized)) as image:
        assert image.mode == "RGB"
        background = image.getpixel((10, 10))
        writing = image.getpixel((image.width // 2, image.height // 2))

    assert min(background) >= 240
    assert max(writing) <= 40


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
