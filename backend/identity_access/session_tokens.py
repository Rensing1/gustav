"""Map verified OIDC tokens to the shared session's persisted values."""
from __future__ import annotations

import time

from .domain import ALLOWED_ROLES
from .tokens import (
    BearerTokenVerificationError,
    IDTokenVerificationError,
    verify_bearer_token,
    verify_id_token,
)
from .unified_sessions import SessionInvalid, SessionUnavailable


def session_values(tokens: dict, cfg, current=None, *, nonce: str | None = None) -> dict:
    """Validate both audiences and preserve subject identity across refreshes.

    Only verified access claims grant application roles. The token endpoint's
    refresh lifetime governs the session; there is no independent app timeout.
    """
    try:
        access = verify_bearer_token(token=tokens['access_token'], cfg=cfg)
        raw_id = tokens.get('id_token')
        identity = verify_id_token(id_token=raw_id, cfg=cfg) if raw_id else None
    except (BearerTokenVerificationError, IDTokenVerificationError) as exc:
        if exc.code in ('jwks_fetch_failed', 'jwks_invalid', 'jwks_refresh_deferred'):
            raise SessionUnavailable() from exc
        raise SessionInvalid() from exc
    except (KeyError, TypeError) as exc:
        raise SessionInvalid() from exc
    sub = access.get('sub')
    if not isinstance(sub, str) or not sub or (current and sub != current.sub):
        raise SessionInvalid()
    if identity and identity.get('sub') != sub:
        raise SessionInvalid()
    if nonce is not None and (not identity or identity.get('nonce') != nonce):
        raise SessionInvalid()
    now = time.time()
    try:
        lifetime = int(tokens['refresh_expires_in'])
        refresh_token = tokens['refresh_token']
        if lifetime <= 0 or not isinstance(refresh_token, str) or not refresh_token:
            raise ValueError()
    except (KeyError, ValueError, TypeError) as exc:
        raise SessionInvalid() from exc
    roles = [role for role in access.get('realm_access', {}).get('roles', []) if role in ALLOWED_ROLES]
    claims = identity or access
    name = claims.get('gustav_display_name') or claims.get('name') or (current.name if current else 'Benutzer')
    return dict(sub=sub, roles=roles, name=str(name), id_token=raw_id or current.id_token,
                access_token=tokens['access_token'], refresh_token=refresh_token,
                access_expires_at=float(access['exp']), expires_at=now + lifetime)
