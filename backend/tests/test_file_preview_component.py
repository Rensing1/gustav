"""
FilePreview component — markup and accessibility smoke tests.

Why:
    Ensure the reusable file preview component renders the expected wrapper
    attributes for JS-based zoom (data-file-preview) and basic keyboard
    accessibility (role, tabindex, aria-label) for both PDF and fallback
    download variants.
"""

from __future__ import annotations

from backend.web.components.file_preview import FilePreview


def test_file_preview_pdf_includes_zoom_and_accessibility_attrs() -> None:
    """PDF previews should expose zoom hooks and an accessible label."""
    html = FilePreview(
        url="http://example.test/file.pdf",
        mime="application/pdf",
        title="Arbeitsblatt",
    ).render()

    # Wrapper classes / attributes for JS zoom + keyboard interaction
    assert 'file-preview--pdf' in html
    assert 'data-file-preview="true"' in html
    assert 'role="button"' in html
    assert 'tabindex="0"' in html
    assert 'aria-pressed="false"' in html
    assert 'aria-expanded="false"' in html
    assert 'aria-label="Dateivorschau vergrößern/verkleinern"' in html
    # Embedded viewer element should be present
    assert '<iframe' in html


def test_file_preview_image_includes_zoom_and_accessibility_attrs() -> None:
    """Image previews should expose zoom hooks and an accessible label."""
    html = FilePreview(
        url="http://example.test/image.png",
        mime="image/png",
        title="Bildmaterial",
        alt="Alt-Text",
    ).render()

    # Wrapper classes / attributes for JS zoom + keyboard interaction
    assert 'file-preview--image' in html
    assert 'data-file-preview="true"' in html
    assert 'role="button"' in html
    assert 'tabindex="0"' in html
    assert 'aria-pressed="false"' in html
    assert 'aria-expanded="false"' in html
    assert 'aria-label="Dateivorschau vergrößern/verkleinern"' in html
    # Image element with alt text should be present
    assert '<img' in html
    assert 'alt="Alt-Text"' in html


def test_file_preview_download_fallback_wraps_link_with_zoom_hooks() -> None:
    """Unsupported MIME types fall back to a download link with the same wrapper."""
    html = FilePreview(
        url="http://example.test/file.bin",
        mime="application/octet-stream",
        title="Anhang",
    ).render()

    assert 'file-preview--download' in html
    assert 'data-file-preview="true"' in html
    assert 'role="button"' in html
    assert 'tabindex="0"' in html
    assert 'aria-pressed="false"' in html
    assert 'aria-expanded="false"' in html
    assert '<a ' in html and 'href="http://example.test/file.bin"' in html
