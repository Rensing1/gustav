"""App-owned profile dependencies; no route-module lookup or shared overrides."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from fastapi import Request

from backend.identity_access.admin_client import AdminClient
from backend.identity_access.profile import ProfileIdentity
from backend.identity_access.tokens import verify_bearer_token
from backend.web.auth_runtime import AuthRuntime


@dataclass(frozen=True)
class ProfileProviders:
    """Provide request-scoped identity clients and verified fallback claims."""

    identity: Callable[[], ProfileIdentity]
    verify_claims: Callable[[str], dict[str, object]]


def create_profile_providers(runtime: AuthRuntime) -> ProfileProviders:
    """Bind production adapters to one app's OIDC runtime, without network I/O."""
    return ProfileProviders(
        identity=lambda: AdminClient(runtime.oidc_config),
        verify_claims=lambda token: verify_bearer_token(token=token, cfg=runtime.oidc_config),
    )


def profile_providers(request: Request) -> ProfileProviders:
    """Resolve only the serving app's dependencies; missing wiring fails closed."""
    return cast(ProfileProviders, request.app.state.profile_providers)
