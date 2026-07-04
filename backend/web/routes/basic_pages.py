"""Basic HTML and health routes for the remaining FastAPI web shell."""

from __future__ import annotations

from typing import Protocol

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from backend.web.components import Layout

class LayoutResponseBuilder(Protocol):
    """Callable shape for rendering a Layout into an HTML response."""

    def __call__(
        self,
        request: Request,
        layout: Layout,
        *,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
    ) -> HTMLResponse:
        ...


def create_basic_pages_router(layout_response: LayoutResponseBuilder) -> APIRouter:
    """Create routes for the small legacy shell pages and health endpoint."""

    router = APIRouter()

    @router.get("/", response_class=HTMLResponse)
    async def home(request: Request):
        # Minimal, neutral start page for the shrinking legacy shell.
        user = getattr(request.state, "user", None)
        content = """
        <div class=\"container\">
            <h1>Willkommen bei GUSTAV</h1>
            <p>Diese FastAPI-Weboberfläche wird schrittweise abgebaut. Die neue Produktoberfläche entsteht im separaten SvelteKit-Frontend mit klaren Räumen für Lernende, Lehrkräfte und Diagnostik.</p>
            <p>Der Backend-Webadapter bleibt vorerst für verbleibende Legacy-Flows, interne Übergänge und Betriebsschnittstellen bestehen. Neue Produktnavigation wird hier bewusst nicht mehr ausgerollt.</p>
            <p>GUSTAV bleibt dabei datenschutzkonform. Personenbezogene Daten werden weiterhin nur innerhalb der kontrollierten Systemgrenzen verarbeitet.</p>
        </div>
        """
        layout = Layout(title="Startseite", content=content, user=user, current_path=request.url.path)
        return layout_response(request, layout)

    @router.get("/health")
    async def health_check():
        return JSONResponse({"status": "healthy"}, headers={"Cache-Control": "private, no-store"})

    @router.get("/about", response_class=HTMLResponse)
    async def about_page(request: Request):
        user = getattr(request.state, "user", None)
        content = """
        <div class=\"container\">
            <h1>Über GUSTAV</h1>
            <p>Diese Seite wird demnächst freigeschaltet. Hier findest du Informationen darüber, wie GUSTAV funktioniert und welche Ziele mit dieser Plattform erreicht werden sollen.</p>
        </div>
        """
        layout = Layout(title="Über GUSTAV", content=content, user=user, current_path=request.url.path)
        return layout_response(request, layout, headers={"Cache-Control": "private, no-store"})

    return router
