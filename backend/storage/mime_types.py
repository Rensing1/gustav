"""Shared MIME type constants for learning submission uploads.

Why:
    Upload policy, validation and worker routing must agree on the exact MIME
    strings. Keeping these values in one small module prevents drift without
    coupling validators to each other.
"""

from __future__ import annotations


PDF_MIME = "application/pdf"
PNG_MIME = "image/png"
JPEG_MIME = "image/jpeg"
SCRATCH_SB3_MIME = "application/x.scratch.sb3"
MAKECODE_HEX_MIME = "application/x.makecode.hex"
FILIUS_FLS_MIME = "application/x.filius.fls"

ALLOWED_IMAGE_MIME = frozenset({JPEG_MIME, PNG_MIME})
ALLOWED_FILE_MIME = frozenset({PDF_MIME, SCRATCH_SB3_MIME, MAKECODE_HEX_MIME, FILIUS_FLS_MIME})
DETERMINISTIC_EVIDENCE_FILE_MIME = frozenset({SCRATCH_SB3_MIME, MAKECODE_HEX_MIME, FILIUS_FLS_MIME})


__all__ = [
    "PDF_MIME",
    "PNG_MIME",
    "JPEG_MIME",
    "SCRATCH_SB3_MIME",
    "MAKECODE_HEX_MIME",
    "FILIUS_FLS_MIME",
    "ALLOWED_IMAGE_MIME",
    "ALLOWED_FILE_MIME",
    "DETERMINISTIC_EVIDENCE_FILE_MIME",
]
