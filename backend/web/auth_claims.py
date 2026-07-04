"""Pure helpers for mapping verified identity claims into GUSTAV auth state."""

from __future__ import annotations

from collections.abc import Mapping

from backend.identity_access.domain import ALLOWED_ROLES


def primary_role(roles: list[str]) -> str:
    """Return the compatibility role used by older route code.

    Why:
        Some legacy handlers still expect a single `role` string while newer
        auth state carries all roles. This helper keeps the narrowing rule in
        one place until those legacy callers are retired.

    Permissions:
        Call only after token verification or trusted session lookup. This
        helper does not authenticate; it only maps already-trusted role values.
    """

    priority = ["admin", "teacher", "student"]
    lowered = [role.lower() for role in roles if isinstance(role, str)]
    for role in priority:
        if role in lowered:
            return role
    return "student"


def roles_from_claims(claims: Mapping[str, object]) -> list[str]:
    """Extract allowed GUSTAV roles from verified OIDC claims."""

    raw_roles: list[str] = []
    realm_access = claims.get("realm_access") or {}
    if isinstance(realm_access, dict):
        roles = realm_access.get("roles")
        if isinstance(roles, list):
            raw_roles = [str(role) for role in roles]
    filtered = [role for role in raw_roles if role in ALLOWED_ROLES]
    return filtered or ["student"]


def display_name_from_claims(claims: Mapping[str, object]) -> str:
    """Choose the user-facing display name from verified OIDC claims."""

    email = str(claims.get("email") or claims.get("preferred_username") or "")
    return str(
        claims.get("gustav_display_name")
        or claims.get("name")
        or (email.split("@")[0] if email else "Benutzer")
    )


def user_context_from_claims(claims: Mapping[str, object]) -> dict[str, object]:
    """Build the compact auth user dict stored on FastAPI request state."""

    roles = roles_from_claims(claims)
    return {
        "sub": str(claims.get("sub") or "unknown-sub"),
        "name": display_name_from_claims(claims),
        "role": primary_role(roles),
        "roles": roles,
    }
