"""
Vision pipeline orchestration (minimal slice).

This module provides a thin, framework-agnostic use case to transform PDF
bytes into preprocessed per-page images suitable for downstream vision models.

Design goals:
- Keep pure functions and avoid IO; callers provide bytes and handle storage.
- Delegate rendering to pdf_renderer and preprocessing to image_preprocess.
"""

from __future__ import annotations

from typing import List, Tuple, TYPE_CHECKING
from io import BytesIO
from PIL import Image
from . import pdf_renderer as _pdf

if TYPE_CHECKING:  # only for type checkers; avoid import-time coupling in tests
    from .pdf_renderer import RenderMeta, RenderPage  # pragma: no cover

from .pdf_renderer import RenderMeta, RenderPage, render_pdf_to_images
from .image_preprocess import preprocess as _preprocess


def process_pdf_bytes(pdf_bytes: bytes) -> Tuple[List["RenderPage"], "RenderMeta"]:
    """Convert PDF bytes to preprocessed page images with sane defaults.

    Intent:
        Render each page at 300 DPI, convert to grayscale, and apply
        light preprocessing (median denoise + equalization). Binarization is
        left to downstream consumers based on task type.

    Permissions:
        None here. The caller is responsible for authorization and for ensuring
        the bytes originate from an allowed, verified upload.

    Returns:
        (pages, meta) where pages contain PNG-encoded image bytes and dimensions.
    """
    pages, meta = _pdf.render_pdf_to_images(
        pdf_bytes,
        dpi=300,
        page_limit=100,
        include_annotations=True,
        grayscale=True,
        preprocess=lambda im: _preprocess(im, denoise=True, equalize=True, binarize=False),
    )
    return pages, meta


def stitch_images_vertically(pages_png: List[bytes]) -> bytes:
    """Concatenate PNG page images vertically into a single PNG (KISS).

    Intent:
        Produce one image by stacking all pages top-to-bottom. We do not
        resize, pad minimally with white for narrower pages, and keep mode "L"
        (grayscale) when possible.

    Parameters:
        pages_png: List of PNG-encoded page images (potentially different widths).

    Returns:
        PNG-encoded bytes of the stitched image.
    """
    if not pages_png:
        # Return a minimal 1x1 white pixel PNG to avoid downstream errors.
        img = Image.new("L", (1, 1), color=255)
        buf = BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    # Load images and normalize to grayscale (L)
    ims: List[Image.Image] = []
    for b in pages_png:
        im = Image.open(BytesIO(b))
        if im.mode != "L":
            im = im.convert("L")
        ims.append(im)

    max_w = max(i.width for i in ims)
    total_h = sum(i.height for i in ims)

    canvas = Image.new("L", (max_w, total_h), color=255)
    y = 0
    for im in ims:
        canvas.paste(im, (0, y))
        y += im.height

    out = BytesIO()
    canvas.save(out, format="PNG")
    return out.getvalue()
