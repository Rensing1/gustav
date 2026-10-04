"""Closed policy for safe teaching-material file types.

Why:
    Upload clients report MIME types inconsistently for classroom project files.
    GUSTAV therefore derives one canonical MIME type from the filename extension
    and validates the client value against it. Only PDF and raster images may be
    rendered inline; every program and OpenDocument file is download-only.
"""

from __future__ import annotations

from pathlib import PurePath

MATERIAL_FILE_MIME_BY_EXTENSION: dict[str, str] = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".sb3": "application/x.scratch.sb3",
    ".hex": "application/x.makecode.hex",
    ".fls": "application/x.filius.fls",
    ".py": "text/x-python",
    ".json": "application/json",
    ".txt": "text/plain",
    ".odt": "application/vnd.oasis.opendocument.text",
    ".ods": "application/vnd.oasis.opendocument.spreadsheet",
    ".odp": "application/vnd.oasis.opendocument.presentation",
}

INLINE_PREVIEW_MIME_TYPES = frozenset({"application/pdf", "image/png", "image/jpeg"})
ACCEPTED_MATERIAL_MIME_TYPES = tuple(dict.fromkeys(MATERIAL_FILE_MIME_BY_EXTENSION.values()))
MATERIAL_FILE_MAX_BYTES = 20 * 1024 * 1024


def canonical_material_mime(filename: str) -> str:
    """Return the canonical MIME type or reject an unsupported filename.

    Permissions:
        Pure validation; the caller must enforce author ownership separately.
    """

    extension = PurePath(str(filename or "").strip()).suffix.lower()
    mime_type = MATERIAL_FILE_MIME_BY_EXTENSION.get(extension)
    if mime_type is None:
        raise ValueError("invalid_filename")
    return mime_type


def validate_material_file_type(filename: str, mime_type: str) -> str:
    """Validate an extension/MIME pair and return the normalized MIME value."""

    canonical = canonical_material_mime(filename)
    normalized = str(mime_type or "").strip().lower()
    if normalized != canonical:
        raise ValueError("mime_not_allowed")
    return canonical


def is_inline_preview_mime(mime_type: str | None) -> bool:
    """Return whether GUSTAV may embed this material in a browser context."""

    return str(mime_type or "").strip().lower() in INLINE_PREVIEW_MIME_TYPES


def material_download_disposition(mime_type: str | None, requested: str) -> str:
    """Force non-previewable files to download instead of rendering inline."""

    return requested if is_inline_preview_mime(mime_type) else "attachment"


__all__ = [
    "ACCEPTED_MATERIAL_MIME_TYPES",
    "INLINE_PREVIEW_MIME_TYPES",
    "MATERIAL_FILE_MAX_BYTES",
    "MATERIAL_FILE_MIME_BY_EXTENSION",
    "canonical_material_mime",
    "is_inline_preview_mime",
    "material_download_disposition",
    "validate_material_file_type",
]
