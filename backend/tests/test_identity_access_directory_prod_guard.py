"""
Guards for Keycloak admin access method in production.

Why:
- In PROD/Stage, we must not fall back to the password grant for admin API
  access. Only client_credentials via a confidential client is allowed.
"""
from __future__ import annotations

import types
import pytest


@pytest.mark.anyio
async def test_password_grant_forbidden_in_prod(monkeypatch: pytest.MonkeyPatch):
    """In prod-like env without client secret, the adapter must not attempt password grant."""
    monkeypatch.setenv("GUSTAV_ENV", "prod")
    # Ensure no client secret is present
    monkeypatch.delenv("KC_ADMIN_CLIENT_SECRET", raising=False)
    # Provide username/password so legacy path would be taken if not forbidden
    monkeypatch.setenv("KC_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("KC_ADMIN_PASSWORD", "admin")

    # Fail if any HTTP request is attempted
    import requests

    def _deny_post(*args, **kwargs):  # pragma: no cover - should not be reached
        raise AssertionError("HTTP call should not be performed in forbidden password grant path")

    monkeypatch.setattr(requests, "post", _deny_post)

    from backend.identity_access import directory

    with pytest.raises(RuntimeError) as ei:
        directory._KC().token()
    assert "password_grant_disabled_in_prod" in str(ei.value)


@pytest.mark.anyio
async def test_client_credentials_in_prod_uses_secret(monkeypatch: pytest.MonkeyPatch):
    """In prod-like env, client_credentials must be used when secret is configured."""
    monkeypatch.setenv("GUSTAV_ENV", "prod")
    monkeypatch.setenv("KC_ADMIN_CLIENT_ID", "gustav-admin-cli")
    monkeypatch.setenv("KC_ADMIN_CLIENT_SECRET", "REAL_SECRET")
    # Avoid real HTTP: fake a successful token response
    import requests

    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"access_token": "ABC123"}

    def _fake_post(*args, **kwargs):
        return _Resp()

    monkeypatch.setattr(requests, "post", _fake_post)

    from backend.identity_access import directory

    tok = directory._KC().token()
    assert tok == "ABC123"

