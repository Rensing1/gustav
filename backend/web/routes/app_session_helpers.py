"""Session helper functions for application-level routes.

Why:
    The app route adapter owns many views. Session bootstrap, Browser-BFF
    session transport, private response headers, and small user payloads are a
    separate concern and should not make the route hotspot harder to read.
"""

from __future__ import annotations

from fastapi import Request


def runtime_from_request(request: Request) -> object | None:
    """Return the explicit app runtime when the ASGI app provides one."""

    try:
        runtime = getattr(getattr(request, "app", None).state, "runtime", None)
    except Exception:
        return None
    return runtime


def session_store(request: Request):
    """Return the app session store from the explicit app runtime."""

    runtime = runtime_from_request(request)
    if runtime is not None and hasattr(runtime, "session_store"):
        return runtime.session_store
    raise RuntimeError("app runtime session_store is not configured")


def runtime_settings(request: Request):
    """Return settings from the explicit app runtime."""

    runtime = runtime_from_request(request)
    if runtime is not None and hasattr(runtime, "settings"):
        return runtime.settings
    raise RuntimeError("app runtime settings are not configured")


def oidc_config(request: Request | None = None):
    """Return OIDC configuration from the explicit app runtime."""

    if request is not None:
        runtime = runtime_from_request(request)
        if runtime is not None and hasattr(runtime, "oidc_config"):
            return runtime.oidc_config
    raise RuntimeError("app runtime oidc_config is not configured")


def spaces_for_role(role: str) -> list[str]:
    """Return visible top-level workspaces for the primary app role."""

    if role == "student":
        return ["learning"]
    return ["teaching", "diagnostics", "live"]


def start_target_for_role(role: str) -> str:
    """Return the first app route for the primary app role."""

    if role == "student":
        return "/learning"
    return "/teaching"


def private_headers() -> dict[str, str]:
    """Return cache headers for authenticated app responses."""

    return {"Cache-Control": "private, no-store"}


def current_user(request: Request) -> dict | None:
    """Return the middleware-authenticated user payload, if present."""

    user = getattr(request.state, "user", None)
    return user if isinstance(user, dict) else None


def user_payload(user: dict) -> dict[str, object]:
    """Normalize a middleware user payload for app read models."""

    primary_role = str(user.get("role") or "student")
    return {
        "sub": str(user.get("sub") or ""),
        "name": str(user.get("name") or ""),
        "role": primary_role,
        "roles": [str(role) for role in (user.get("roles") or []) if isinstance(role, str)],
    }
