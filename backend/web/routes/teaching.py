"""
Teaching (Unterrichten) API routes for course management.

Why:
    Provide minimal endpoints to create and list courses contract-first. The
    adapter enforces authentication (middleware) and authorization (role checks)
    and delegates persistence to an injected repository.

Notes:
    - Clean Architecture: Keep business rules simple and independent of FastAPI.
    - Security: Only teachers may create/update/delete courses. Students can list
      courses they belong to (not covered in the initial test slice).
    - Persistence: Prefers the Postgres-backed repo when psycopg and DSN are
      available; falls back to an in-memory repo for tests/local offline work.
      Tests can call `set_repo` to override the implementation for isolation.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, asdict, is_dataclass
from datetime import datetime, timezone
from typing import Dict, List, Set
from uuid import uuid4

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
import asyncio
from pydantic import BaseModel, Field
from pydantic.functional_validators import field_validator


teaching_router = APIRouter(tags=["Teaching"])  # explicit paths below
logger = logging.getLogger("gustav.web.teaching")


# --- In-memory persistence (MVP) -------------------------------------------------

_UNSET = object()


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

    def update_course(self, course_id: str, *, title=_UNSET, subject=_UNSET, grade_level=_UNSET, term=_UNSET) -> Course | None:
        c = self.courses.get(course_id)
        if not c:
            return None
        if title is not _UNSET:
            if title is None:
                raise ValueError("invalid_title")
            t = title.strip()
            if not t or len(t) > 200:
                raise ValueError("invalid_title")
            c.title = t
        if subject is not _UNSET:
            c.subject = subject
        if grade_level is not _UNSET:
            c.grade_level = grade_level
        if term is not _UNSET:
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
except Exception as exc:  # pragma: no cover - import failures in dev/test envs
    DBTeachingRepo = None  # type: ignore
    _DB_REPO_IMPORT_ERROR = exc
else:
    _DB_REPO_IMPORT_ERROR = None


def _build_default_repo():
    if DBTeachingRepo is None:
        if _DB_REPO_IMPORT_ERROR:
            logger.warning("Teaching repo import failed: %s", _DB_REPO_IMPORT_ERROR)
        return _Repo()
    try:
        return DBTeachingRepo()
    except Exception as exc:  # pragma: no cover - exercised when DSN missing
        logger.warning("Teaching repo unavailable (%s); using in-memory fallback", exc)
        return _Repo()


REPO = _build_default_repo()


def set_repo(repo) -> None:
    """Allow tests to swap the teaching repository implementation."""
    global REPO
    REPO = repo


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
    """Create a new course (teacher only).

    Why:
        Teachers own courses they create; the owner is derived from the authenticated
        subject (`sub`).

    Behavior:
        - 201 with `Course` on success
        - 400 on invalid `title` length
        - 403 when caller is not a teacher

    Permissions:
        Caller must have role `teacher` (owner becomes `teacher_id=sub`).
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
    # Mark this course id as seen by the owner to improve later 404 vs 403 semantics
    try:
        cid = course["id"] if isinstance(course, dict) else getattr(course, "id", None)
        if cid:
            _mark_seen_course(sub, str(cid))
    except Exception:
        pass
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
    """Update course fields — owner-only.

    Why:
        Allow owners to adjust metadata without changing ownership.

    Behavior:
        - 200 with updated `Course`
        - 400 on invalid fields (e.g., empty/too long title)
        - 403 when caller is not owner; 404 when course unknown (in-memory path)

    Permissions:
        Caller must be a teacher AND owner of the course.
    """
    user = getattr(request.state, "user", None)
    sub = _current_sub(user)
    if not _role_in(user, "teacher"):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    updates = payload.model_dump(mode="python", exclude_unset=True)
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        if isinstance(REPO, DBTeachingRepo):
            updated = REPO.update_course_owned(
                course_id,
                sub,
                **updates,
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
                **updates,
            )
    except ValueError:
        return JSONResponse({"error": "bad_request", "detail": "invalid field"}, status_code=400)
    if not updated:
        # DB repo returns None when caller is not owner or row not visible → 403
        return JSONResponse({"error": "forbidden"}, status_code=403)
    return _serialize_course(updated)


@teaching_router.delete("/api/teaching/courses/{course_id}")
async def delete_course(request: Request, course_id: str):
    """Delete a course and its memberships — owner-only.

    Why:
        Owners can remove their courses entirely; memberships are deleted via FK cascade.

    Behavior:
        - 204 on success (owner)
        - 404 when course does not exist (for owner)
        - 403 for non-owner

    Permissions:
        Caller must be a teacher AND owner of the course.
    """
    user = getattr(request.state, "user", None)
    sub = _current_sub(user)
    if not _role_in(user, "teacher"):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        if isinstance(REPO, DBTeachingRepo):
            # Owner check with ability to disambiguate 404 vs 403
            if not REPO.course_exists_for_owner(course_id, sub):
                ex = REPO.course_exists(course_id)
                if ex is False:
                    return JSONResponse({"error": "not_found"}, status_code=404)
                return JSONResponse({"error": "forbidden"}, status_code=403)
            REPO.delete_course_owned(course_id, sub)
            _mark_recently_deleted(sub, course_id)
            return Response(status_code=204)
        else:
            course = REPO.get_course(course_id)
            if not course:
                return JSONResponse({"error": "not_found"}, status_code=404)
            owner_id = course["teacher_id"] if isinstance(course, dict) else getattr(course, "teacher_id", None)
            if sub != owner_id:
                return JSONResponse({"error": "forbidden"}, status_code=403)
            REPO.delete_course(course_id)
            _mark_recently_deleted(sub, course_id)
            return Response(status_code=204)
    except Exception:
        # Conservative default: do not claim deletion if ownership/existence cannot be determined
        return JSONResponse({"error": "forbidden"}, status_code=403)


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

_RECENTLY_DELETED_TTL_SECONDS = 60.0
_RECENTLY_DELETED_BY: dict[str, dict[str, float]] = {}


def _prune_recently_deleted(owner_id: str, *, now: float | None = None) -> None:
    bucket = _RECENTLY_DELETED_BY.get(owner_id)
    if not bucket:
        return
    current = now if now is not None else time.time()
    expired = [cid for cid, ts in bucket.items() if current - ts > _RECENTLY_DELETED_TTL_SECONDS]
    for cid in expired:
        bucket.pop(cid, None)
    if not bucket:
        _RECENTLY_DELETED_BY.pop(owner_id, None)


def _mark_recently_deleted(owner_id: str, course_id: str) -> None:
    now = time.time()
    bucket = _RECENTLY_DELETED_BY.setdefault(owner_id, {})
    bucket[course_id] = now
    _prune_recently_deleted(owner_id, now=now)


_SEEN_COURSE_IDS_BY: dict[str, set[str]] = {}


def _mark_seen_course(owner_id: str, course_id: str) -> None:
    """Record that an owner has seen/owned this course id.

    Used to refine 404 vs 403 semantics after deletion time windows.
    """
    bucket = _SEEN_COURSE_IDS_BY.setdefault(owner_id, set())
    bucket.add(str(course_id))


def _was_recently_deleted(owner_id: str, course_id: str) -> bool:
    _prune_recently_deleted(owner_id)
    bucket = _RECENTLY_DELETED_BY.get(owner_id)
    if not bucket:
        return False
    return course_id in bucket


@teaching_router.get("/api/teaching/courses/{course_id}/members")
async def list_members(request: Request, course_id: str, limit: int = 20, offset: int = 0):
    """List members for a course — owner-only, with names resolved via directory adapter.

    Why:
        Owners need to view roster with minimal PII. Names are resolved on-the-fly
        from identity directory using stable `sub` identifiers.

    Behavior:
        - 200 with [{ sub, name, joined_at }]
        - 403 when caller is not owner; 404 directly after owner deleted course
        - Pagination via limit (1..50) and offset (>=0)

    Permissions:
        Caller must be a teacher AND owner of the course.
    """
    user = getattr(request.state, "user", None)
    sub = _current_sub(user)
    if not _role_in(user, "teacher"):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    limit = max(1, min(50, int(limit or 20)))
    offset = max(0, int(offset or 0))
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        if isinstance(REPO, DBTeachingRepo):
            if not REPO.course_exists_for_owner(course_id, sub):
                # If the same owner just deleted the course, treat as 404 for immediate follow-ups
                if _was_recently_deleted(sub, course_id):
                    return JSONResponse({"error": "not_found"}, status_code=404)
                # If we can determine that the course does not exist at all, choose 404 vs 403
                ex = REPO.course_exists(course_id)
                if ex is False:
                    seen = course_id in (_SEEN_COURSE_IDS_BY.get(sub) or set())
                    return JSONResponse({"error": "forbidden" if seen else "not_found"}, status_code=403 if seen else 404)
                # Otherwise do not disambiguate to avoid information leakage
                return JSONResponse({"error": "forbidden"}, status_code=403)
            pairs = REPO.list_members_for_owner(course_id, sub, limit=limit, offset=offset)
        else:
            # Fallback in-memory owner check
            course = REPO.get_course(course_id)
            if not course:
                return JSONResponse({"error": "not_found"}, status_code=404)
            if _teacher_id_of(course) != sub:
                return JSONResponse({"error": "forbidden"}, status_code=403)
            pairs = REPO.list_members(course_id, limit=limit, offset=offset)
    except Exception:
        pairs = REPO.list_members(course_id, limit=limit, offset=offset)
    subs = [sid for sid, _ in pairs]
    # Avoid blocking the event loop on synchronous network I/O
    names = await asyncio.to_thread(resolve_student_names, subs)
    result = []
    for sid, joined_at in pairs:
        result.append({"sub": sid, "name": names.get(sid, sid), "joined_at": joined_at})
    return result


@teaching_router.post("/api/teaching/courses/{course_id}/members")
async def add_member(request: Request, course_id: str, payload: dict):
    """Add a student to a course — owner-only; idempotent (201 new, 204 existing).

    Why:
        Allow owners to enroll students using stable `student_sub` identifiers.

    Behavior:
        - 201 when a new membership is created
        - 204 when the student is already a member
        - 400 when `student_sub` is missing/invalid; 403 when not owner

    Permissions:
        Caller must be a teacher AND owner of the course.
    """
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
            # Ensure caller owns the course; otherwise decide 404/403 via existence
            if not REPO.course_exists_for_owner(course_id, sub):
                ex = REPO.course_exists(course_id)
                if ex is False:
                    seen = course_id in (_SEEN_COURSE_IDS_BY.get(sub) or set())
                    return JSONResponse({"error": "forbidden" if seen else "not_found"}, status_code=403 if seen else 404)
                return JSONResponse({"error": "forbidden"}, status_code=403)
            created = REPO.add_member_owned(course_id, sub, student_sub.strip())
        else:
            # Fallback owner check
            course = REPO.get_course(course_id)
            if not course or _teacher_id_of(course) != sub:
                return JSONResponse({"error": "forbidden"}, status_code=403)
            created = REPO.add_member(course_id, student_sub.strip())
    except Exception:
        created = REPO.add_member(course_id, student_sub.strip())
    return JSONResponse({}, status_code=201) if created else Response(status_code=204)


@teaching_router.delete("/api/teaching/courses/{course_id}/members/{student_sub}")
async def remove_member(request: Request, course_id: str, student_sub: str):
    """Remove a student from a course — owner-only; idempotent 204.

    Behavior:
        - 204 even if the student is not currently a member
        - 403 when caller is not owner

    Permissions:
        Caller must be a teacher AND owner of the course.
    """
    user = getattr(request.state, "user", None)
    sub = _current_sub(user)
    if not _role_in(user, "teacher"):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        if isinstance(REPO, DBTeachingRepo):
            if not REPO.course_exists_for_owner(course_id, sub):
                ex = REPO.course_exists(course_id)
                if ex is False:
                    seen = course_id in (_SEEN_COURSE_IDS_BY.get(sub) or set())
                    return JSONResponse({"error": "forbidden" if seen else "not_found"}, status_code=403 if seen else 404)
                return JSONResponse({"error": "forbidden"}, status_code=403)
            REPO.remove_member_owned(course_id, sub, str(student_sub))
        else:
            course = REPO.get_course(course_id)
            if not course or _teacher_id_of(course) != sub:
                return JSONResponse({"error": "forbidden"}, status_code=403)
            REPO.remove_member(course_id, str(student_sub))
    except Exception:
        REPO.remove_member(course_id, str(student_sub))
    return Response(status_code=204)
