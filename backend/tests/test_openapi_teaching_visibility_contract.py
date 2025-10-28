"""
OpenAPI contract: Teaching visibility patch declares Cache-Control headers and CSRF note.
"""
from __future__ import annotations

from pathlib import Path
import yaml


def test_teaching_visibility_patch_has_cache_and_csrf_note():
    root = Path(__file__).resolve().parents[2]
    spec = yaml.safe_load((root / "api" / "openapi.yml").read_text(encoding="utf-8"))
    path = "/api/teaching/courses/{course_id}/modules/{module_id}/sections/{section_id}/visibility"
    assert path in spec["paths"], "visibility path missing in openapi.yml"
    op = spec["paths"][path]["patch"]
    # Security notes include CSRF
    notes = op.get("x-security-notes", []) or []
    assert any("CSRF" in str(n) for n in notes), "CSRF note missing in x-security-notes"
    # 200 includes Cache-Control header example
    h200 = (op.get("responses", {}).get("200", {}).get("headers", {}) or {}).get("Cache-Control")
    assert h200 is not None and h200.get("schema", {}).get("example") == "private, no-store"
    # 403 also includes Cache-Control header
    h403 = (op.get("responses", {}).get("403", {}).get("headers", {}) or {}).get("Cache-Control")
    assert h403 is not None and h403.get("schema", {}).get("example") == "private, no-store"

