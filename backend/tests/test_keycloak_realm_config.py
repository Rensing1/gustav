"""
Keycloak realm export sanity tests.

Assert that the realm is configured to use email as username to keep
registration simple and aligned with the app's UX.
"""

from __future__ import annotations

import json
from pathlib import Path


def test_realm_uses_email_as_username():
    p = Path("keycloak/realm-gustav.json")
    assert p.exists(), "realm-gustav.json missing"
    data = json.loads(p.read_text(encoding="utf-8"))
    # Expect email as username
    assert data.get("registrationEmailAsUsername", True) is True, (
        "registrationEmailAsUsername should be true to hide the username field"
    )
    # Also keep loginWithEmailAllowed true for consistency
    assert data.get("loginWithEmailAllowed", True) is True

