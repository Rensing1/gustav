"""
JWT verification helpers for the identity_access bounded context.

Why: Keep cryptographic validation of ID tokens outside the web adapter so we
can unit test it independently and swap the persistence/cache later on.

Security: Validates the ID token signature with the realm's JWKS, ensures issuer,
audience, and expiration are respected. This is a minimal implementation suited
for development; in production we may want to back the cache with Redis.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple
import time

import requests
from jose import jwt
from jose.exceptions import JOSEError

from .oidc import OIDCConfig


class IDTokenVerificationError(Exception):
    """Raised when the ID token fails verification."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass
class _CacheEntry:
    jwks: Dict[str, object]
    expires_at: float


class JWKSCache:
    """Very small in-memory cache for JWKS responses (development use)."""

    def __init__(self, ttl_seconds: int = 300):
        self.ttl_seconds = ttl_seconds
        self._entries: Dict[Tuple[str, str], _CacheEntry] = {}

    def _cache_key(self, cfg: OIDCConfig) -> Tuple[str, str]:
        return (cfg.base_url, cfg.realm)

    def get(self, cfg: OIDCConfig) -> Dict[str, object]:
        key = self._cache_key(cfg)
        now = time.time()
        entry = self._entries.get(key)
        if entry and entry.expires_at > now:
            return entry.jwks

        jwks = self._fetch(cfg)
        self._entries[key] = _CacheEntry(jwks=jwks, expires_at=now + self.ttl_seconds)
        return jwks

    def _fetch(self, cfg: OIDCConfig) -> Dict[str, object]:
        url = f"{cfg.base_url}/realms/{cfg.realm}/protocol/openid-connect/certs"
        try:
            resp = requests.get(url, timeout=5)
        except requests.RequestException as exc:
            raise IDTokenVerificationError("jwks_fetch_failed") from exc
        if resp.status_code != 200:
            raise IDTokenVerificationError("jwks_fetch_failed")
        try:
            jwks = resp.json()
        except ValueError as exc:
            raise IDTokenVerificationError("jwks_invalid") from exc
        if not isinstance(jwks, dict) or "keys" not in jwks:
            raise IDTokenVerificationError("jwks_invalid")
        return jwks


JWKS_CACHE = JWKSCache()

MAX_CLOCK_SKEW_SECONDS = 5  # Allow minimal skew between servers

def verify_id_token(
    *,
    id_token: str,
    cfg: OIDCConfig,
    cache: JWKSCache | None = None,
) -> Dict[str, object]:
    """Validate an ID token using the realm JWKS and return claims.

    Parameters
    ----------
    id_token:
        The raw JWT string returned by Keycloak.
    cfg:
        OIDC configuration (realm, base URL, client id, redirect URI).
    cache:
        Optional JWKS cache (defaults to module-level cache).

    Raises
    ------
    IDTokenVerificationError:
        When the token is invalid (signature, issuer, audience, expiry, kid).
    """
    cache = cache or JWKS_CACHE
    jwks = cache.get(cfg)
    header = jwt.get_unverified_header(id_token)
    kid = header.get("kid")
    if not kid:
        raise IDTokenVerificationError("missing_kid")
    key_dict = _find_key(jwks, kid)
    if not key_dict:
        raise IDTokenVerificationError("unknown_kid")

    expected_issuer = f"{cfg.base_url}/realms/{cfg.realm}"
    try:
        claims = jwt.decode(
            id_token,
            key_dict,
            algorithms=[key_dict.get("alg", "RS256")],
            audience=cfg.client_id,
            issuer=expected_issuer,
            options={
                "verify_signature": True,
                "verify_aud": True,
                "verify_exp": False,
                "verify_iat": False,
                "verify_nbf": False,
                "verify_at_hash": False,
            },
        )
    except JOSEError as exc:
        raise IDTokenVerificationError("invalid_id_token") from exc

    _validate_temporal_claims(claims)

    return claims


def _find_key(jwks: Dict[str, object], kid: str) -> Dict[str, object] | None:
    keys = jwks.get("keys")
    if not isinstance(keys, list):
        return None
    for key in keys:
        if isinstance(key, dict) and key.get("kid") == kid:
            return key
    return None


def _validate_temporal_claims(claims: Dict[str, object]) -> None:
    now = time.time()
    exp = claims.get("exp")
    if not isinstance(exp, (int, float)):
        raise IDTokenVerificationError("invalid_id_token")
    if exp + MAX_CLOCK_SKEW_SECONDS < now:
        raise IDTokenVerificationError("invalid_id_token")

    iat = claims.get("iat")
    if isinstance(iat, (int, float)):
        if iat - MAX_CLOCK_SKEW_SECONDS > now:
            raise IDTokenVerificationError("invalid_id_token")

    nbf = claims.get("nbf")
    if isinstance(nbf, (int, float)) and nbf - MAX_CLOCK_SKEW_SECONDS > now:
        raise IDTokenVerificationError("invalid_id_token")
