"""
Vision pipeline orchestration (minimal slice).

This module provides a thin, framework-agnostic use case to transform PDF
bytes into preprocessed per-page images suitable for downstream vision models.

Design goals:
- Keep pure functions and avoid IO; callers provide bytes and handle storage.
- Delegate rendering to pdf_renderer and preprocessing to image_preprocess.
"""

from __future__ import annotations

from typing import List, Tuple

from .pdf_renderer import RenderMeta, RenderPage, render_pdf_to_images
from .image_preprocess import preprocess as _preprocess


def process_pdf_bytes(pdf_bytes: bytes) -> Tuple[List[RenderPage], RenderMeta]:
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
    pages, meta = render_pdf_to_images(
        pdf_bytes,
        dpi=300,
        page_limit=100,
        include_annotations=True,
        grayscale=True,
        preprocess=lambda im: _preprocess(im, denoise=True, equalize=True, binarize=False),
    )
    return pages, meta

