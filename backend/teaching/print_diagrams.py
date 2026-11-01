"""Prepare authorized print Markdown for the shared diagram renderer."""

from __future__ import annotations

import base64

from markdown_it import MarkdownIt

from backend.diagram_renderer import DiagramRenderError, diagram_key, render_sources
from backend.teaching.printouts import PrintExportError, PrintPolicy

_PARSER = MarkdownIt("commonmark", {"html": False})


def collect_diagrams(document: object) -> list[dict[str, str]]:
    """Read explicit fences from the authorized print model, never raw HTML."""
    found: dict[str, str] = {}
    for node in document.get("nodes", []):
        for item in node.get("items", []):
            for token in _PARSER.parse(str(item.get("body_md") or "")):
                if token.type == "fence" and token.info.strip().split(maxsplit=1)[:1] == [
                    "mermaid"
                ]:
                    found[diagram_key(token.content)] = token.content
    return [{"id": key, "source": source} for key, source in found.items()]


def render_diagrams(
    document: object, *, deadline: float, policy: PrintPolicy
) -> dict[str, bytes | None]:
    """Keep the existing PDF failure contract and pass only checked bytes to layout."""
    definitions = collect_diagrams(document)
    try:
        results = render_sources(
            [item["source"] for item in definitions],
            deadline=deadline,
            max_output_bytes=policy.max_output_bytes,
        )
    except DiagramRenderError as exc:
        code = "pdf_render_timeout" if exc.code == "render_timeout" else "pdf_renderer_unavailable"
        raise PrintExportError(code, 503) from exc
    return {
        item["id"]: base64.b64decode(result["png"]) if "png" in result else None
        for item, result in zip(definitions, results, strict=True)
    }
