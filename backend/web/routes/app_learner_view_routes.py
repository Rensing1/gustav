"""Learner home HTTP adapter with explicitly supplied course persistence."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.learning.usecases.home import LearnerHomeUseCase
from backend.web.learning_course_providers import learning_course_providers
from backend.web.routes.app_session_helpers import current_user, private_headers, user_payload
from backend.web.security.guards import has_role

app_learner_view_router = APIRouter(tags=["App"])


@app_learner_view_router.get("/api/learning/views/learner-home")
def get_learner_home(request: Request, limit: int = 12, offset: int = 0):
    """Return private current/past course choices for the authenticated student.

    Repository work runs in FastAPI's bounded threadpool. The existing course
    use case bounds pagination; membership visibility remains enforced by RLS.
    """
    user = current_user(request)
    if user is None:
        return JSONResponse(
            {"error": "unauthenticated"}, status_code=401, headers=private_headers()
        )
    if not has_role(user, "student"):
        return JSONResponse({"error": "forbidden"}, status_code=403, headers=private_headers())

    repo = learning_course_providers(request).repository()
    body = {
        "user": user_payload(user),
        **LearnerHomeUseCase(repo).execute(
            student_sub=str(user.get("sub") or ""),
            limit=int(limit or 12),
            offset=int(offset or 0),
        ),
    }
    return JSONResponse(body, headers=private_headers())
