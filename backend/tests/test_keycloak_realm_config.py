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


def test_gustav_web_client_exports_roles_in_id_token():
    p = Path("keycloak/realm-gustav.json")
    data = json.loads(p.read_text(encoding="utf-8"))
    clients = data.get("clients", [])
    client = next((c for c in clients if c.get("clientId") == "gustav-web"), None)
    assert client is not None, "gustav-web client definition missing"
    mapper = next(
        (
            m
            for m in client.get("protocolMappers", [])
            if m.get("protocolMapper") == "oidc-usermodel-realm-role-mapper"
        ),
        None,
    )
    assert mapper is not None, "realm roles mapper missing for gustav-web client"
    config = mapper.get("config", {})
    assert config.get("claim.name") == "realm_access.roles"
    assert config.get("id.token.claim") == "true", "realm roles must be present in ID tokens"
    assert config.get("access.token.claim") == "true"
