"""
Teaching (Unterrichten) API routes for course management (MVP).

Why:
    Provide minimal endpoints to create and list courses contract-first.
    This adapter enforces authentication (middleware) and authorization (role checks),
    and delegates persistence to an in-memory repository for the TDD slice.

Notes:
    - Clean Architecture: Keep business rules simple and independent of FastAPI.
    - Security: Only teachers may create/update/delete courses. Students can list
      courses they belong to (not covered in the initial test slice).
    - Persistence: In-memory, to be replaced by a DB adapter in a follow-up.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Dict, List, Set
from uuid import uuid4

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator


teaching_router = APIRouter(tags=["Teaching"])  # explicit paths below


# --- In-memory persistence (MVP) -------------------------------------------------

@dataclass
class Course:
    id: str
    title: str
    subject: str | None
    grade_level: str | None
    term: str | None
    teacher_id: str
    created_at: str
    updated_at: str


class _Repo:
    def __init__(self) -> None:
        self.courses: Dict[str, Course] = {}
        self.members: Dict[str, Set[str]] = {}

    def create_course(self, *, title: str, subject: str | None, grade_level: str | None, term: str | None, teacher_id: str) -> Course:
        now = datetime.now(timezone.utc).isoformat()
        cid = str(uuid4())
        course = Course(
            id=cid,
            title=title,
            subject=subject,
            grade_level=grade_level,
            term=term,
            teacher_id=teacher_id,
            created_at=now,
            updated_at=now,
        )
        self.courses[cid] = course
        self.members.setdefault(cid, set())
        return course

    def list_courses_for_teacher(self, *, teacher_id: str, limit: int, offset: int) -> List[Course]:
        items = [c for c in self.courses.values() if c.teacher_id == teacher_id]
        return items[offset: offset + limit]

    def list_courses_for_student(self, *, student_id: str, limit: int, offset: int) -> List[Course]:
        # Simple scan; replace with indexed DB query later
        ids = [cid for cid, members in self.members.items() if student_id in members]
        items = [self.courses[cid] for cid in ids if cid in self.courses]
        return items[offset: offset + limit]


REPO = _Repo()


# --- Request/Response models -----------------------------------------------------

class CourseCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    subject: str | None = Field(default=None, max_length=100)
    grade_level: str | None = Field(default=None, max_length=32)
    term: str | None = Field(default=None, max_length=32)

    @validator("subject", "grade_level", "term")
    def _strip_empty(cls, v):  # type: ignore[no-redef]
        if isinstance(v, str):
            v = v.strip()
            return v if v else None
        return v


def _role_in(user: dict | None, role: str) -> bool:
    if not user:
        return False
    roles = user.get("roles") or []
    if not isinstance(roles, list):
        return False
    return role in roles


def _current_sub(user: dict | None) -> str:
    if not user:
        return ""
    sub = user.get("sub")
    return str(sub) if sub else ""


# --- Routes ----------------------------------------------------------------------

@teaching_router.get("/api/teaching/courses")
async def list_courses(request: Request, limit: int = 20, offset: int = 0):
    """
    List courses for the current user with simple pagination.

    Behavior:
        - Teachers: return owned courses.
        - Students: return courses the student is a member of (empty in MVP unless managed elsewhere).
    """
    user = getattr(request.state, "user", None)
    sub = _current_sub(user)
    limit = max(1, min(50, int(limit or 20)))
    offset = max(0, int(offset or 0))
    if _role_in(user, "teacher"):
        items = REPO.list_courses_for_teacher(teacher_id=sub, limit=limit, offset=offset)
    else:
        items = REPO.list_courses_for_student(student_id=sub, limit=limit, offset=offset)
    return [asdict(c) for c in items]


@teaching_router.post("/api/teaching/courses")
async def create_course(request: Request, payload: CourseCreate):
    """
    Create a new course. Only allowed for users with the teacher role.

    Permissions:
        Caller must have role `teacher`. Uses the OIDC `sub` as `teacher_id`.
    """
    user = getattr(request.state, "user", None)
    if not _role_in(user, "teacher"):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    sub = _current_sub(user)
    course = REPO.create_course(
        title=payload.title.strip(),
        subject=payload.subject,
        grade_level=payload.grade_level,
        term=payload.term,
        teacher_id=sub,
    )
    return JSONResponse(content=asdict(course), status_code=201)

