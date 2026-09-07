"""Teacher read adapter with explicit catalog dependencies."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.teaching.services.unit_catalog import UnitCatalogService
from backend.web.routes.app_session_helpers import current_user, private_headers, user_payload
from backend.web.security.guards import has_any_role
from backend.web.teacher_catalog_providers import teacher_catalog_providers

app_teacher_catalog_router = APIRouter(tags=["App"])


@app_teacher_catalog_router.get("/api/teaching/views/units/catalog")
def get_teacher_units_catalog(request: Request, query: str = "", sort: str | None = None):
    """Read only the authenticated teacher's searchable catalog in the threadpool."""
    user = current_user(request)
    if user is None:
        return JSONResponse(
            {"error": "unauthenticated"}, status_code=401, headers=private_headers()
        )
    if not has_any_role(user, {"teacher", "admin"}):
        return JSONResponse({"error": "forbidden"}, status_code=403, headers=private_headers())
    service = UnitCatalogService(teacher_catalog_providers(request).repository())
    return JSONResponse(
        {
            "user": user_payload(user),
            **service.catalog(str(user.get("sub") or ""), query, sort),
        },
        headers=private_headers(),
    )
