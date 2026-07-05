"""Basic health route for the FastAPI web adapter."""

from __future__ import annotations

from typing import Protocol

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse


class LayoutResponseBuilder(Protocol):
    """Compatibility shape for the app wiring call site."""

    def __call__(
        self,
        request: Request,
        layout: object,
        *,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
    ) -> HTMLResponse:
        ...


def create_basic_pages_router(layout_response: LayoutResponseBuilder) -> APIRouter:
    """Create the remaining basic runtime routes."""

    router = APIRouter()

    @router.get("/health")
    async def health_check():
        return JSONResponse({"status": "healthy"}, headers={"Cache-Control": "private, no-store"})

    return router
