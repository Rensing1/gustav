"""Small framework-light helpers used by legacy SSR rendering."""

from __future__ import annotations

import html
import json
import re
import uuid
from collections.abc import Mapping
from datetime import datetime, timezone
from urllib.parse import quote, urlencode


def quote_url_path_value(value: object) -> str:
    """Quote one dynamic path segment defensively for SSR-generated URLs."""

    return quote(str(value or ""), safe="")


def build_url_with_query(path: str, params: Mapping[str, object]) -> str:
    """Build a URL with a safely encoded query string."""

    filtered = {
        str(key): str(value)
        for key, value in params.items()
        if value is not None
    }
    return f"{path}?{urlencode(filtered)}" if filtered else path


def normalize_changed_at_to_utc(changed_raw: str) -> datetime | None:
    """Parse a `changed_at` ISO timestamp and normalize it to UTC."""

    try:
        normalized = changed_raw.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def clamp_pagination(limit_raw: str | None, offset_raw: str | None) -> tuple[int, int]:
    """Clamp SSR pagination to the UI-supported range."""

    try:
        limit = int(limit_raw) if limit_raw is not None else 20
    except (ValueError, TypeError):
        limit = 20
    try:
        offset = int(offset_raw) if offset_raw is not None else 0
    except (ValueError, TypeError):
        offset = 0
    return max(1, min(50, limit)), max(0, offset)


def is_uuid_like(value: str) -> bool:
    """Return whether a string can be parsed as a UUID."""

    try:
        uuid.UUID(str(value))
        return True
    except Exception:
        return False


def normalize_open_attempt_id_uuid(value: str | None) -> str:
    """Normalize `open_attempt_id` to a strict UUID or an empty string."""

    candidate = str(value or "").strip()
    if not candidate:
        return ""
    return candidate if is_uuid_like(candidate) else ""


def hx_vals_attr_payload(payload: dict[str, object]) -> str:
    """Return an HTML-safe JSON string for usage inside an `hx-vals` attribute."""

    raw = json.dumps(payload, separators=(",", ":"))
    return html.escape(raw)


def is_analysis_in_progress(status: object) -> bool:
    """Return True while the worker is still processing the submission."""

    return str(status or "").lower() in ("pending", "extracted")


def generate_task_submit_idempotency_key() -> str:
    """Generate a short SSR idempotency token for one submit action."""

    return f"ui-{uuid.uuid4().hex[:16]}"


def normalize_task_submit_idempotency_key(raw_value: object) -> str:
    """Return a safe idempotency token or a fresh fallback token."""

    value = str(raw_value or "").strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{1,64}", value):
        return value
    return generate_task_submit_idempotency_key()
