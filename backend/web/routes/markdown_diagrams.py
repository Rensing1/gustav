"""Authenticated browser adapter for the shared, transient diagram renderer."""

from __future__ import annotations

import json
import time

from anyio import CapacityLimiter, to_thread
from fastapi import APIRouter, Request

from backend.diagram_renderer import DiagramRenderError, render_sources
from backend.web.routes.security import _is_same_origin
from backend.web.routes.teaching_shared import _json_private, _private_error

markdown_diagrams_router = APIRouter(tags=["Markdown"])
_RENDER_LIMITER = CapacityLimiter(2)


@markdown_diagrams_router.post("/api/markdown/diagrams")
async def render_markdown_diagrams(request: Request):
    """Render submitted sources for signed-in teachers/students after CSRF checks.

    This endpoint reads no stored content. Authorizing material/task access stays
    with its existing API; source and generated images are never logged or saved.
    """
    user = getattr(request.state, "user", None)
    if not user:
        return _private_error({"error": "unauthorized"}, status_code=401)
    if not {"teacher", "student"}.intersection(user.get("roles") or []):
        return _private_error({"error": "forbidden"}, status_code=403)
    if not (request.headers.get("origin") or request.headers.get("referer")) or not _is_same_origin(
        request
    ):
        return _private_error({"error": "forbidden", "detail": "csrf_violation"}, status_code=403)
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 2 * 1024 * 1024:
            return _private_error({"error": "payload_too_large"}, status_code=413)
    try:
        payload = json.loads(body)
        if not isinstance(payload, dict) or set(payload) - {"sources", "theme"}:
            raise ValueError()
        sources, theme = payload.get("sources"), payload.get("theme", "light")
        if (
            not isinstance(sources, list)
            or not 1 <= len(sources) <= 100
            or theme not in ("light", "dark")
        ):
            raise ValueError()
        if any(not isinstance(source, str) or len(source) > 50_000 for source in sources):
            raise ValueError()
        if sum(map(len, sources)) > 200_000:
            return _private_error({"error": "payload_too_large"}, status_code=413)
    except (ValueError, TypeError):
        return _private_error(
            {"error": "bad_request", "detail": "invalid_diagram_batch"}, status_code=400
        )
    try:

        def render():
            return render_sources(
                sources,
                theme=theme,
                deadline=time.monotonic() + 30,
                max_output_bytes=8 * 1024 * 1024,
            )

        diagrams = await to_thread.run_sync(render, limiter=_RENDER_LIMITER)
        return _json_private({"diagrams": diagrams})
    except DiagramRenderError as exc:
        return _private_error({"error": exc.code}, status_code=exc.status)
