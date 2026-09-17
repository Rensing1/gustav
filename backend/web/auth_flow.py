"""Small helpers for web authentication flow classification."""

from __future__ import annotations


def auth_failure_reason(auth_source: str) -> str:
    """Return a low-cardinality auth failure reason for logs."""

    if auth_source == "bearer":
        return "token_invalid"
    return "session_missing"


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
