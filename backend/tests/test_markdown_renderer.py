"""
Unit tests for the minimal markdown renderer.

Regression guard: headings must not be wrapped inside <p> tags, otherwise the
HTML becomes invalid and breaks layout/styling in MaterialCard/TaskCard.
"""
from __future__ import annotations

from backend.web.components.markdown import render_markdown_safe


def test_render_markdown_heading_not_wrapped_by_paragraph():
    html = render_markdown_safe("# Title\n\nRegular text")
    assert "<h1>Title</h1>" in html
    assert "<p><h1>Title</h1></p>" not in html
    assert "<p>Regular text</p>" in html
