"""Contracts for the shared authentication boundary, before implementation."""
import json
from pathlib import Path

import yaml


def test_keycloak_lifetimes_and_api_audience():
    realm = json.loads(Path("keycloak/realm-gustav.json").read_text())
    assert realm["ssoSessionIdleTimeoutRememberMe"] == 2592000
    assert realm["ssoSessionMaxLifespanRememberMe"] == 2592000
    client = next(c for c in realm["clients"] if c["clientId"] == "gustav-web")
    assert any(m.get("config", {}).get("included.custom.audience") == "gustav-api" for m in client["protocolMappers"])
    assert "keycloak:26.7.3" in Path("keycloak/Dockerfile").read_text()


def test_openapi_shared_session_and_safe_logout():
    paths = yaml.safe_load(Path("api/openapi.yml").read_text())["paths"]
    assert "/api/app/session-sync" not in paths
    assert {"cookieAuth": []} in paths["/api/app/session-bootstrap"]["get"]["security"]
    assert "503" in paths["/api/app/session-bootstrap"]["get"]["responses"]
    assert "post" in paths["/auth/logout"]
    assert "200" in paths["/auth/logout"]["get"]["responses"]


def test_password_help_uses_live_policy_for_both_forms():
    root = Path("keycloak/themes/gustav/login")
    help_text = (root / "_password_requirements.ftl").read_text()
    for field in ("length", "digits", "lowerCase", "upperCase", "specialChars"):
        assert f"passwordPolicies.{field}" in help_text
    for name in ("register.ftl", "login-update-password.ftl"):
        assert '_password_requirements.ftl' in (root / name).read_text()


def test_password_change_errors_are_associated_with_fields():
    for name in ('login-update-password.ftl', 'update-password.ftl'):
        source = (Path('keycloak/themes/gustav/login') / name).read_text()
        assert 'aria-invalid=' in source
        assert 'password-new-error' in source
        assert 'password-confirm-error' in source
