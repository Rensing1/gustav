"""
Unit test: local Feedback adapter supports Visual tasks via DSPy image pipeline.

Intent:
    - `analyze_visual(...)` must load the uploaded image from STORAGE_VERIFY_ROOT,
      convert it to a data-URI, and call the Visual DSPy program.
    - Keep the test deterministic by stubbing the DSPy program entry point.
"""

from __future__ import annotations

import hashlib
import importlib
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

pytest.importorskip("psycopg")

from backend.learning.adapters.ports import FeedbackResult


def _png_bytes() -> bytes:
    out = BytesIO()
    Image.new("RGB", (1, 1), (255, 0, 0)).save(out, format="PNG")
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
