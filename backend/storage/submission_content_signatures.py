"""Byte-signature checks for learning submission uploads.

Why:
    Browser MIME types and file extensions are not trustworthy. Before a
    submission is persisted or a worker spends feedback budget, the stored bytes
    must at least match the declared upload family.
"""

from __future__ import annotations

from io import BytesIO
import string

from backend.storage.mime_types import FILIUS_FLS_MIME, JPEG_MIME, MAKECODE_HEX_MIME, PDF_MIME, PNG_MIME, SCRATCH_SB3_MIME

_ZIP_MAGIC = (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")
_PRINTABLE_BYTES = set((string.printable + "\r\n\t").encode("ascii"))


def _invalid() -> None:
    raise ValueError("invalid_upload_content")


def _verify_image(data: bytes, *, expected_format: str) -> None:
    try:
        from PIL import Image

        with Image.open(BytesIO(data)) as image:
            if str(image.format or "").upper() != expected_format:
                _invalid()
            image.verify()
    except ValueError:
        raise
    except Exception:
        _invalid()


def _is_text_like(data: bytes) -> bool:
    if not data:
        return False
    sample = data[:4096]
    if b"\x00" in sample:
        return False
    return all(byte in _PRINTABLE_BYTES for byte in sample)


def validate_submission_content_signature(mime_type: str, data: bytes) -> None:
    """Validate that stored bytes match the declared learning upload MIME.

    Parameters:
        mime_type: Declared MIME type already accepted by the upload policy.
        data: Stored object bytes loaded by the API route or worker.
    Behavior:
        Raises `ValueError("invalid_upload_content")` for deterministic
        mismatches. Unknown MIME types are ignored so the existing allowlists
        remain the source of truth for accepted upload types.
    """

    mime = str(mime_type or "").strip().lower()
    payload = bytes(data or b"")
    if not payload:
        _invalid()

    if mime == PNG_MIME:
        if not payload.startswith(b"\x89PNG\r\n\x1a\n"):
            _invalid()
        _verify_image(payload, expected_format="PNG")
        return

    if mime == JPEG_MIME:
        if not payload.startswith(b"\xff\xd8\xff"):
            _invalid()
        _verify_image(payload, expected_format="JPEG")
        return

    if mime == PDF_MIME:
        if not payload.startswith(b"%PDF-"):
            _invalid()
        return

    if mime in {SCRATCH_SB3_MIME, FILIUS_FLS_MIME}:
        if not payload.startswith(_ZIP_MAGIC):
            _invalid()
        return

    if mime == MAKECODE_HEX_MIME:
        if payload.startswith(_ZIP_MAGIC) or not _is_text_like(payload):
            _invalid()
        return


__all__ = ["validate_submission_content_signature"]
