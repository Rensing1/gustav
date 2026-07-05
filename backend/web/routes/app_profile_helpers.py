"""Profile normalization helpers for application-level routes.

Why:
    Profile views combine bearer claims with identity-provider user attributes.
    The parsing and default-building rules are pure data-shaping logic and are
    easier to understand outside the large app route adapter.
"""

from __future__ import annotations

from datetime import datetime


def claims_email(claims: dict[str, object]) -> str:
    """Return the preferred stable email-like identifier from bearer claims."""

    return str(claims.get("email") or claims.get("preferred_username") or "").strip()


def parse_lock_timestamp(value: object) -> datetime | None:
    """Parse an editable-name lock timestamp, accepting trailing `Z`."""

    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        return None


def split_name_suggestion(identifier: str) -> tuple[str, str]:
    """Derive a best-effort first/last-name suggestion from an identifier."""

    try:
        from backend.identity_access import directory  # type: ignore

        humanized = str(directory.humanize_identifier(identifier) or "").strip()
    except Exception:
        humanized = ""
    if not humanized:
        return "", ""
    parts = [part for part in humanized.split(" ") if part]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def profile_identity_defaults(claims: dict[str, object]) -> dict[str, object]:
    """Build default profile fields from bearer claims."""

    email = claims_email(claims)
    first_name, last_name = split_name_suggestion(email)
    return {
        "display_name": str(claims.get("gustav_display_name") or claims.get("name") or first_name or "Benutzer"),
        "email": email,
        "first_name": first_name,
        "last_name": last_name,
        "name_locked_until": None,
        "name_can_edit": True,
    }


def normalized_attributes(payload: object) -> dict[str, list[str]]:
    """Normalize identity-provider attributes to non-empty string lists."""

    attrs = payload if isinstance(payload, dict) else {}
    out: dict[str, list[str]] = {}
    for key, value in attrs.items():
        if not isinstance(key, str):
            continue
        if isinstance(value, list):
            out[key] = [str(item) for item in value if str(item or "").strip()]
        elif value is not None and str(value).strip():
            out[key] = [str(value)]
    return out
