"""Small helpers for web authentication flow classification."""

from __future__ import annotations


def requires_bff_bearer_auth(path: str) -> bool:
    """Return whether a path belongs to the BFF-owned read-model surface."""

    return path in ("/api/app/session-bootstrap", "/api/app/session-sync") or path.startswith(
        (
            "/api/app/profile",
            "/api/learning/concern-box/",
            "/api/learning/views/",
            "/api/teaching/concern-box/",
            "/api/teaching/views/",
            "/api/diagnostics/views/",
            "/api/live/views/",
        )
    )


def auth_failure_reason(auth_source: str) -> str:
    """Return a low-cardinality auth failure reason for logs."""

    if auth_source == "missing_bearer":
        return "session_bootstrap_missing_bearer"
    if auth_source == "bearer":
        return "session_bootstrap_invalid_bearer"
    return "bff_session_missing"


def auth_failure_path_class(path: str) -> str:
    """Return a low-cardinality path class without route parameters or PII."""

    if path.startswith("/api/app/"):
        return "api.app"
    if path.startswith("/api/learning/"):
        return "api.learning"
    if path.startswith("/api/teaching/"):
        return "api.teaching"
    if path.startswith("/api/diagnostics/"):
        return "api.diagnostics"
    if path.startswith("/api/"):
        return "api.other"
    if path.startswith("/internal/"):
        return "internal"
    if path.startswith("/backend-internal/"):
        return "backend_internal"
    return "other"
