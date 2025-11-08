"""
Vision adapter and minimal orchestration to extract markdown text.

Why:
    After rendering a PDF to page images, we need to obtain readable text for
    teachers and students. This module defines a tiny adapter contract for a
    Vision client and a helper that turns per-page images into a markdown
    transcript. Feedback generation is intentionally out-of-scope here.

Design:
    - `VisionClient` abstracts das Vision-Modell (z. B. Ollama) mit einer
      Methode `analyze_image(image_bytes)`, die Klartext liefert.
    - `extract_text_from_pages` calls the client once per page and produces a
      markdown document with simple page headings. Analysis metadata records
      page count and a source hint for observability.

Permissions:
    Dieses Modul arbeitet rein auf In‑Memory‑Bytes und trifft keine
    Autorisierungsentscheidungen. Aufrufer müssen Berechtigungen vorab prüfen.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Protocol

from backend.vision.pdf_renderer import RenderPage


class VisionClient(Protocol):
    """Minimal protocol for a Vision/OCR client."""

    def analyze_image(self, *, image_bytes: bytes) -> str: ...


class CompletionRepo(Protocol):
    """Port used (later) to mark a submission as completed with extracted text."""

    def mark_completed(self, *, submission_id: str, text_md: str, analysis_json: dict, feedback_md: str) -> None: ...


@dataclass(frozen=True)
class VisionExtractionResult:
    text_md: str
    analysis_json: dict


def extract_text_from_pages(*, pages: List[RenderPage], client: VisionClient) -> VisionExtractionResult:
    """Call the Vision client per page and return a markdown transcript.

    Behavior:
        - Invokes `client.analyze_image(image_bytes=...)` for every page.
        - Produces markdown with headings `## Page N` and the page text.
        - Returns analysis metadata with page count and a source hint.

    Returns:
        VisionExtractionResult with `text_md` and `analysis_json`.
    """
    sections: List[str] = []
    for idx, page in enumerate(pages, start=1):
        text = client.analyze_image(image_bytes=page.png_bytes)
        sections.append(f"## Page {idx}\n\n{text}\n")
    text_md = "\n\n".join(sections).strip()
    analysis = {"pages": len(pages), "source": "vision.ollama"}
    return VisionExtractionResult(text_md=text_md, analysis_json=analysis)


__all__ = [
    "VisionClient",
    "CompletionRepo",
    "VisionExtractionResult",
    "extract_text_from_pages",
]
