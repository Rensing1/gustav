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

from pathlib import Path
import os
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
PKG_DIR = REPO_ROOT / "backend" / "identity_access"
if str(PKG_DIR.parent) not in sys.path:
    sys.path.insert(0, str(PKG_DIR.parent))

from identity_access import directory  # type: ignore  # noqa: E402


def test_display_name_prefers_attribute_then_first_last():
    u = {"firstName": "Max", "lastName": "Mustermann", "attributes": {"display_name": ["Franz Müller"]}}
    assert directory._display_name(u) == "Franz Müller"

    u2 = {"firstName": "Max", "lastName": "Mustermann"}
    assert directory._display_name(u2) == "Max Mustermann"


def test_display_name_humanizes_email_and_legacy_prefix():
    u = {"email": "raphael.fournell@gym.example.de"}
    assert directory._display_name(u) == "Raphael Fournell"

    u2 = {"username": "legacy-email:max.tolle"}
    assert directory._display_name(u2) == "Max Tolle"


def test_display_name_handles_single_word_and_fallback():
    u = {"username": "emilia"}
    assert directory._display_name(u) == "Emilia"

    u2 = {}
    assert directory._display_name(u2) == "Unbekannt"

