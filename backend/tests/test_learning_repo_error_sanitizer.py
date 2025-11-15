"""
Unit tests for `_sanitize_error_message`.

These guardrails ensure that sensitive tokens and filesystem paths never leak
through the public Learning API responses.
"""
from __future__ import annotations

from backend.learning.repo_db import _sanitize_error_message


def test_sanitizer_redacts_colon_tokens() -> None:
    """Secrets like 'token: value' must be redacted, not echoed back."""

    raw = "Vision adapter failed: service_token: ABC12345!"
    sanitized = _sanitize_error_message(raw)

    assert sanitized is not None
    assert "ABC12345" not in sanitized


def test_sanitizer_strips_absolute_paths() -> None:
    """File-system paths should not leak into telemetry responses."""

    raw = "OCR failed reading /home/felix/uploads/foo.pdf at C:\\Users\\Felix\\Desktop\\bar.png"
    sanitized = _sanitize_error_message(raw)

    assert sanitized is not None
    assert "/home/felix" not in sanitized
    assert "C:\\Users\\Felix" not in sanitized
