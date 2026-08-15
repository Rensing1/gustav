"""Domain rules for secure course invitation capabilities.

Why:
    HTTP routes, database repositories and mail workers all need the same token
    and recipient rules. Keeping them framework-free prevents either FastAPI or
    SMTP details from becoming part of the Teaching domain.
"""

from __future__ import annotations

import hashlib
import hmac
import re
from uuid import UUID


TOKEN_VERSION = "v1"
_MIN_SECRET_LENGTH = 32
_EMAIL_PATTERN = re.compile(r"^[^@\s\x00-\x1f\x7f]+@[^@\s\x00-\x1f\x7f]+$")


class InvitationTokenError(ValueError):
    """Raised when an invitation capability is malformed or unauthentic."""


def _secret_bytes(secret: str) -> bytes:
    value = str(secret or "").encode("utf-8")
    if len(value) < _MIN_SECRET_LENGTH or str(secret).upper().startswith("CHANGE_ME"):
        raise InvitationTokenError("course_invite_signing_secret_invalid")
    return value


def build_invitation_token(invitation_id: UUID | str, nonce: str, secret: str) -> str:
    """Return a reproducible signed capability without persisting the token.

    Parameters:
        invitation_id: Stable database identifier for the invitation.
        nonce: Random per-invitation value stored in PostgreSQL.
        secret: Dedicated application signing secret with at least 32 bytes.
    """

    normalized_id = str(UUID(str(invitation_id)))
    normalized_nonce = str(nonce or "")
    if len(normalized_nonce) < 20 or len(normalized_nonce) > 128:
        raise InvitationTokenError("invitation_nonce_invalid")
    unsigned = f"{TOKEN_VERSION}.{normalized_id}.{normalized_nonce}"
    signature = hmac.new(_secret_bytes(secret), unsigned.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{unsigned}.{signature}"


def parse_invitation_token(token: str, secret: str) -> tuple[UUID, str]:
    """Verify a capability in constant time and return its database identity."""

    parts = str(token or "").split(".")
    if len(parts) != 4 or parts[0] != TOKEN_VERSION:
        raise InvitationTokenError("invitation_token_invalid")
    version, raw_id, nonce, supplied_signature = parts
    if len(nonce) < 20 or len(nonce) > 128 or len(supplied_signature) != 64:
        raise InvitationTokenError("invitation_token_invalid")
    try:
        invitation_id = UUID(raw_id)
    except ValueError as exc:
        raise InvitationTokenError("invitation_token_invalid") from exc
    unsigned = f"{version}.{invitation_id}.{nonce}"
    expected = hmac.new(_secret_bytes(secret), unsigned.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(supplied_signature, expected):
        raise InvitationTokenError("invitation_token_invalid")
    return invitation_id, nonce


def _allowed_domain_set(raw: str | None) -> set[str]:
    return {
        value.strip().lower().removeprefix("@")
        for value in str(raw or "").split(",")
        if value.strip().removeprefix("@")
    }


def normalize_invitation_recipients(
    recipients: list[str],
    *,
    allowed_domains: str | None = None,
) -> list[str]:
    """Validate, normalize and deduplicate at most 100 school addresses."""

    if not isinstance(recipients, list) or not recipients:
        raise ValueError("recipients_required")
    if len(recipients) > 100:
        raise ValueError("too_many_recipients")
    allowed = _allowed_domain_set(allowed_domains)
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in recipients:
        address = str(raw or "").strip().lower()
        if len(address) > 254 or not _EMAIL_PATTERN.fullmatch(address):
            raise ValueError("invalid_or_disallowed_recipient")
        _local, domain = address.rsplit("@", 1)
        if not domain or (allowed and domain not in allowed):
            raise ValueError("invalid_or_disallowed_recipient")
        if address not in seen:
            seen.add(address)
            normalized.append(address)
    if len(normalized) > 100:
        raise ValueError("too_many_recipients")
    return normalized


def recipient_digest(email: str, invitation_id: UUID | str, secret: str) -> str:
    """Return an irreversible, invitation-scoped digest for deduplication."""

    message = f"course-invite-email:{invitation_id}:{str(email).strip().lower()}"
    return hmac.new(_secret_bytes(secret), message.encode("utf-8"), hashlib.sha256).hexdigest()
