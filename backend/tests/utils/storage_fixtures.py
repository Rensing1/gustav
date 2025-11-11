from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import List, Optional

from PIL import Image, ImageDraw

from backend.storage.config import get_submissions_bucket


def _generate_dummy_png_bytes() -> bytes:
    """
    Produce a small but well-formed PNG that survives Pillow decoding.

    We draw light/ dark bands to mimic handwriting so downstream OCR logic
    has predictable input during tests.
    """
    img = Image.new("L", (160, 220), color=245)
    draw = ImageDraw.Draw(img)
    for idx in range(0, img.height, 20):
        shade = 200 if (idx // 20) % 2 == 0 else 230
        draw.rectangle([(0, idx), (img.width, idx + 10)], fill=shade)
    draw.text((10, 10), "Test PDF Page", fill=30)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def write_dummy_png(path: Path) -> None:
    """Write a minimal PNG file to the given path (parents created automatically)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_generate_dummy_png_bytes())


def ensure_pdf_derivatives(
    *,
    root: Path,
    bucket: Optional[str] = None,
    course_id: str,
    task_id: str,
    student_sub: str,
    submission_id: str,
    page_count: int = 2,
) -> List[str]:
    """
    Create derived PDF artifacts (stitched + page PNGs) under STORAGE_VERIFY_ROOT.

    Returns the list of storage keys written (one per page) so tests can store them
    inside `internal_metadata -> page_keys`.
    """
    effective_bucket = (bucket or get_submissions_bucket()).strip() or get_submissions_bucket()
    derived_dir = (
        root
        / effective_bucket
        / course_id
        / task_id
        / student_sub
        / "derived"
        / submission_id
    )
    derived_dir.mkdir(parents=True, exist_ok=True)
    write_dummy_png(derived_dir / "stitched.png")
    keys: List[str] = []
    for idx in range(1, page_count + 1):
        key = f"{effective_bucket}/{course_id}/{task_id}/{student_sub}/derived/{submission_id}/page_{idx:04}.png"
        write_dummy_png(derived_dir / f"page_{idx:04}.png")
        keys.append(key)
    return keys


__all__ = ["write_dummy_png", "ensure_pdf_derivatives"]
