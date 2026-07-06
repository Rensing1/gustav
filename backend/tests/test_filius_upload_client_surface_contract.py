"""
Filius upload client surface contract.

Intent:
    All upload entry points must map `.fls`/Filius tasks to the canonical FLS
    MIME type, not just the JSON API route.
"""

from __future__ import annotations

from pathlib import Path


def test_svelte_learning_page_maps_filius_uploads_to_fls_mime() -> None:
    source = Path(
        "frontend/src/routes/learning/courses/[courseId]/units/[unitId]/+page.svelte"
    ).read_text(encoding="utf-8")
    constants = Path("frontend/src/lib/utils/submission-mime-types.ts").read_text(encoding="utf-8")

    assert '"filius"' in source
    assert "return FILIUS_FLS_MIME;" in source
    assert 'FILIUS_FLS_MIME = "application/x.filius.fls"' in constants


def test_learning_api_upload_surface_maps_filius_uploads_to_fls_mime() -> None:
    source = Path("backend/web/routes/learning_submission_commands.py").read_text(encoding="utf-8")
    facade_source = Path("backend/web/routes/learning.py").read_text(encoding="utf-8")
    main_source = Path("backend/web/main.py").read_text(encoding="utf-8")

    assert "learning_submission_commands" in facade_source
    assert '"filius"' in source
    assert "FILIUS_FLS_MIME" in source
    assert "extract_configuration_xml_bytes" in source
    assert "def _server_side_prepare_submission_upload" not in main_source


def test_legacy_browser_upload_script_maps_filius_extension_and_error_copy() -> None:
    source = Path("backend/web/static/js/gustav.js").read_text(encoding="utf-8")

    assert "application/x.filius.fls" in source
    assert "lowerName.endsWith('.fls')" in source
    assert "Erlaubt ist nur .fls." in source
