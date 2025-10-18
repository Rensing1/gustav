"""
Minimal OIDC client for Keycloak integration.

Why: Keep web framework independent business logic in a separate module (Clean
Architecture). The web adapter (FastAPI) calls into this client to build the
authorization URL and exchange the authorization code for tokens.

Security: Uses PKCE (S256) parameters; caller is responsible for state &
code_verifier storage (e.g., in server-side state store or DB). This minimal
client does not manage persistence.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional
import hashlib
import base64
import os
from urllib.parse import urlencode

# Small indirection to ease monkeypatching in tests
import requests as http


def http_post(url: str, data: Dict[str, str], headers: Dict[str, str]):
    return http.post(url, data=data, headers=headers)


@dataclass(frozen=True)
class OIDCConfig:
    base_url: str  # internal base URL (server-to-server), e.g., http://keycloak:8080
    realm: str  # e.g., gustav
    client_id: str  # e.g., gustav-web
    redirect_uri: str  # e.g., http://localhost:8100/auth/callback
    public_base_url: str | None = None  # browser-facing URL, e.g., http://localhost:8080

    @property
    def auth_endpoint(self) -> str:
        base = self.public_base_url or self.base_url
        return f"{base}/realms/{self.realm}/protocol/openid-connect/auth"

    @property
    def token_endpoint(self) -> str:
        # Token exchange happens server-side; use internal base URL
        return f"{self.base_url}/realms/{self.realm}/protocol/openid-connect/token"


class OIDCClient:
    def __init__(self, config: OIDCConfig):
        self.cfg = config

    @staticmethod
    def generate_code_verifier(length: int = 64) -> str:
        """Generate a high-entropy URL-safe code_verifier.

        Note: RFC suggests length between 43 and 128 characters.
        """
        return base64.urlsafe_b64encode(os.urandom(length)).decode("ascii").rstrip("=")

    @staticmethod
    def code_challenge_s256(code_verifier: str) -> str:
        """Derive S256 code challenge from verifier."""
        digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
        return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")

    def build_authorization_url(self, *, state: str, code_challenge: str, nonce: Optional[str] = None) -> str:
        """Return the authorization URL for the configured realm/client.

        Parameters
        - state: Opaque anti-CSRF token (and QR context if needed)
        - code_challenge: The S256 code challenge derived from the verifier
        - nonce: Optional OIDC replay protection value (recommended)
        """
        params = {
            "response_type": "code",
            "client_id": self.cfg.client_id,
            "redirect_uri": self.cfg.redirect_uri,
            "scope": "openid",
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        if nonce:
            params["nonce"] = nonce
        return f"{self.cfg.auth_endpoint}?{urlencode(params)}"

    def exchange_code_for_tokens(self, *, code: str, code_verifier: str) -> Dict[str, str]:
        """Exchange authorization code for tokens at token endpoint.

        Returns tokens dict on success; raises ValueError on failure.
        """
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": self.cfg.client_id,
            "redirect_uri": self.cfg.redirect_uri,
            "code_verifier": code_verifier,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        resp = http_post(self.cfg.token_endpoint, data=data, headers=headers)
        if resp.status_code != 200:
            raise ValueError("token_exchange_failed")
        return resp.json()
