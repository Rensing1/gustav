"""Learning upload content-signature validation.

These tests define the small shared byte gate used before persistence and as a
worker fallback. Deep Scratch/Filius/Calliope structure checks remain in their
specialized validators.
"""

from __future__ import annotations

from io import BytesIO
import zipfile

import pytest
from PIL import Image

from backend.storage.mime_types import FILIUS_FLS_MIME, JPEG_MIME, MAKECODE_HEX_MIME, PDF_MIME, PNG_MIME, SCRATCH_SB3_MIME


def _png_bytes() -> bytes:
    out = BytesIO()
    Image.new("RGB", (1, 1), (255, 0, 0)).save(out, format="PNG")
    return out.getvalue()


def _jpeg_bytes() -> bytes:
    out = BytesIO()
    Image.new("RGB", (1, 1), (0, 255, 0)).save(out, format="JPEG")
    return out.getvalue()


def _zip_bytes() -> bytes:
    out = BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("payload.txt", "ok")
    return out.getvalue()


@pytest.mark.parametrize(
    ("mime_type", "payload"),
    [
        (PNG_MIME, _png_bytes()),
        (JPEG_MIME, _jpeg_bytes()),
        (PDF_MIME, b"%PDF-1.7\n%test\n"),
        (SCRATCH_SB3_MIME, _zip_bytes()),
        (FILIUS_FLS_MIME, _zip_bytes()),
        (MAKECODE_HEX_MIME, b":00000001FF\n"),
    ],
)
def test_accepts_expected_content_signatures(mime_type: str, payload: bytes) -> None:
    from backend.storage.submission_content_signatures import validate_submission_content_signature

    validate_submission_content_signature(mime_type, payload)


@pytest.mark.parametrize("mime_type", [PNG_MIME, JPEG_MIME, PDF_MIME, MAKECODE_HEX_MIME])
def test_rejects_zip_bytes_for_non_zip_declared_mime(mime_type: str) -> None:
    from backend.storage.submission_content_signatures import validate_submission_content_signature

    with pytest.raises(ValueError, match="invalid_upload_content"):
        validate_submission_content_signature(mime_type, _zip_bytes())


def test_rejects_binary_bytes_declared_as_hex() -> None:
    from backend.storage.submission_content_signatures import validate_submission_content_signature

    with pytest.raises(ValueError, match="invalid_upload_content"):
        validate_submission_content_signature(MAKECODE_HEX_MIME, b"\x00\x01\x02\x03")
