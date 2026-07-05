"""
Unit tests for name humanization in the directory adapter.

We test only the pure helpers (no network): `_display_name` should return a
human-friendly name using the following precedence:
- attributes.display_name
- firstName + lastName
- email/username heuristic (prefix before '@', split on [._-], title case)
- fallback "Unbekannt"
"""
from __future__ import annotations

from backend.identity_access import directory


def test_display_name_prefers_attribute_then_first_last():
    u = {"firstName": "Max", "lastName": "Mustermann", "attributes": {"display_name": ["Person Beispiel"]}}
    assert directory._display_name(u) == "Person Beispiel"

    u2 = {"firstName": "Max", "lastName": "Mustermann"}
    assert directory._display_name(u2) == "Max Mustermann"


def test_display_name_humanizes_email_and_legacy_prefix():
    u = {"email": "student.example@example.edu"}
    assert directory._display_name(u) == "Student Example"

    u2 = {"username": "legacy-email:learner.placeholder"}
    assert directory._display_name(u2) == "Learner Placeholder"


def test_display_name_handles_single_word_and_fallback():
    u = {"username": "emilia"}
    assert directory._display_name(u) == "Emilia"

    u2 = {}
    assert directory._display_name(u2) == "Unbekannt"
