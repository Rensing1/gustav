"""
JWT verification helpers for the identity_access bounded context.

Why: Keep cryptographic validation of ID tokens outside the web adapter so we
can unit test it independently and swap the persistence/cache later on.

Security: Validates the ID token signature with the realm's JWKS, ensures issuer,
audience, and expiration are respected. A bounded per-process cache supports Keycloak signing-key rotation.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from threading import Lock
from typing import Dict, Tuple

import requests
from jose import jwt
from jose.exceptions import JOSEError

from .oidc import OIDCConfig

logger = logging.getLogger("gustav.identity_access.tokens")

class IDTokenVerificationError(Exception):
    """Raised when the ID token fails verification."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class BearerTokenVerificationError(Exception):
    """Raised when a bearer JWT fails verification."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass
class _RealmKeys:
    lock: Lock = field(default_factory=Lock)
    jwks: Dict[str, object] | None = None
    expires_at: float = 0
    retry_after: float = 0
    error: str | None = None


class JWKSCache:
    """Share key retrieval per realm/process and bound untrusted refresh requests."""

    def __init__(self, ttl_seconds: int = 300):
        self.ttl_seconds = ttl_seconds
        self._states: Dict[Tuple[str, str], _RealmKeys] = {}
        self._states_lock = Lock()

    def _cache_key(self, cfg: OIDCConfig) -> Tuple[str, str]:
        return (cfg.base_url, cfg.realm)

    def get(self, cfg: OIDCConfig, *, force: bool = False,
            previous: Dict[str, object] | None = None) -> Dict[str, object]:
        """Return cached keys or make one bounded HTTP call under a realm lock.

        `previous` identifies the snapshot that missed a key: a concurrent
        caller's newer result suffices. During the five-second cooldown a new
        unknown key is temporarily unverifiable, not definitively invalid.
        Already cached valid keys remain usable even if a forced fetch failed.
        """
        key = self._cache_key(cfg)
        with self._states_lock:
            state = self._states.get(key)
            if state is None:
                state = self._states[key] = _RealmKeys()
        # A forged unknown kid must not stall checks using already valid keys.
        if not force and state.expires_at > time.monotonic() and state.jwks is not None:
            return state.jwks
        with state.lock:
            now = time.monotonic()
            if state.jwks is not None and state.expires_at > now:
                if not force or (previous is not None and state.jwks is not previous):
                    return state.jwks
            if state.retry_after > now:
                raise IDTokenVerificationError(state.error or 'jwks_refresh_deferred')
            try:
                jwks = self._fetch(cfg)
            except IDTokenVerificationError as exc:
                state.error = exc.code
                state.retry_after = time.monotonic() + 5
                raise
            state.jwks = jwks
            state.expires_at = time.monotonic() + self.ttl_seconds
            state.error = None
            state.retry_after = time.monotonic() + 5 if force else 0
            return jwks

    def _fetch(self, cfg: OIDCConfig) -> Dict[str, object]:
        url = f"{cfg.base_url}/realms/{cfg.realm}/protocol/openid-connect/certs"
        try:
            resp = requests.get(url, timeout=5)
        except requests.RequestException as exc:
            logger.warning("JWKS fetch failed: %s", exc.__class__.__name__)
            raise IDTokenVerificationError("jwks_fetch_failed") from exc
        if resp.status_code != 200:
            logger.warning("JWKS fetch returned status %s", resp.status_code)
            raise IDTokenVerificationError("jwks_fetch_failed")
        try:
            jwks = resp.json()
        except ValueError as exc:
            logger.warning("JWKS payload invalid JSON")
            raise IDTokenVerificationError("jwks_invalid") from exc
        if not isinstance(jwks, dict) or "keys" not in jwks:
            logger.warning("JWKS payload missing keys array")
            raise IDTokenVerificationError("jwks_invalid")
        return jwks


JWKS_CACHE = JWKSCache()

MAX_CLOCK_SKEW_SECONDS = 5  # Allow minimal skew between servers


def _expected_issuer(cfg: OIDCConfig) -> str:
    issuer_base = cfg.public_base_url or cfg.base_url
    return f"{issuer_base}/realms/{cfg.realm}"

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
    try:
        header = jwt.get_unverified_header(id_token)
    except JOSEError as exc:
        raise IDTokenVerificationError("invalid_id_token") from exc
    if header.get('alg') != 'RS256':
        raise IDTokenVerificationError('invalid_id_token')
    kid = header.get("kid")
    if not kid:
        raise IDTokenVerificationError("missing_kid")
    jwks = cache.get(cfg)
    key_dict = _find_key(jwks, kid)
    if not key_dict:
        key_dict = _find_key(cache.get(cfg, force=True, previous=jwks), kid)
    if not key_dict:
        raise IDTokenVerificationError("unknown_kid")

    expected_issuer = _expected_issuer(cfg)
    try:
        # Security: enforce RS256 (as configured in Keycloak) regardless of JWKS 'alg'
        claims = jwt.decode(
            id_token,
            key_dict,
            algorithms=["RS256"],
            audience=cfg.client_id,
            issuer=expected_issuer,
            options={
                "verify_signature": True,
                "verify_aud": True,
                "require_aud": True,
                "require_iat": True,
                "verify_exp": False,
                "verify_iat": False,
                "verify_nbf": False,
                "verify_at_hash": False,
            },
        )
    except JOSEError as exc:
        logger.warning("ID token JOSE verification failed: %s", exc.__class__.__name__)
        raise IDTokenVerificationError("invalid_id_token") from exc

    _validate_temporal_claims(claims)

    return claims


def verify_bearer_token(
    *,
    token: str,
    cfg: OIDCConfig,
    cache: JWKSCache | None = None,
) -> Dict[str, object]:
    """Validate a signed access token explicitly addressed to the GUSTAV API."""
    cache = cache or JWKS_CACHE
    try:
        header = jwt.get_unverified_header(token)
    except JOSEError as exc:
        logger.warning("Bearer token header decode failed: %s", exc.__class__.__name__)
        raise BearerTokenVerificationError("invalid_bearer_token") from exc
    if header.get('alg') != 'RS256':
        raise BearerTokenVerificationError('invalid_bearer_token')
    kid = header.get("kid")
    if not kid:
        raise BearerTokenVerificationError("missing_kid")
    try:
        jwks = cache.get(cfg)
    except IDTokenVerificationError as exc:
        raise BearerTokenVerificationError(exc.code) from exc
    key_dict = _find_key(jwks, kid)
    if not key_dict:
        try:
            key_dict = _find_key(cache.get(cfg, force=True, previous=jwks), kid)
        except IDTokenVerificationError as exc:
            raise BearerTokenVerificationError(exc.code) from exc
    if not key_dict:
        raise BearerTokenVerificationError("unknown_kid")

    try:
        claims = jwt.decode(
            token,
            key_dict,
            algorithms=["RS256"],
            issuer=_expected_issuer(cfg),
            options={
                "verify_signature": True,
                "verify_aud": False,
                "verify_exp": False,
                "verify_iat": False,
                "verify_nbf": False,
                "verify_at_hash": False,
            },
        )
    except JOSEError as exc:
        logger.warning("Bearer token JOSE verification failed: %s", exc.__class__.__name__)
        raise BearerTokenVerificationError("invalid_bearer_token") from exc

    try:
        _validate_temporal_claims(claims)
    except IDTokenVerificationError as exc:
        raise BearerTokenVerificationError("invalid_bearer_token") from exc
    _validate_bearer_audience(claims, "gustav-api")
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


def _validate_bearer_audience(claims: Dict[str, object], client_id: str) -> None:
    aud = claims.get("aud")
    if isinstance(aud, str) and aud == client_id:
        return
    if isinstance(aud, list) and client_id in [str(item) for item in aud]:
        return
    raise BearerTokenVerificationError("invalid_bearer_token")
