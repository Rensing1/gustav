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


def test_render_markdown_table_renders_table_elements():
    md = """|                | Familie Groborz | Familie Jensen |
|----------------|------------------|----------------|
| **Summe 2025** | 1.153 €          | 1.509 €        |"""
    html = render_markdown_safe(md)
    assert "<table" in html
    assert "<th>Familie Groborz</th>" in html
    assert "<th>Familie Jensen</th>" in html
    assert "<td>1.153 €</td>" in html
    assert "<td>1.509 €</td>" in html
    assert "<strong>Summe 2025</strong>" in html


def test_render_markdown_table_with_surrounding_text():
    md = """Vor der Tabelle

| Fach | Note |
|------|------|
| Mathe | 1 |
| Englisch | 2 |

Nach der Tabelle"""
    html = render_markdown_safe(md)
    assert "<p>Vor der Tabelle</p>" in html
    assert "<table" in html
    assert "<p>Nach der Tabelle</p>" in html
    assert html.index("<p>Vor der Tabelle</p>") < html.index("<table")
    assert html.index("<table") < html.index("<p>Nach der Tabelle</p>")


def test_render_markdown_table_escapes_html_in_cells():
    md = """| A | B |
|---|---|
| <script>alert('x')</script> | <img src=x onerror=alert('x')> |"""
    html = render_markdown_safe(md)
    assert "<table" in html
    assert "<script>" not in html
    assert "&lt;script&gt;alert('x')&lt;/script&gt;" in html
    assert "&lt;img src=x onerror=alert('x')&gt;" in html


def test_render_markdown_pipes_without_separator_render_as_text():
    md = "A | B | C\nD | E | F"
    html = render_markdown_safe(md)
    assert "<table" not in html
    assert "A | B | C" in html
    assert "D | E | F" in html
