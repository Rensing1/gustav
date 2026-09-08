"""Pure submission input validation; callers supply the configured upload limit."""

from typing import Any

from backend.storage.learning_policy import ALLOWED_FILE_MIME, ALLOWED_IMAGE_MIME, STORAGE_KEY_RE


def validate_submission_payload(payload: dict[str, Any], *, max_upload_bytes: int) -> tuple[str, dict[str, Any]]:
    """Validate and normalize text, upload, and H5P submission payloads."""

    if not isinstance(payload, dict):
        raise ValueError("invalid_input")
    intent_raw = payload.get("intent")
    if intent_raw is None:
        intent = "submit"
    elif not isinstance(intent_raw, str):
        raise ValueError("invalid_input")
    else:
        intent = intent_raw.strip().lower()
    if intent not in {"feedback", "submit"}:
        raise ValueError("invalid_input")
    kind = payload.get("kind")
    if kind not in ("text", "image", "file", "h5p"):
        raise ValueError("invalid_input")
    if kind == "text":
        text_body = payload.get("text_body")
        if not isinstance(text_body, str) or not text_body.strip():
            raise ValueError("invalid_input")
        if len(text_body) > 65_536:
            raise ValueError("invalid_input")
        return kind, {"intent": intent, "text_body": text_body.strip()}
    if kind == "h5p":
        required = {"score_raw", "score_max"}
        if not required.issubset(payload.keys()):
            raise ValueError("invalid_h5p_payload")
        try:
            raw_int = int(payload.get("score_raw"))
            max_int = int(payload.get("score_max"))
        except (TypeError, ValueError):
            raise ValueError("invalid_h5p_payload") from None
        if raw_int < 0 or max_int < 0 or raw_int > max_int:
            raise ValueError("invalid_h5p_payload")
        return kind, {"intent": intent, "score_raw": raw_int, "score_max": max_int}

    detail = "invalid_image_payload" if kind == "image" else "invalid_file_payload"
    required = {"storage_key", "mime_type", "size_bytes", "sha256"}
    if not required.issubset(payload.keys()):
        raise ValueError(detail)
    size_bytes = payload.get("size_bytes")
    try:
        size_int = int(size_bytes)
    except (TypeError, ValueError):
        raise ValueError(detail) from None
    if size_int <= 0 or size_int > max_upload_bytes:
        raise ValueError(detail)
    mime_type_raw = payload.get("mime_type")
    if not isinstance(mime_type_raw, str) or not mime_type_raw:
        raise ValueError(detail)
    mime_type = mime_type_raw.strip().lower()
    allowed_mime = ALLOWED_IMAGE_MIME if kind == "image" else ALLOWED_FILE_MIME
    if mime_type not in allowed_mime:
        raise ValueError(detail)
    storage_key = payload.get("storage_key")
    if not isinstance(storage_key, str) or not storage_key:
        raise ValueError(detail)
    if not STORAGE_KEY_RE.fullmatch(storage_key):
        raise ValueError(detail)
    sha256 = payload.get("sha256")
    if not isinstance(sha256, str):
        raise ValueError(detail)
    sha256_normalized = sha256.strip().lower()
    if len(sha256_normalized) != 64 or any(c not in "0123456789abcdef" for c in sha256_normalized):
        raise ValueError(detail)
    return kind, {
        "intent": intent,
        "storage_key": storage_key,
        "mime_type": mime_type,
        "size_bytes": size_int,
        "sha256": sha256_normalized,
    }
