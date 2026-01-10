"""
OpenAPI contract: H5P debug pages are admin-only (embedded UI uses model endpoints).

Why:
    `/h5p/editor` and `/h5p/player` are standalone debug pages and must not be
    confused with the real in-platform integration. This test ensures the
    OpenAPI contract documents that distinction.
"""

from __future__ import annotations

from pathlib import Path

import yaml


def _load_spec() -> dict:
    root = Path(__file__).resolve().parents[2]
    return yaml.safe_load((root / "api" / "openapi.yml").read_text(encoding="utf-8"))


def test_h5p_debug_pages_documented_as_admin_only() -> None:
    spec = _load_spec()
    paths = spec.get("paths") or {}

    for path in ("/h5p/editor", "/h5p/player"):
        assert path in paths, f"missing {path} in openapi.yml"
        get_op = paths[path]["get"]
        assert get_op.get("security"), f"GET {path} must require authentication"

        summary = str(get_op.get("summary") or "").lower()
        assert "debug" in summary, f"Expected 'debug' in summary for {path}"
        assert "admin" in summary, f"Expected 'admin' in summary for {path}"

        notes = get_op.get("x-security-notes") or []
        if isinstance(notes, str):
            notes = [notes]
        assert any("admin" in str(n).lower() for n in notes), f"Expected admin-only note for {path}"

