"""
Safe Markdown renderer for student-facing UI with table support.

Why:
- Keep rendering predictable and secure while supporting common markdown patterns
  teachers use in materials (headings, emphasis, tables).

Security model:
- Let a markdown parser build the HTML (with HTML input disabled).
- Sanitize the output via a small whitelist so only known-safe tags remain.
"""
from __future__ import annotations

from markdown_it import MarkdownIt
import bleach


_ALLOWED_TAGS = [
    "p",
    "br",
    "strong",
    "em",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "table",
    "thead",
    "tbody",
    "tr",
    "th",
    "td",
    "ul",
    "ol",
    "li",
    "code",
    "pre",
    "blockquote",
    "a",
]

_ALLOWED_ATTRIBUTES = {
    "a": ["href", "title"],
}

_ALLOWED_PROTOCOLS = ["http", "https", "mailto"]

# Parser configuration:
# - html=False: do not render raw HTML from input.
# - linkify=False: avoid auto-linking plain URLs.
# - typographer=False: keep output deterministic (no auto smart quotes).
# - breaks=True: keep single newlines as <br> similar to previous behaviour.
_MD = MarkdownIt(
    "commonmark",
    {
        "html": False,
        "linkify": False,
        "typographer": False,
        "breaks": True,
    },
).enable("table")


def render_markdown_safe(src: str) -> str:
    """Render teacher-authored markdown to safe HTML for students.

    Why:
        - Students should see formatted text (headings, emphasis, tables) without
          exposing them to XSS via untrusted input.
    Parameters:
        src: Raw markdown string (may be empty).
    Returns:
        Sanitised HTML limited to a small whitelist of tags (headings, emphasis,
        paragraphs, lists, tables). Raw HTML in the source is treated as text.
    Permissions:
        - Caller must already have ensured the viewer may see the content
          (e.g., section is released to the course); this helper performs no auth.
    """
    if not src:
        return ""

    # Parse markdown to HTML with tables enabled and HTML input disabled.
    html = _MD.render(str(src))

    # Sanitize to a minimal whitelist to keep XSS surface small.
    cleaned = bleach.clean(
        html,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRIBUTES,
        protocols=_ALLOWED_PROTOCOLS,
        strip=False,
    )
    return cleaned.strip()
