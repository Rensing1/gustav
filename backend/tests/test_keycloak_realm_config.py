"""
Keycloak realm export sanity tests.

Assert that the realm is configured to use email as username to keep
registration simple and aligned with the app's UX.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


REALM_EXPORT_PATH = Path("keycloak/realm-gustav.json")
REALM_RENDERER_PATH = Path("keycloak/render_realm.py")


def _load_realm_renderer():
    assert REALM_RENDERER_PATH.exists(), "render_realm.py missing"
    spec = importlib.util.spec_from_file_location("gustav_keycloak_render_realm", REALM_RENDERER_PATH)
    assert spec and spec.loader, "render_realm.py must be importable for config tests"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _registration_profile_config(data: dict) -> str:
    components = data.get("components", {})
    providers = components.get("org.keycloak.userprofile.UserProfileProvider", [])
    provider = providers[0] if providers else {}
    config_items = provider.get("config", {}).get("kc.user.profile.config", [])
    assert config_items, "declarative user profile config missing"
    return config_items[0]


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


def test_realm_template_defers_registration_domain_pattern_to_placeholder():
    """Realm template must not hardcode a school domain outside shared env config."""
    data = json.loads(REALM_EXPORT_PATH.read_text(encoding="utf-8"))
    profile_config = _registration_profile_config(data)
    assert '"name": "email"' in profile_config or '"name":"email"' in profile_config
    assert '"pattern"' in profile_config, "email profile must define a domain pattern validator"
    assert "__GUSTAV_ALLOWED_EMAIL_PATTERN__" in profile_config
    assert "school\\\\.example" not in profile_config


def test_realm_renderer_uses_allowed_registration_domains_env():
    """Rendered realm config must derive its regex from ALLOWED_REGISTRATION_DOMAINS."""
    renderer = _load_realm_renderer()
    data = renderer.render_realm_template("@gymnasium.example,@oberstufe.example")
    profile_config = _registration_profile_config(data)

    assert "gymnasium\\\\.example" in profile_config
    assert "oberstufe\\\\.example" in profile_config
    assert "school\\\\.example" not in profile_config


def test_realm_renderer_falls_back_to_public_placeholder_domain():
    """Without env input the rendered realm should stay on the public placeholder domain."""
    renderer = _load_realm_renderer()
    data = renderer.render_realm_template(None)
    profile_config = _registration_profile_config(data)

    assert "school\\\\.example" in profile_config


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


def test_realm_allows_public_example_redirect_uri():
    """Realm export must include a public placeholder redirect URI.

    Why:
        This repository is intended to be publishable as open source. Therefore
        the realm export must not hardcode a real production domain, but it
        should still show the expected shape of the prod redirect URI.
    """
    data = json.loads(REALM_EXPORT_PATH.read_text(encoding="utf-8"))
    clients = data.get("clients", [])
    client = next((c for c in clients if c.get("clientId") == "gustav-web"), None)
    assert client, "gustav-web client definition missing"
    redirect_uris = client.get("redirectUris", [])
    assert "https://app.gustav.example/*" in redirect_uris, "public example redirect URI missing"
