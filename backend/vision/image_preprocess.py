"""
Minimal, dependency-light image preprocessing for document scans.

Pipeline (conservative):
- Ensure grayscale (mode "L").
- Optional median denoise to reduce salt-and-pepper noise.
- Optional global histogram equalization to enhance contrast.
- Optional binarization via Otsu threshold (fallback to fixed threshold).

Design:
- Keep pure-Pillow implementation to avoid heavy dependencies.
- Functions are deterministic and side-effect free.
"""

from typing import Optional
from PIL import Image, ImageFilter, ImageOps


def _to_grayscale(img: Image.Image) -> Image.Image:
    return img if img.mode == "L" else img.convert("L")


def _median_denoise(img: Image.Image, size: int = 3) -> Image.Image:
    # Use small kernel to avoid blurring edges too much
    return img.filter(ImageFilter.MedianFilter(size=size))


def _equalize(img: Image.Image) -> Image.Image:
    # Global equalization (CLAHE alternative without extra deps)
    return ImageOps.equalize(img)


def _otsu_threshold(img: Image.Image) -> int:
    # Compute Otsu threshold from histogram
    hist = img.histogram()  # 256 bins for L-mode
    total = sum(hist)
    sum_total = sum(i * h for i, h in enumerate(hist))
    sum_b = 0.0
    w_b = 0.0
    max_var = -1.0
    threshold = 127
    for t in range(256):
        w_b += hist[t]
        if w_b == 0:
            continue
        w_f = total - w_b
        if w_f == 0:
            break
        sum_b += t * hist[t]
        m_b = sum_b / w_b
        m_f = (sum_total - sum_b) / w_f
        between = w_b * w_f * ((m_b - m_f) ** 2)
        if between > max_var:
            max_var = between
            threshold = t
    return threshold


def _binarize(img: Image.Image, threshold: Optional[int] = None) -> Image.Image:
    if threshold is None:
        threshold = _otsu_threshold(img)
    # Map to 0/255
    return img.point(lambda p: 255 if p > threshold else 0, mode="1").convert("L")


def preprocess(
    img: Image.Image,
    *,
    denoise: bool = True,
    equalize: bool = True,
    binarize: bool = False,
) -> Image.Image:
    """Apply a conservative preprocessing pipeline to a document image.

    Parameters:
    - denoise: Apply small median filter to reduce salt-and-pepper noise.
    - equalize: Apply global histogram equalization to boost contrast.
    - binarize: Convert to black/white using Otsu thresholding.

    Returns a new grayscale image (mode "L").
    """
    out = _to_grayscale(img)
    if denoise:
        out = _median_denoise(out)
    if equalize:
        out = _equalize(out)
    if binarize:
        out = _binarize(out)
    return out

