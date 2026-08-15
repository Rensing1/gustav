"""Pure domain tests for signed invitation capabilities and recipients."""

from __future__ import annotations

from uuid import uuid4

import pytest

from backend.teaching.course_invitations import (
    InvitationTokenError,
    build_invitation_token,
    normalize_invitation_recipients,
    parse_invitation_token,
    recipient_digest,
)


SECRET = "test-course-invitation-secret-that-is-long-enough"


def test_invitation_token_round_trips_and_rejects_tampering() -> None:
    invitation_id = uuid4()
    token = build_invitation_token(invitation_id, "nonce-value-that-is-long-enough", SECRET)

    parsed_id, parsed_nonce = parse_invitation_token(token, SECRET)
    assert parsed_id == invitation_id
    assert parsed_nonce == "nonce-value-that-is-long-enough"

    with pytest.raises(InvitationTokenError):
        parse_invitation_token(f"{token[:-1]}x", SECRET)


def test_invitation_token_requires_a_dedicated_strong_secret() -> None:
    with pytest.raises(InvitationTokenError):
        build_invitation_token(uuid4(), "nonce-value-that-is-long-enough", "short")


def test_recipient_normalization_deduplicates_and_enforces_school_domains() -> None:
    recipients = normalize_invitation_recipients(
        [" Alice@School.Example ", "alice@school.example", "bob@school.example"],
        allowed_domains="@school.example",
    )
    assert recipients == ["alice@school.example", "bob@school.example"]

    with pytest.raises(ValueError, match="invalid_or_disallowed_recipient"):
        normalize_invitation_recipients(
            ["private@example.net"],
            allowed_domains="@school.example",
        )


def test_recipient_normalization_rejects_controls_and_more_than_100() -> None:
    with pytest.raises(ValueError, match="invalid_or_disallowed_recipient"):
        normalize_invitation_recipients(["alice@school.example\nBcc: attacker@example.net"])
    with pytest.raises(ValueError, match="too_many_recipients"):
        normalize_invitation_recipients(
            [f"student-{index}@school.example" for index in range(101)]
        )


def test_recipient_digest_is_invitation_scoped_and_deterministic() -> None:
    first = recipient_digest("alice@school.example", "invite-a", SECRET)
    assert first == recipient_digest("alice@school.example", "invite-a", SECRET)
    assert first != recipient_digest("alice@school.example", "invite-b", SECRET)
    assert "alice" not in first
