"""
Minimal, safe Markdown renderer for student-facing UI.

Why:
- Avoid external dependencies and keep rendering predictable and secure.
- Only support a small subset needed for materials and task instructions.

Security model:
- Escape the input first to neutralize any HTML.
- Replace simple markdown patterns with corresponding tags we control.
- Supported: headings (#..######), strong (**text**), emphasis (*text*),
  and paragraphs. Newlines inside a paragraph become <br>.
"""
from __future__ import annotations

from html import escape as _escape
import re


_RE_HEADING = re.compile(r"^(#{1,6})\s+(.+)$", flags=re.MULTILINE)
_RE_STRONG = re.compile(r"\*\*(.+?)\*\*")
_RE_EM = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")


def _render_inline(text: str) -> str:
    # strong first, then em to avoid overlapping markers
    text = _RE_STRONG.sub(r"<strong>\1</strong>", text)
    text = _RE_EM.sub(r"<em>\1</em>", text)
    return text


def render_markdown_safe(src: str) -> str:
    """Render a tiny markdown subset to safe HTML.

    Parameters:
        src: Raw markdown string. May be empty.

    Returns:
        Safe HTML string containing only tags we emit.

    Notes:
        - This function is intentionally small. Extend carefully as needed.
    """
    if not src:
        return ""

    # Escape everything first for safety
    escaped = _escape(str(src))

    # Headings at line start
    def _h(m: re.Match[str]) -> str:
        level = min(len(m.group(1)), 6)
        inner = _render_inline(m.group(2))
        return f"<h{level}>{inner}</h{level}>"

    with_headings = _RE_HEADING.sub(_h, escaped)

    # Split into paragraphs on blank lines
    paragraphs = [p for p in re.split(r"\n\s*\n", with_headings) if p.strip()]
    rendered_parts: list[str] = []
    for p in paragraphs:
        # Convert single newlines to <br>
        p = p.replace("\n", "<br>")
        rendered_parts.append(f"<p>{_render_inline(p)}</p>")

    return "".join(rendered_parts)

