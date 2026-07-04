"""Shared HTML layout response rendering for the remaining FastAPI shell."""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import HTMLResponse

from backend.web.components import Layout


def render_layout_response(
    request: Request,
    layout: Layout,
    *,
    status_code: int = 200,
    headers: dict[str, str] | None = None,
) -> HTMLResponse:
    """Render a Layout with HTMX-aware fragment behavior.

    Why:
        The shrinking FastAPI shell still serves a few HTML routes. Those routes
        must share one rule: normal requests get the full document, HTMX
        requests get only the fragment plus out-of-band sidebar updates.

    Permissions:
        None. Callers must finish their own role or course checks before they
        render a response.
    """

    body = layout.render_fragment() if request.headers.get("HX-Request") else layout.render()
    response = HTMLResponse(content=body, status_code=status_code)
    try:
        is_personalized = bool(getattr(request.state, "user", None))
    except Exception:
        is_personalized = False
    if is_personalized and not (headers and "Cache-Control" in headers):
        response.headers["Cache-Control"] = "private, no-store"
    if headers:
        for key, value in headers.items():
            response.headers[key] = value
    return response
