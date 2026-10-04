"""Build safe ``Content-Disposition`` values for user-provided filenames.

Why:
    HTTP response headers must be Latin-1 serializable, while uploaded filenames
    may contain any Unicode character. A quoted ASCII fallback keeps the header
    portable and RFC 5987 ``filename*`` preserves the sanitized UTF-8 name for
    modern browsers. Callers remain responsible for authorizing the download
    before using this presentation-layer helper.
"""

from __future__ import annotations

import unicodedata
from urllib.parse import quote

_FALLBACK_ALLOWED = frozenset(" ._()-")


def _sanitize_display_filename(filename: str | None, fallback: str) -> str:
    """Remove path separators and header-control characters from a filename."""

    candidate = str(filename or "").strip() or fallback
    cleaned = "".join(
        "_"
        if character in {'"', "\\", "/"} or ord(character) < 32 or ord(character) == 127
        else character
        for character in candidate
    ).strip(" .")
    if cleaned:
        return cleaned

    safe_fallback = "".join(
        character
        for character in str(fallback)
        if character not in {'"', "\\", "/", "\r", "\n"} and 31 < ord(character) < 127
    ).strip(" .")
    return safe_fallback or "download"


def _ascii_component(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return "".join(
        character if character.isalnum() or character in _FALLBACK_ALLOWED else "_"
        for character in normalized
    )


def _ascii_fallback_filename(display_filename: str, fallback: str) -> str:
    stem, separator, extension = display_filename.rpartition(".")
    if not separator or not stem:
        stem, extension = display_filename, ""

    fallback_display = _sanitize_display_filename(fallback, "download")
    fallback_stem = fallback_display.rpartition(".")[0] or fallback_display
    ascii_stem = _ascii_component(stem).strip(" ._-")
    if not ascii_stem:
        ascii_stem = _ascii_component(fallback_stem).strip(" ._-") or "download"

    ascii_extension = _ascii_component(extension).strip(" ._-")
    if extension and not ascii_extension:
        ascii_extension = _ascii_component(fallback_display.rpartition(".")[2]).strip(" ._-")
    return f"{ascii_stem}.{ascii_extension}" if ascii_extension else ascii_stem


def content_disposition_value(
    disposition: str,
    filename: str | None,
    *,
    fallback: str = "download",
) -> str:
    """Return an RFC 5987 download header value for an authorized response.

    Args:
        disposition: Already validated ``inline`` or ``attachment`` value.
        filename: Untrusted original filename supplied by an uploader.
        fallback: ASCII-oriented basename used when Unicode cannot be transliterated.

    Returns:
        A Latin-1-safe value containing both ``filename`` and ``filename*``.
    """

    if disposition not in {"inline", "attachment"}:
        raise ValueError("invalid_content_disposition")

    display_filename = _sanitize_display_filename(filename, fallback)
    ascii_filename = _ascii_fallback_filename(display_filename, fallback)
    encoded_filename = quote(display_filename, safe="")
    return f"{disposition}; filename=\"{ascii_filename}\"; filename*=UTF-8''{encoded_filename}"
