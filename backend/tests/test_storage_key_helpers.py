"""
Tests for storage_key helper functions to standardize path shapes.

TDD: These functions do not exist yet. We define expected behavior and
validate sanitization and structure for materials and submissions keys.
"""
from __future__ import annotations

import re


def test_make_materials_key_shape_and_sanitization():
    from backend.storage.keys import make_materials_key  # type: ignore

    key = make_materials_key(
        unit_id="unit-ÄÖ",
        section_id="sec 01",
        material_id="mat/..//id",
        filename="Prüfung 2025/Teil#1?.PDF",
        uuid_hex="deadbeef",
    )
    # Expected structure: materials/{unit}/{section}/{material}/{uuid}.ext
    assert key.startswith("materials/")
    parts = key.split("/")
    assert len(parts) == 5, key
    _, u, s, m, fname = parts
    # Sanitized path segments
    allowed_seg = re.compile(r"^[A-Za-z0-9._-]+$")
    assert allowed_seg.match(u)
    assert allowed_seg.match(s)
    assert allowed_seg.match(m)
    assert fname.startswith("deadbeef") and fname.endswith(".pdf")


def test_make_submission_key_shape_and_sanitization():
    from backend.storage.keys import make_submission_key  # type: ignore

    key = make_submission_key(
        course_id="course#1",
        task_id="task id",
        student_sub="student@example.com",
        ext=".JPG",
        epoch_ms=1700000000123,
        uuid_hex="cafebabe",
    )
    # Expected structure: submissions/{course}/{task}/{student}/{ts-uuid}{ext}
    assert key.startswith("submissions/")
    parts = key.split("/")
    assert len(parts) == 5, key
    _, c, t, stu, tail = parts
    allowed_seg = re.compile(r"^[A-Za-z0-9._-]+$")
    assert allowed_seg.match(c)
    assert allowed_seg.match(t)
    assert allowed_seg.match(stu)
    assert tail.endswith(".jpg")
    assert "cafebabe" in tail and "1700000000123" in tail

