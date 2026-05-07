"""
Filius upload client surface contract.

Intent:
    All upload entry points must map `.fls`/Filius tasks to the canonical FLS
    MIME type, not just the JSON API route.
"""

from __future__ import annotations

from pathlib import Path


def test_svelte_learning_page_maps_filius_uploads_to_fls_mime() -> None:
    source = Path("frontend/src/routes/learning/courses/[courseId]/units/[unitId]/+page.svelte").read_text(encoding="utf-8")

    assert '"filius"' in source
    assert 'return "application/x.filius.fls";' in source


def test_legacy_ssr_upload_surface_maps_filius_uploads_to_fls_mime() -> None:
    source = Path("backend/web/main.py").read_text(encoding="utf-8")

    assert '"filius"' in source
    assert "application/x.filius.fls" in source
    assert "filename.lower().endswith(\".fls\")" in source


def test_legacy_browser_upload_script_maps_filius_extension_and_error_copy() -> None:
    source = Path("backend/web/static/js/gustav.js").read_text(encoding="utf-8")

    assert "application/x.filius.fls" in source
    assert "lowerName.endsWith('.fls')" in source
    assert "Erlaubt ist nur .fls." in source
