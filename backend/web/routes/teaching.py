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

from dataclasses import dataclass, asdict, is_dataclass
from datetime import datetime, timezone
from typing import Dict, List, Set
from uuid import uuid4

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from pydantic.functional_validators import field_validator


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
        # members[course_id] = { student_id: joined_at_iso }
        self.members: Dict[str, Dict[str, str]] = {}

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
        self.members.setdefault(cid, {})
        return course

    def list_courses_for_teacher(self, *, teacher_id: str, limit: int, offset: int) -> List[Course]:
        items = [c for c in self.courses.values() if c.teacher_id == teacher_id]
        return items[offset: offset + limit]

    def list_courses_for_student(self, *, student_id: str, limit: int, offset: int) -> List[Course]:
        # Simple scan; replace with indexed DB query later
        ids = [cid for cid, members in self.members.items() if student_id in (members or {}).keys()]
        items = [self.courses[cid] for cid in ids if cid in self.courses]
        return items[offset: offset + limit]

    def get_course(self, course_id: str) -> Course | None:
        return self.courses.get(course_id)

    def add_member(self, course_id: str, student_id: str) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        bucket = self.members.setdefault(course_id, {})
        if student_id in bucket:
            return False
        bucket[student_id] = now
        return True

    def list_members(self, course_id: str, limit: int, offset: int) -> List[tuple[str, str]]:
        bucket = self.members.get(course_id) or {}
        items = list(bucket.items())  # (student_id, joined_at)
        return items[offset: offset + limit]

    def remove_member(self, course_id: str, student_id: str) -> None:
        bucket = self.members.get(course_id) or {}
        bucket.pop(student_id, None)
        self.members[course_id] = bucket

    def update_course(self, course_id: str, *, title: str | None, subject: str | None, grade_level: str | None, term: str | None) -> Course | None:
        c = self.courses.get(course_id)
        if not c:
            return None
        if title is not None:
            t = title.strip()
            if not t or len(t) > 200:
                raise ValueError("invalid_title")
            c.title = t
        if subject is not None:
            c.subject = subject
        if grade_level is not None:
            c.grade_level = grade_level
        if term is not None:
            c.term = term
        c.updated_at = datetime.now(timezone.utc).isoformat()
        self.courses[course_id] = c
        return c

    def delete_course(self, course_id: str) -> bool:
        existed = course_id in self.courses
        self.courses.pop(course_id, None)
        self.members.pop(course_id, None)
        return existed


# Try to use DB-backed repo when available; fallback to in-memory for dev/tests
try:  # late import to avoid hard dependency during unit tests
    from teaching.repo_db import DBTeachingRepo  # type: ignore

    REPO = DBTeachingRepo()
except Exception:  # pragma: no cover - fallback for local unit tests
    REPO = _Repo()


# --- Request/Response models -----------------------------------------------------

class CourseCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    subject: str | None = Field(default=None, max_length=100)
    grade_level: str | None = Field(default=None, max_length=32)
    term: str | None = Field(default=None, max_length=32)

    @field_validator("subject", "grade_level", "term")
    @classmethod
    def _strip_empty(cls, v):
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


# --- User directory adapter (mockable) ------------------------------------------

def resolve_student_names(subs: list[str]) -> dict[str, str]:
    """Resolve user IDs to names via identity directory; test-friendly wrapper."""
    try:
        from identity_access import directory  # type: ignore
        return directory.resolve_student_names(subs)
    except Exception:
        return {s: s for s in subs}


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
    return [_serialize_course(c) for c in items]


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
    return JSONResponse(content=_serialize_course(course), status_code=201)


class CourseUpdate(BaseModel):
    # Accept raw strings (including empty) and validate in handler to return 400
    title: str | None = None
    subject: str | None = None
    grade_level: str | None = None
    term: str | None = None

    @field_validator("subject", "grade_level", "term")
    @classmethod
    def _strip_empty(cls, v):
        if isinstance(v, str):
            v = v.strip()
            return v if v else None
        return v


@teaching_router.patch("/api/teaching/courses/{course_id}")
async def update_course(request: Request, course_id: str, payload: CourseUpdate):
    """Update course fields — owner-only."""
    user = getattr(request.state, "user", None)
    sub = _current_sub(user)
    if not _role_in(user, "teacher"):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        if isinstance(REPO, DBTeachingRepo):
            updated = REPO.update_course_owned(
                course_id,
                sub,
                title=payload.title,
                subject=payload.subject,
                grade_level=payload.grade_level,
                term=payload.term,
            )
        else:
            course = REPO.get_course(course_id)
            if not course:
                return JSONResponse({"error": "not_found"}, status_code=404)
            owner_id = course["teacher_id"] if isinstance(course, dict) else getattr(course, "teacher_id", None)
            if sub != owner_id:
                return JSONResponse({"error": "forbidden"}, status_code=403)
            updated = REPO.update_course(
                course_id,
                title=payload.title,
                subject=payload.subject,
                grade_level=payload.grade_level,
                term=payload.term,
            )
    except ValueError:
        return JSONResponse({"error": "bad_request", "detail": "invalid field"}, status_code=400)
    return _serialize_course(updated) if updated else JSONResponse({"error": "not_found"}, status_code=404)


@teaching_router.delete("/api/teaching/courses/{course_id}")
async def delete_course(request: Request, course_id: str):
    """Delete a course and its memberships — owner-only."""
    user = getattr(request.state, "user", None)
    sub = _current_sub(user)
    if not _role_in(user, "teacher"):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        if isinstance(REPO, DBTeachingRepo):
            REPO.delete_course_owned(course_id, sub)
        else:
            course = REPO.get_course(course_id)
            if not course:
                return JSONResponse({"error": "not_found"}, status_code=404)
            owner_id = course["teacher_id"] if isinstance(course, dict) else getattr(course, "teacher_id", None)
            if sub != owner_id:
                return JSONResponse({"error": "forbidden"}, status_code=403)
            REPO.delete_course(course_id)
    except Exception:
        REPO.delete_course(course_id)
    return JSONResponse({}, status_code=204)


def _serialize_course(c) -> dict:
    if is_dataclass(c):
        return asdict(c)
    if isinstance(c, dict):
        return c
    # Last resort: attempt attribute access
    return {
        "id": getattr(c, "id", None),
        "title": getattr(c, "title", None),
        "subject": getattr(c, "subject", None),
        "grade_level": getattr(c, "grade_level", None),
        "term": getattr(c, "term", None),
        "teacher_id": getattr(c, "teacher_id", None),
        "created_at": getattr(c, "created_at", None),
        "updated_at": getattr(c, "updated_at", None),
    }


def _teacher_id_of(course) -> str | None:
    """Return the teacher_id from a Course (dataclass or dict)."""
    if isinstance(course, dict):
        return course.get("teacher_id")
    try:
        return getattr(course, "teacher_id", None)
    except Exception:
        return None


@teaching_router.get("/api/teaching/courses/{course_id}/members")
async def list_members(request: Request, course_id: str, limit: int = 20, offset: int = 0):
    """List members for a course — owner-only, with names resolved via directory adapter."""
    user = getattr(request.state, "user", None)
    sub = _current_sub(user)
    if not _role_in(user, "teacher"):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    limit = max(1, min(50, int(limit or 20)))
    offset = max(0, int(offset or 0))
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        if isinstance(REPO, DBTeachingRepo):
            pairs = REPO.list_members_for_owner(course_id, sub, limit=limit, offset=offset)
        else:
            # Fallback in-memory owner check
            course = REPO.get_course(course_id)
            if not course or _teacher_id_of(course) != sub:
                return JSONResponse({"error": "forbidden"}, status_code=403)
            pairs = REPO.list_members(course_id, limit=limit, offset=offset)
    except Exception:
        pairs = REPO.list_members(course_id, limit=limit, offset=offset)
    subs = [sid for sid, _ in pairs]
    names = resolve_student_names(subs)
    result = []
    for sid, joined_at in pairs:
        result.append({"sub": sid, "name": names.get(sid, sid), "joined_at": joined_at})
    return result


@teaching_router.post("/api/teaching/courses/{course_id}/members")
async def add_member(request: Request, course_id: str, payload: dict):
    """Add a student to a course — owner-only; idempotent (201 new, 204 existing)."""
    user = getattr(request.state, "user", None)
    sub = _current_sub(user)
    if not _role_in(user, "teacher"):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    student_sub = (payload or {}).get("student_sub")
    if not isinstance(student_sub, str) or not student_sub.strip():
        return JSONResponse({"error": "bad_request", "detail": "student_sub required"}, status_code=400)
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        if isinstance(REPO, DBTeachingRepo):
            created = REPO.add_member_owned(course_id, sub, student_sub.strip())
        else:
            # Fallback owner check
            course = REPO.get_course(course_id)
            if not course or _teacher_id_of(course) != sub:
                return JSONResponse({"error": "forbidden"}, status_code=403)
            created = REPO.add_member(course_id, student_sub.strip())
    except Exception:
        created = REPO.add_member(course_id, student_sub.strip())
    return JSONResponse({}, status_code=201 if created else 204)


@teaching_router.delete("/api/teaching/courses/{course_id}/members/{student_sub}")
async def remove_member(request: Request, course_id: str, student_sub: str):
    """Remove a student from a course — owner-only; idempotent 204."""
    user = getattr(request.state, "user", None)
    sub = _current_sub(user)
    if not _role_in(user, "teacher"):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        if isinstance(REPO, DBTeachingRepo):
            REPO.remove_member_owned(course_id, sub, str(student_sub))
        else:
            course = REPO.get_course(course_id)
            if not course or _teacher_id_of(course) != sub:
                return JSONResponse({"error": "forbidden"}, status_code=403)
            REPO.remove_member(course_id, str(student_sub))
    except Exception:
        REPO.remove_member(course_id, str(student_sub))
    return JSONResponse({}, status_code=204)
