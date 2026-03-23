"""Application-level read-model routes for the new web platform.

Why:
    SvelteKit needs a small shell bootstrap payload that is independent from
    legacy SSR concerns. This router is the first explicit room read-model
    endpoint in the FastAPI adapter.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.learning.usecases.courses import ListCoursesInput, ListCoursesUseCase

try:
    from . import learning as learning_routes
except ImportError:  # pragma: no cover - flat import fallback
    from routes import learning as learning_routes  # type: ignore


app_router = APIRouter(tags=["App"])


def _spaces_for_role(role: str) -> list[str]:
    if role == "student":
        return ["learning"]
    return ["teaching", "diagnostics", "live"]


def _start_target_for_role(role: str) -> str:
    if role == "student":
        return "/learning"
    return "/teaching"


def _private_headers() -> dict[str, str]:
    return {"Cache-Control": "private, no-store"}


def _current_user(request: Request) -> dict | None:
    user = getattr(request.state, "user", None)
    return user if isinstance(user, dict) else None


def _user_has_role(user: dict | None, role: str) -> bool:
    if not isinstance(user, dict):
        return False
    roles = user.get("roles")
    if isinstance(roles, list):
        normalized = {str(item).lower() for item in roles if isinstance(item, str)}
        if role.lower() in normalized:
            return True
    return str(user.get("role") or "").lower() == role.lower()


def _user_payload(user: dict) -> dict[str, object]:
    primary_role = str(user.get("role") or "student")
    return {
        "sub": str(user.get("sub") or ""),
        "name": str(user.get("name") or ""),
        "role": primary_role,
        "roles": [str(role) for role in (user.get("roles") or []) if isinstance(role, str)],
    }


def _list_learner_courses(student_sub: str, limit: int, offset: int) -> list[dict]:
    return ListCoursesUseCase(learning_routes._get_repo()).execute(  # type: ignore[attr-defined]
        ListCoursesInput(student_sub=student_sub, limit=limit, offset=offset)
    )


def _teacher_home_entries() -> list[dict[str, str]]:
    return [
        {
            "id": "courses",
            "title": "Kurse",
            "href": "/courses",
            "description": "Kurse organisieren und betreuen.",
        },
        {
            "id": "units",
            "title": "Lerneinheiten",
            "href": "/units",
            "description": "Lerneinheiten bearbeiten und strukturieren.",
        },
        {
            "id": "diagnostics",
            "title": "Diagnostik",
            "href": "/diagnostics",
            "description": "Diagnostische Sichten fuer Lehrkraefte.",
        },
        {
            "id": "live",
            "title": "Live",
            "href": "/live",
            "description": "Operative Kurs-Lerneinheit-Matrix.",
        },
    ]


@app_router.get("/api/app/session-bootstrap")
async def get_session_bootstrap(request: Request):
    """Return shell bootstrap data for the current authenticated session."""
    user = _current_user(request)
    if user is None:
        return JSONResponse({"error": "unauthenticated"}, status_code=401, headers=_private_headers())

    primary_role = str(user.get("role") or "student")
    body = {
        "user": _user_payload(user),
        "start_target": _start_target_for_role(primary_role),
        "spaces": _spaces_for_role(primary_role),
    }
    return JSONResponse(body, headers=_private_headers())


@app_router.get("/api/learning/views/learner-home")
async def get_learner_home(request: Request, limit: int = 12, offset: int = 0):
    """Return the learner home read-model with the current student's courses."""
    user = _current_user(request)
    if user is None:
        return JSONResponse({"error": "unauthenticated"}, status_code=401, headers=_private_headers())
    if not _user_has_role(user, "student"):
        return JSONResponse({"error": "forbidden"}, status_code=403, headers=_private_headers())

    items = _list_learner_courses(str(user.get("sub") or ""), limit=int(limit or 12), offset=int(offset or 0))
    body = {
        "user": _user_payload(user),
        "courses": [
            {
                "id": str(item.get("id") or ""),
                "title": str(item.get("title") or ""),
                "href": f"/learning/courses/{item.get('id')}",
            }
            for item in items
            if isinstance(item, dict)
        ],
    }
    return JSONResponse(body, headers=_private_headers())


@app_router.get("/api/teaching/views/teacher-home")
async def get_teacher_home(request: Request):
    """Return the teacher home read-model for the primary teaching spaces."""
    user = _current_user(request)
    if user is None:
        return JSONResponse({"error": "unauthenticated"}, status_code=401, headers=_private_headers())
    if not (_user_has_role(user, "teacher") or _user_has_role(user, "admin")):
        return JSONResponse({"error": "forbidden"}, status_code=403, headers=_private_headers())

    return JSONResponse(
        {"user": _user_payload(user), "entries": _teacher_home_entries()},
        headers=_private_headers(),
    )
