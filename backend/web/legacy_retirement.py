"""Retirement handling for legacy FastAPI product UI entries."""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from backend.web.components import Layout
from backend.web.components.base import Component
from backend.web.layout_response import render_layout_response
from backend.web.security.guards import has_role


def is_deep_teaching_live_legacy_path(path_value: str) -> bool:
    """Return whether a path belongs to a retired deep Teaching-Live SSR entry."""

    parts = path_value.strip("/").split("/")
    if len(parts) < 6 or parts[0:2] != ["teaching", "courses"]:
        return False
    if parts[3] == "students" and len(parts) >= 6:
        return parts[-1] == "live"
    if len(parts) == 8 and parts[3] == "modules" and parts[5] == "sections":
        return parts[7] == "visibility"
    if parts[3] != "units" or len(parts) < 6 or parts[5] != "live":
        return False
    suffix = parts[6:]
    return suffix in (
        [],
        ["detail"],
        ["matrix"],
        ["matrix", "delta"],
        ["sections-panel"],
    )


def _render_retired_legacy_entry(
    request: Request,
    *,
    user: dict | None,
    legacy_path: str,
    replacement_space: str,
) -> HTMLResponse:
    """Render one consistent retirement notice for legacy FastAPI entries."""

    content = (
        '<div class="container">'
        '<h1>Legacy route retired</h1>'
        f'<p>Der alte FastAPI-Einstieg <code>{Component.escape(legacy_path)}</code> wird nicht mehr als produktive Startseite betrieben.</p>'
        f'<p>Die produktive Navigation liegt jetzt im neuen SvelteKit-Frontend für <strong>{Component.escape(replacement_space)}</strong>.</p>'
        "</div>"
    )
    layout = Layout(title="Legacy route retired", content=content, user=user, current_path=request.url.path)
    return render_layout_response(
        request,
        layout,
        status_code=410,
        headers={"Cache-Control": "private, no-store"},
    )


def retired_legacy_product_response(request: Request, user: dict | None) -> Response | None:
    """Return a retirement response for legacy FastAPI product paths.

    Why:
        After the SvelteKit cutover the Python web adapter should not carry
        productive `/courses*`, `/units*`, `/teaching/live*` or deep
        `/learning/courses*` journeys. Centralizing this decision makes the
        remaining legacy surface explicit.
    """

    path = request.url.path
    teacher_legacy = path == "/courses" or path.startswith("/courses/") or path == "/units" or path.startswith("/units/")
    teaching_live_legacy = (
        path == "/teaching/live"
        or path.startswith("/teaching/live/")
        or is_deep_teaching_live_legacy_path(path)
    )
    student_legacy = path == "/learning" or path.startswith("/learning/courses/")

    if teacher_legacy:
        if not has_role(user, "teacher"):
            return RedirectResponse(url="/", status_code=303, headers={"Cache-Control": "private, no-store"})
        return _render_retired_legacy_entry(
            request,
            user=user,
            legacy_path=path,
            replacement_space="die Lehrenden-Welt",
        )

    if student_legacy:
        if not has_role(user, "student"):
            return RedirectResponse(url="/", status_code=303, headers={"Cache-Control": "private, no-store"})
        return _render_retired_legacy_entry(
            request,
            user=user,
            legacy_path=path,
            replacement_space="den Lernendenraum",
        )

    if teaching_live_legacy:
        if not has_role(user, "teacher"):
            return RedirectResponse(url="/", status_code=303, headers={"Cache-Control": "private, no-store"})
        return _render_retired_legacy_entry(
            request,
            user=user,
            legacy_path=path,
            replacement_space="den Live-Raum",
        )

    return None
