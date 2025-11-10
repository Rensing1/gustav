"""
Unit tests for PDF page stitching into a single image.

KISS behavior:
- Vertically concatenate all page images without resizing.
- Output width equals the maximum page width.
- Output height equals the sum of page heights.
"""
from __future__ import annotations

from io import BytesIO
from PIL import Image

from backend.vision.pipeline import stitch_images_vertically


def _png_bytes(w: int, h: int, gray: int) -> bytes:
    im = Image.new("L", (w, h), color=gray)
    buf = BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def test_stitch_images_vertically_basic_dimensions():
    # Arrange: three pages of different heights and widths
    b1 = _png_bytes(20, 10, 50)   # top
    b2 = _png_bytes(25, 5, 150)   # middle (wider)
    b3 = _png_bytes(20, 7, 220)   # bottom

    # Act
    out = stitch_images_vertically([b1, b2, b3])

    # Assert: dimensions
    im = Image.open(BytesIO(out))
    assert im.width == 25
    assert im.height == 10 + 5 + 7

    # Spot check pixels in each band to ensure ordering
    assert im.getpixel((0, 0)) == 50          # top-left of first page
    assert im.getpixel((0, 10 + 0)) == 150    # start of second band
    assert im.getpixel((0, 10 + 5 + 0)) == 220  # start of third band

