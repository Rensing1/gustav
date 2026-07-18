"""Stable HTTP error mapping for Teaching runtime dependencies.

Why:
    The Teaching adapter translates PostgreSQL connection failures into its
    context-owned error. Keeping the HTTP mapping outside reload-prone route
    modules lets FastAPI retain one stable handler identity during reloads.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.teaching.errors import TeachingRepositoryUnavailable


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
