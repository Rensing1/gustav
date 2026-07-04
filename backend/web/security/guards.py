"""Shared web security guards.

Why:
    Route modules should not duplicate role checks. Central helpers keep
    authorization semantics explicit while larger guard extraction continues.
"""

from __future__ import annotations

from collections.abc import Iterable


def normalized_roles(user: dict | None) -> set[str]:
    """Return lower-case roles from both `roles` and legacy primary `role`."""

    if not isinstance(user, dict):
        return set()
    roles: set[str] = set()
    raw_roles = user.get("roles")
    if isinstance(raw_roles, list):
        roles.update(str(item).lower() for item in raw_roles if isinstance(item, str))
    primary = user.get("role")
    if isinstance(primary, str) and primary:
        roles.add(primary.lower())
    return roles


def has_role(user: dict | None, role: str) -> bool:
    """Return whether a user has the requested role."""

    return role.lower() in normalized_roles(user)


def has_any_role(user: dict | None, roles: Iterable[str]) -> bool:
    """Return whether a user has any role in the requested set."""

    user_roles = normalized_roles(user)
    return any(role.lower() in user_roles for role in roles)
