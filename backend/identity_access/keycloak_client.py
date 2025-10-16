"""
Minimal Keycloak client for DEV/CI Direct Grant flows.

This module is a thin, framework-agnostic adapter used by the web layer
to authenticate a user with email/password against Keycloak when the
feature flag AUTH_USE_DIRECT_GRANT is enabled. Production deployments
should continue to use the browser-based redirect flow.

Security: Never log credentials. This client does not store or persist
any sensitive data; it simply forwards to Keycloak's token endpoint.
"""

from __future__ import annotations

from typing import Dict
import requests

from .oidc import OIDCConfig


class AuthClient:
    """Authenticate against Keycloak using the Direct Grant.

    The method `direct_grant` performs a password grant against the configured
    realm and client. It returns a token dict on success and raises on errors.
    """

    def __init__(self, cfg: OIDCConfig) -> None:
        self.cfg = cfg

    def direct_grant(self, *, email: str, password: str) -> Dict[str, str]:
        url = self.cfg.token_endpoint()
        data = {
            "grant_type": "password",
            "client_id": self.cfg.client_id,
            "username": email,
            "password": password,
        }
        r = requests.post(url, data=data, timeout=10)
        if r.status_code != 200:
            # Propagate as a simple ValueError for the web adapter to catch.
            raise ValueError("direct_grant_failed")
        body = r.json()
        # Expect id_token to be present for our session creation
        if not isinstance(body, dict) or "id_token" not in body:
            raise ValueError("id_token_missing")
        return body  # type: ignore[return-value]

