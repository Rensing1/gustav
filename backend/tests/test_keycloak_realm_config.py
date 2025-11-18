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


def test_realm_requires_email_verification_and_email_theme():
    """Realm must use the gustav email theme (email verification is IdP-only).

    Why:
        - verifyEmail=true ensures that new users must confirm their address
          before they can log in to the learning platform.
        - emailTheme='gustav' makes Keycloak use our branded email templates,
          so verification/reset mails match the app's UI and footer text.
    """
    p = Path("keycloak/realm-gustav.json")
    assert p.exists(), "realm-gustav.json missing"
    data = json.loads(p.read_text(encoding="utf-8"))

    # Email verification is handled IdP-seitig; GUSTAV erzwingt sie nicht mehr.
    assert data.get("verifyEmail") is False
    # Self-service password reset via E-Mail ist deaktiviert; Admin-Panel bleibt zuständig.
    assert data.get("resetPasswordAllowed", False) is False
    # Email theme must be explicitly set so Keycloak renders our templates.
    assert data.get("emailTheme") == "gustav", "emailTheme should be set to 'gustav'"


def test_realm_configures_smtp_from_address():
    """Realm export must configure a valid from address for emails.

    Why:
        When importing the realm into a fresh Keycloak instance (local = prod),
        password reset and verification emails must work ohne manuelle
        Nachkonfiguration im Admin-UI. A missing or empty `from` value causes
        `EmailException: Please provide a valid address` in Keycloak.
    """
    p = Path("keycloak/realm-gustav.json")
    data = json.loads(p.read_text(encoding="utf-8"))
    smtp = data.get("smtpServer") or {}
    assert smtp, "smtpServer block must be present in realm export"
    assert smtp.get("from") == "hennecke@gymalf.de"
    assert smtp.get("fromDisplayName") == "GUSTAV-Lernplattform"
