"""
PDF rendering and preprocessing pipeline (minimal TDD seed).

Intent:
- Convert uploaded PDFs into per-page images for downstream vision/OCR.
- Keep memory bounded by processing page-by-page.
- Provide sane defaults (300 DPI, grayscale, include annotations).

Security/Permissions:
- This module performs pure computation on provided bytes/paths. Callers must
  ensure the PDF originates from an authorized upload and is within policy.

Note:
- External dependencies (pypdfium2, Pillow) are optional. For tests, these can
  be mocked. At runtime, we attempt to import when used and raise a clear error
  if missing.
"""

from dataclasses import dataclass
from typing import Iterable, List, Optional


@dataclass
class RenderPage:
    index: int
    width: int
    height: int
    mode: str  # e.g., "L" for grayscale
    data: bytes  # encoded image bytes (e.g., PNG)


@dataclass
class RenderMeta:
    page_count: int
    dpi: int
    grayscale: bool
    used_annotations: bool


class PdfRenderError(Exception):
    pass


def _import_pdfium():
    try:
        import pypdfium2 as pdfium  # type: ignore
        return pdfium
    except Exception as exc:  # pragma: no cover - surfaced in tests via mocking
        raise PdfRenderError("pypdfium2 is required for PDF rendering") from exc



def render_pdf_to_images(
    pdf_bytes: bytes,
    *,
    dpi: int = 300,
    page_limit: int = 100,
    include_annotations: bool = True,
    grayscale: bool = True,
    preprocess=None,
) -> tuple[List[RenderPage], RenderMeta]:
    """Render a PDF (bytes) to per-page images with conservative defaults.

    - Processes pages sequentially to bound memory.
    - Applies grayscale conversion if requested.
    - Caps pages at `page_limit` for DoS protection.

    Returns (pages, meta) on success or raises PdfRenderError.
    """
    pdfium = _import_pdfium()
    # We do not hard-require Pillow import here because many pdfium bitmaps
    # expose to_pil() returning a Pillow-like object that supports convert/save.

    try:
        doc = pdfium.PdfDocument(pdf_bytes)
    except Exception as exc:
        raise PdfRenderError("failed_to_open_pdf") from exc

    total_pages = len(doc)
    max_pages = min(page_limit, total_pages)

    pages_out: List[RenderPage] = []

    # Convert target DPI to a scale factor (PDF default resolution is 72 DPI)
    try:
        scale = float(dpi) / 72.0
        if scale <= 0:
            scale = 1.0
    except Exception:
        scale = 4.1667  # ~300 DPI fallback

    for i in range(max_pages):
        try:
            page = doc[i]
            # pypdfium2 expects a scale factor; derive from DPI (72 base DPI)
            bitmap = page.render(
                scale=scale,
                draw_annots=bool(include_annotations),
            )
            pil = bitmap.to_pil()  # to Pillow Image
            if grayscale and pil.mode != "L":
                pil = pil.convert("L")
            if callable(preprocess):
                # Allow caller to run additional preprocessing (e.g., denoise/CLAHE/binarize)
                pil = preprocess(pil)
            # Encode to PNG bytes for transport/storage
            import io

            buf = io.BytesIO()
            pil.save(buf, format="PNG")
            data = buf.getvalue()
            pages_out.append(
                RenderPage(index=i, width=pil.width, height=pil.height, mode=pil.mode, data=data)
            )
        except Exception as exc:
            raise PdfRenderError(f"render_failed_on_page_{i}") from exc
        finally:
            try:
                # Explicit release if provided by mock/real objects
                del page
                del bitmap
                del pil
            except Exception:
                pass

    meta = RenderMeta(
        page_count=total_pages,
        dpi=dpi,
        grayscale=grayscale,
        used_annotations=include_annotations,
    )
    return pages_out, meta
