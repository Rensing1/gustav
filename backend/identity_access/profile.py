"""Framework-independent profile rules for the authenticated subject.

The HTTP adapter must supply the current user's subject, never an arbitrary
target from the request body. Identity writes preserve unrelated attributes.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Protocol

from backend.identity_access.profile_helpers import (
    normalized_attributes,
    parse_lock_timestamp,
    profile_identity_defaults,
)


class ProfileIdentity(Protocol):
    """The only identity operations needed for profile self-service."""

    def get_user(self, *, user_id: str) -> dict[str, object]: ...

    def update_user(self, *, user_id: str, payload: dict[str, object]) -> None: ...


class ProfileNameLockedError(RuntimeError):
    """Raised when the current name cannot yet be edited."""


class ProfileService:
    """Read or update a self-service profile through an explicit identity port."""

    def __init__(self, identity: ProfileIdentity) -> None:
        self.identity = identity

    def load(self, sub: str, claims: dict[str, object]) -> dict[str, object]:
        """Read the current subject's profile, with verified claims as fallback.

        The adapter must authorize `sub` as the caller's own identity. Claims
        supply defaults only; identity attributes take precedence when available.
        """
        defaults = profile_identity_defaults(claims)
        client = self.identity
        try:
            user = client.get_user(user_id=sub)
        except Exception:
            return defaults

        attributes = normalized_attributes(user.get("attributes"))
        display_name = str(
            (attributes.get("display_name") or [defaults["display_name"]])[0] or ""
        ).strip()
        email = str(user.get("email") or defaults["email"] or "").strip()
        first_name = str(user.get("firstName") or "").strip()
        last_name = str(user.get("lastName") or "").strip()
        if not first_name and not last_name:
            first_name = str(defaults["first_name"] or "")
            last_name = str(defaults["last_name"] or "")

        locked_until = parse_lock_timestamp((attributes.get("name_locked_until") or [None])[0])
        now = datetime.now(timezone.utc)
        can_edit = locked_until is None or locked_until <= now
        lock_value = locked_until.astimezone(timezone.utc).isoformat() if locked_until else None

        return {
            "display_name": display_name or str(defaults["display_name"]),
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "name_locked_until": lock_value,
            "name_can_edit": can_edit,
        }

    def update_display_name(self, sub: str, display_name: str) -> None:
        """Persist only the mutable display-name attribute for one profile.

        Why:
            The authenticated caller may update only their own `sub`. The
            validated display name is trimmed; unrelated attributes and the
            provider's existing email are preserved. Login fields are not copied.
        """
        client = self.identity
        user = client.get_user(user_id=sub)
        attributes = normalized_attributes(user.get("attributes"))
        attributes["display_name"] = [str(display_name).strip()]
        client.update_user(
            user_id=sub,
            payload={
                "email": str(user.get("email") or "").strip(),
                "attributes": attributes,
            },
        )

    def update_name(self, sub: str, first_name: str, last_name: str) -> None:
        """Persist only Vorname, Nachname and the lock attribute for one profile.

        Why:
            Login-related fields can be externally managed and therefore immutable.
            We update only the profile fields that belong to this use case so the
            request also works for brokered or restricted accounts.

        The adapter must authorize `sub` as the caller's identity and validate
        the name fields. An active lock raises ProfileNameLockedError without
        writing; a successful update starts the existing 180-day lock.
        """
        client = self.identity
        user = client.get_user(user_id=sub)
        attributes = normalized_attributes(user.get("attributes"))
        locked_until = parse_lock_timestamp((attributes.get("name_locked_until") or [None])[0])
        now = datetime.now(timezone.utc)
        if locked_until is not None and locked_until > now:
            raise ProfileNameLockedError(locked_until.astimezone(timezone.utc).isoformat())

        next_lock = (now + timedelta(days=180)).astimezone(timezone.utc).isoformat()
        attributes["name_locked_until"] = [next_lock]
        payload = {
            "firstName": str(first_name).strip(),
            "lastName": str(last_name).strip(),
            "email": str(user.get("email") or "").strip(),
            "attributes": attributes,
        }
        client.update_user(user_id=sub, payload=payload)
