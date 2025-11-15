"""
Helpers to generate standardized storage_key paths for Supabase Storage.

Why:
    Keep path shapes consistent across domains and provide simple, testable
    sanitization that avoids path traversal and exotic characters while
    remaining human-readable.

Conventions:
    - Teaching materials: materials/{unit}/{section}/{material}/{uuid}.{ext}
    - Learning submissions: submissions/{course}/{task}/{student}/{epoch_ms}-{uuid}.{ext}

Security:
    - Sanitization removes characters outside [A-Za-z0-9._-] from segments.
    - Filename extensions are lowercased and filtered to alphanumeric + dot.
"""
from __future__ import annotations

import os
import re
import unicodedata

_SEGMENT_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _sanitize_segment(value: str, *, fallback: str = "x") -> str:
    value = value or ""
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    sanitized = _SEGMENT_RE.sub("-", ascii_value).strip("-_.")
    return sanitized or fallback


def _sanitize_ext_from_filename(filename: str | None, default_ext: str = "") -> str:
    if not filename:
        ext = default_ext
    else:
        _, ext = os.path.splitext(os.path.basename(filename))
    ext = (ext or default_ext or "").lower()
    # keep only alnum and dots; collapse invalids
    ext = "".join(ch for ch in ext if ch.isalnum() or ch == ".")
    if ext and not ext.startswith("."):
        ext = f".{ext}"
    return ext


def make_materials_key(*, unit_id: str, section_id: str, material_id: str, filename: str, uuid_hex: str) -> str:
    """Build a storage key for teaching materials.

    Returns: materials/{unit}/{section}/{material}/{uuid}.{ext}
    """
    u = _sanitize_segment(unit_id, fallback="unit")
    s = _sanitize_segment(section_id, fallback="section")
    m = _sanitize_segment(material_id, fallback="material")
    ext = _sanitize_ext_from_filename(filename)
    hexpart = (uuid_hex or "").strip() or "file"
    return f"materials/{u}/{s}/{m}/{hexpart}{ext}"


def make_submission_key(*, course_id: str, task_id: str, student_sub: str, ext: str, epoch_ms: int, uuid_hex: str) -> str:
    """Build a storage key for learning submissions.

    Returns: submissions/{course}/{task}/{student}/{epoch_ms}-{uuid}.{ext}
    """
    c = _sanitize_segment(course_id, fallback="course")
    t = _sanitize_segment(task_id, fallback="task")
    stu = _sanitize_segment(student_sub, fallback="student")
    ext_norm = _sanitize_ext_from_filename(ext, default_ext=ext)
    hexpart = (uuid_hex or "").strip() or "file"
    return f"submissions/{c}/{t}/{stu}/{epoch_ms}-{hexpart}{ext_norm}"


__all__ = ["make_materials_key", "make_submission_key"]

