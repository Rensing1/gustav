"""
Keycloak realm export sanity tests.

Assert that the realm is configured to use email as username to keep
registration simple and aligned with the app's UX.
"""

from __future__ import annotations

import json
from pathlib import Path


REALM_EXPORT_PATH = Path("keycloak/realm-gustav.json")


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
    data = json.loads(REALM_EXPORT_PATH.read_text(encoding="utf-8"))
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
    """Realm must enforce email verification and use the gustav email theme.

    Why:
        - verifyEmail=true blocks unverified accounts from logging in and reduces
          account-takeover/phishing risk.
        - emailTheme='gustav' keeps verification/reset mails aligned with our UI/branding.
    """
    assert REALM_EXPORT_PATH.exists(), "realm-gustav.json missing"
    data = json.loads(REALM_EXPORT_PATH.read_text(encoding="utf-8"))

    # Enforce verification for all registrations (IdP-side enforcement only).
    assert data.get("verifyEmail") is True
    # Self-service password reset via email is enabled so the link stays visible.
    assert data.get("resetPasswordAllowed", False) is True
    # Email theme must be explicitly set so Keycloak renders our templates.
    assert data.get("emailTheme") == "gustav", "emailTheme should be set to 'gustav'"


def test_realm_enables_remember_me():
    """Realm should allow remember-me so the checkbox renders when desired."""
    data = json.loads(REALM_EXPORT_PATH.read_text(encoding="utf-8"))
    assert data.get("rememberMe", False) is True, "rememberMe should be enabled to render the checkbox"


def test_realm_configures_smtp_from_address():
    """Realm export must configure a valid from address for emails.

    Why:
        When importing the realm into a fresh Keycloak instance (local = prod),
        password reset and verification emails must work without manual
        post-configuration in the admin UI. A missing or empty `from` value causes
        `EmailException: Please provide a valid address` in Keycloak.
    """
    data = json.loads(REALM_EXPORT_PATH.read_text(encoding="utf-8"))
    smtp = data.get("smtpServer") or {}
    assert smtp, "smtpServer block must be present in realm export"
    # Use a neutral placeholder in the realm export; real deploys must override this.
    assert smtp.get("from") == "noreply@school.example"
    assert smtp.get("fromDisplayName") == "GUSTAV-Lernplattform"


def test_realm_allows_prod_redirect_uri():
    """Realm export must include the prod web redirect URI.

    Why:
        - Importing the realm in prod without the prod redirect breaks the OIDC flow
          with "Invalid redirect URI".
    """
    data = json.loads(REALM_EXPORT_PATH.read_text(encoding="utf-8"))
    clients = data.get("clients", [])
    client = next((c for c in clients if c.get("clientId") == "gustav-web"), None)
    assert client, "gustav-web client definition missing"
    redirect_uris = client.get("redirectUris", [])
    assert "https://gustav-lernplattform.de/*" in redirect_uris, "prod redirect URI missing"
