"""Stable HTTP error mapping for required runtime dependencies.

Why:
    Web adapters must fail closed when PostgreSQL is unavailable. Keeping the
    exception type outside reload-prone route modules also lets FastAPI retain
    one stable handler identity during tests and application reloads.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

try:
    from psycopg import OperationalError as DatabaseOperationalError
except ImportError:  # pragma: no cover - production images include psycopg
    DatabaseOperationalError = None  # type: ignore[assignment,misc]


class TeachingRepositoryUnavailable(RuntimeError):
    """Signal that the required Teaching PostgreSQL repository is unavailable."""


def _service_unavailable_response() -> JSONResponse:
    """Return the privacy-safe response shared by dependency failures."""

    return JSONResponse(
        {
            "error": "service_unavailable",
            "detail": "teaching_repository_unavailable",
        },
        status_code=503,
        headers={"Cache-Control": "private, no-store"},
    )


def install_runtime_error_handlers(app: FastAPI) -> None:
    """Install fail-closed mappings for repository startup and connection loss."""

    async def repository_unavailable_handler(
        _request: Request,
        _exc: Exception,
    ) -> JSONResponse:
        return _service_unavailable_response()

    app.add_exception_handler(TeachingRepositoryUnavailable, repository_unavailable_handler)
    if DatabaseOperationalError is not None:
        app.add_exception_handler(DatabaseOperationalError, repository_unavailable_handler)
