"""Shared helpers for storage-backed upload intents.

Why:
    Learning and Teaching both return presigned upload intents that are later
    replayed by browser or server-side clients. Header casing must therefore be
    canonical and stable across both flows. Returning both `content-type` and
    `Content-Type` looks harmless but breaks Fetch because header names are
    case-insensitive and may be coalesced into a comma-separated value.
"""

from __future__ import annotations

from typing import Any


def normalize_upload_intent_headers(
    raw_headers: dict[str, Any] | None,
    *,
    fallback_content_type: str | None = None,
) -> dict[str, str]:
    """Return a lowercase, case-insensitively deduplicated header mapping.

    The helper keeps only the final value for each logical header name and
    optionally ensures a canonical `content-type` exists for upload requests.
    """

    normalized: dict[str, str] = {}
    if raw_headers:
        for key, value in dict(raw_headers).items():
            header_name = str(key).strip().lower()
            if not header_name:
                continue
            normalized[header_name] = str(value)

    fallback = (fallback_content_type or "").strip().lower()
    if fallback and "content-type" not in normalized:
        normalized["content-type"] = fallback

    return normalized
