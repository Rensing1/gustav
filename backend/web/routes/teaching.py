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
from uuid import uuid4, UUID

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


@dataclass
class Unit:
    id: str
    title: str
    summary: str | None
    author_id: str
    created_at: str
    updated_at: str


@dataclass
class CourseModuleData:
    id: str
    course_id: str
    unit_id: str
    position: int
    context_notes: str | None
    created_at: str
    updated_at: str


class _Repo:
    def __init__(self) -> None:
        self.courses: Dict[str, Course] = {}
        # members[course_id] = { student_id: joined_at_iso }
        self.members: Dict[str, Dict[str, str]] = {}
        self.units: Dict[str, Unit] = {}
        self.course_modules: Dict[str, CourseModuleData] = {}
        self.modules_by_course: Dict[str, List[str]] = {}

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
        module_ids = self.modules_by_course.pop(course_id, [])
        for mid in module_ids:
            self.course_modules.pop(mid, None)
        return existed

    # --- Units (in-memory) -----------------------------------------------------
    def list_units_for_author(self, *, author_id: str, limit: int, offset: int) -> List[Unit]:
        items = [u for u in self.units.values() if u.author_id == author_id]
        items.sort(key=lambda u: u.created_at, reverse=True)
        return items[offset: offset + limit]

    def create_unit(self, *, title: str, summary: str | None, author_id: str) -> Unit:
        title = (title or "").strip()
        if not title or len(title) > 200:
            raise ValueError("invalid_title")
        if summary is not None:
            summary = summary.strip()
            if summary and len(summary) > 2000:
                raise ValueError("invalid_summary")
            if summary == "":
                summary = None
        now = datetime.now(timezone.utc).isoformat()
        uid = str(uuid4())
        unit = Unit(
            id=uid,
            title=title,
            summary=summary,
            author_id=author_id,
            created_at=now,
            updated_at=now,
        )
        self.units[uid] = unit
        return unit

    def get_unit_for_author(self, unit_id: str, author_id: str) -> Unit | None:
        unit = self.units.get(unit_id)
        if unit and unit.author_id == author_id:
            return unit
        return None

    def update_unit_owned(self, unit_id: str, author_id: str, *, title=_UNSET, summary=_UNSET) -> Unit | None:
        unit = self.get_unit_for_author(unit_id, author_id)
        if not unit:
            return None
        if title is not _UNSET:
            if title is None:
                raise ValueError("invalid_title")
            t = title.strip()
            if not t or len(t) > 200:
                raise ValueError("invalid_title")
            unit.title = t
        if summary is not _UNSET:
            if summary is None:
                unit.summary = None
            else:
                s = summary.strip()
                if s and len(s) > 2000:
                    raise ValueError("invalid_summary")
                unit.summary = s or None
        unit.updated_at = datetime.now(timezone.utc).isoformat()
        self.units[unit_id] = unit
        return unit

    def delete_unit_owned(self, unit_id: str, author_id: str) -> bool:
        unit = self.get_unit_for_author(unit_id, author_id)
        if not unit:
            return False
        self.units.pop(unit_id, None)
        # Remove modules referencing the unit
        to_remove = [mid for mid, mod in self.course_modules.items() if mod.unit_id == unit_id]
        for mid in to_remove:
            module = self.course_modules.pop(mid, None)
            if module:
                if module.course_id in self.modules_by_course:
                    lst = [m for m in self.modules_by_course[module.course_id] if m != mid]
                    self.modules_by_course[module.course_id] = lst
                    self._resequence_course_modules(module.course_id)
        return True

    def unit_exists_for_author(self, unit_id: str, author_id: str) -> bool:
        unit = self.units.get(unit_id)
        return bool(unit and unit.author_id == author_id)

    def unit_exists(self, unit_id: str) -> bool:
        return unit_id in self.units

    # --- Course modules (in-memory) --------------------------------------------
    def list_course_modules_for_owner(self, course_id: str, owner_id: str) -> List[CourseModuleData]:
        course = self.courses.get(course_id)
        if not course or course.teacher_id != owner_id:
            return []
        module_ids = self.modules_by_course.get(course_id, [])
        modules = [self.course_modules[mid] for mid in module_ids if mid in self.course_modules]
        modules.sort(key=lambda m: (m.position, m.id))
        return modules

    def create_course_module_owned(self, course_id: str, owner_id: str, *, unit_id: str, context_notes: str | None) -> CourseModuleData:
        course = self.courses.get(course_id)
        if not course or course.teacher_id != owner_id:
            raise PermissionError("course_forbidden")
        unit = self.units.get(unit_id)
        if not unit:
            raise LookupError("unit_not_found")
        if unit.author_id != owner_id:
            raise PermissionError("unit_forbidden")
        notes = None
        if context_notes is not None:
            notes = context_notes.strip()
            if notes == "":
                notes = None
            if notes and len(notes) > 2000:
                raise ValueError("invalid_context_notes")
        existing_ids = set(self.modules_by_course.get(course_id, []))
        if unit_id in (self.course_modules[mid].unit_id for mid in existing_ids):
            raise ValueError("duplicate_module")
        now = datetime.now(timezone.utc).isoformat()
        mid = str(uuid4())
        position = len(self.modules_by_course.get(course_id, [])) + 1
        module = CourseModuleData(
            id=mid,
            course_id=course_id,
            unit_id=unit_id,
            position=position,
            context_notes=notes,
            created_at=now,
            updated_at=now,
        )
        self.course_modules[mid] = module
        bucket = self.modules_by_course.setdefault(course_id, [])
        bucket.append(mid)
        return module

    def reorder_course_modules_owned(self, course_id: str, owner_id: str, module_ids: List[str]) -> List[CourseModuleData]:
        course = self.courses.get(course_id)
        if not course or course.teacher_id != owner_id:
            raise PermissionError("course_forbidden")
        existing = self.modules_by_course.get(course_id, [])
        if not existing:
            raise ValueError("no_modules")
        existing_set = set(existing)
        submitted_set = set(module_ids)
        if submitted_set != existing_set or len(module_ids) != len(existing):
            extra = submitted_set - existing_set
            if extra:
                if any(mid in self.course_modules for mid in extra):
                    raise LookupError("module_not_found")
                raise ValueError("module_mismatch")
            raise ValueError("module_mismatch")
        for idx, module_id in enumerate(module_ids, start=1):
            module = self.course_modules.get(module_id)
            if module:
                module.position = idx
                module.updated_at = datetime.now(timezone.utc).isoformat()
                self.course_modules[module_id] = module
        self.modules_by_course[course_id] = list(module_ids)
        return self.list_course_modules_for_owner(course_id, owner_id)

    def _resequence_course_modules(self, course_id: str) -> None:
        bucket = self.modules_by_course.get(course_id, [])
        bucket = [mid for mid in bucket if mid in self.course_modules]
        bucket.sort(key=lambda mid: self.course_modules[mid].position)
        for idx, module_id in enumerate(bucket, start=1):
            module = self.course_modules[module_id]
            module.position = idx
            module.updated_at = datetime.now(timezone.utc).isoformat()
            self.course_modules[module_id] = module
        self.modules_by_course[course_id] = bucket


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


def _require_teacher(request: Request):
    """Return (user, error_response) ensuring caller has teacher role."""
    user = getattr(request.state, "user", None)
    if not _role_in(user, "teacher"):
        return None, JSONResponse({"error": "forbidden"}, status_code=403)
    return user, None


def _is_uuid_like(value: str) -> bool:
    """Best-effort UUID format check without coercing FastAPI to return 422."""
    try:
        UUID(str(value))
    except (ValueError, TypeError):
        return False
    return True


def _guard_unit_author(unit_id: str, author_sub: str):
    """Validate unit ownership, returning an error response when access is denied."""
    if not _is_uuid_like(unit_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid unit_id"}, status_code=400)
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        if isinstance(REPO, DBTeachingRepo):
            if REPO.unit_exists_for_author(unit_id, author_sub):
                return None
            exists = REPO.unit_exists(unit_id)
            if exists is False:
                return JSONResponse({"error": "not_found"}, status_code=404)
            return JSONResponse({"error": "forbidden"}, status_code=403)
    except Exception:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    # Fallback for in-memory repo
    if hasattr(REPO, "unit_exists_for_author") and REPO.unit_exists_for_author(unit_id, author_sub):
        return None
    if hasattr(REPO, "unit_exists") and not REPO.unit_exists(unit_id):
        return JSONResponse({"error": "not_found"}, status_code=404)
    return JSONResponse({"error": "forbidden"}, status_code=403)


def _guard_course_owner(course_id: str, owner_sub: str):
    """Ensure caller owns the course, mapping to 404/403 appropriately."""
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        if isinstance(REPO, DBTeachingRepo):
            if REPO.course_exists_for_owner(course_id, owner_sub):
                return None
            return _resp_non_owner_or_unknown(course_id, owner_sub)
    except Exception:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    course = REPO.get_course(course_id)
    if not course:
        return JSONResponse({"error": "not_found"}, status_code=404)
    if _teacher_id_of(course) != owner_sub:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    return None


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
    try:
        course = REPO.create_course(
            title=payload.title.strip(),
            subject=payload.subject,
            grade_level=payload.grade_level,
            term=payload.term,
            teacher_id=sub,
        )
    except ValueError:
        # Map repo validation to contract 400
        return JSONResponse({"error": "bad_request", "detail": "invalid input"}, status_code=400)
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


class UnitCreatePayload(BaseModel):
    title: str | None = Field(default=None)
    summary: str | None = Field(default=None)

    @field_validator("title")
    @classmethod
    def _normalize_title(cls, v: str) -> str:
        if v is None:
            return None
        if isinstance(v, str):
            stripped = v.strip()
            return stripped or None
        return v

    @field_validator("summary")
    @classmethod
    def _normalize_summary(cls, v: str | None) -> str | None:
        if v is None:
            return None
        stripped = v.strip()
        return stripped or None


class UnitUpdatePayload(BaseModel):
    title: str | None = Field(default=None)
    summary: str | None = Field(default=None)

    @field_validator("title", mode="before")
    @classmethod
    def _normalize_title(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            stripped = v.strip()
            if not stripped:
                return None
            return stripped
        return v

    @field_validator("summary", mode="before")
    @classmethod
    def _normalize_summary(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            stripped = v.strip()
            return stripped or None
        return v


class CourseModuleCreatePayload(BaseModel):
    unit_id: str = Field(..., min_length=1)
    context_notes: str | None = Field(default=None, max_length=2000)

    @field_validator("context_notes")
    @classmethod
    def _normalize_notes(cls, v):
        if v is None:
            return None
        stripped = v.strip()
        return stripped or None


class CourseModuleReorderPayload(BaseModel):
    module_ids: List[str] = Field(..., min_length=1)


@teaching_router.patch("/api/teaching/courses/{course_id}")
async def update_course(request: Request, course_id: str, payload: CourseUpdate):
    """Update course fields — owner-only.

    Why:
        Allow owners to adjust metadata without changing ownership.

    Behavior:
        - 200 with updated `Course`
        - 400 on invalid fields (e.g., empty/too long title)
        - 403 when caller is not owner; 404 when course unknown (DB path disambiguates; in-memory returns 404 for unknown)

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
            # Contract-aligned semantics: disambiguate 404 vs 403 prior to mutation
            if not REPO.course_exists_for_owner(course_id, sub):
                ex = REPO.course_exists(course_id)
                if ex is False:
                    return JSONResponse({"error": "not_found"}, status_code=404)
                return JSONResponse({"error": "forbidden"}, status_code=403)
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
        # Should not normally happen after existence/ownership checks; keep conservative 403
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

@teaching_router.get("/api/teaching/units")
async def list_units(request: Request, limit: int = 20, offset: int = 0):
    """
    Return units authored by the current teacher.

    Parameters:
        request: FastAPI request with session context.
        limit: Pagination window size (1..50).
        offset: Pagination start index (>=0).

    Behavior:
        - 200 with a list of serialized units owned by the caller.
        - 403 when the caller is not a teacher.

    Permissions:
        Caller must have role `teacher`; units are filtered by `author_id == sub`.
    """
    user, error = _require_teacher(request)
    if error:
        return error
    limit = max(1, min(50, int(limit or 20)))
    offset = max(0, int(offset or 0))
    sub = _current_sub(user)
    try:
        units = REPO.list_units_for_author(author_id=sub, limit=limit, offset=offset)
    except Exception as exc:
        logger.warning("list_units failed for sub=%s err=%s", sub[-6:], exc.__class__.__name__)
        return JSONResponse({"error": "forbidden"}, status_code=403)
    return [_serialize_unit(u) for u in units]


@teaching_router.post("/api/teaching/units")
async def create_unit(request: Request, payload: UnitCreatePayload):
    """
    Create a reusable unit owned by the calling teacher.

    Parameters:
        request: FastAPI request with authenticated session.
        payload: Body containing `title` and optional `summary`.

    Behavior:
        - 201 with the persisted unit on success.
        - 400 when validation fails (e.g., blank/too long title).
        - 403 when the caller is not a teacher.

    Permissions:
        Caller must be a teacher; ownership is derived from the authenticated `sub`.
    """
    user, error = _require_teacher(request)
    if error:
        return error
    sub = _current_sub(user)
    try:
        title = payload.title or ""
        unit = REPO.create_unit(title=title, summary=payload.summary, author_id=sub)
    except ValueError as exc:
        detail = str(exc)
        if detail in {"invalid_title", "invalid_summary"}:
            return JSONResponse({"error": "bad_request", "detail": detail}, status_code=400)
        return JSONResponse({"error": "bad_request"}, status_code=400)
    except PermissionError:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    return JSONResponse(content=_serialize_unit(unit), status_code=201)


@teaching_router.patch("/api/teaching/units/{unit_id}")
async def update_unit(request: Request, unit_id: str, payload: UnitUpdatePayload):
    """
    Update metadata of a unit owned by the current teacher.

    Parameters:
        request: FastAPI request context.
        unit_id: Unit identifier (UUID string).
        payload: Partial update for `title` and/or `summary`.

    Behavior:
        - 200 with updated unit.
        - 400 when payload is empty or fails validation.
        - 403 when the caller is not the author.
        - 404 when the unit does not exist.

    Permissions:
        Caller must be a teacher and the author of the unit.
    """
    user, error = _require_teacher(request)
    if error:
        return error
    updates = payload.model_dump(mode="python", exclude_unset=True)
    if not updates:
        return JSONResponse({"error": "bad_request", "detail": "empty payload"}, status_code=400)
    sub = _current_sub(user)
    guard = _guard_unit_author(unit_id, sub)
    if guard:
        return guard
    try:
        updated = REPO.update_unit_owned(unit_id, sub, **updates)
    except ValueError as exc:
        detail = str(exc)
        return JSONResponse({"error": "bad_request", "detail": detail}, status_code=400)
    if not updated:
        return JSONResponse({"error": "not_found"}, status_code=404)
    return _serialize_unit(updated)


@teaching_router.delete("/api/teaching/units/{unit_id}")
async def delete_unit(request: Request, unit_id: str):
    """
    Delete a unit owned by the current teacher.

    Behavior:
        - 204 on success, cascading removal of associated modules.
        - 403 when caller is not the author.
        - 404 when the unit does not exist.

    Permissions:
        Caller must be a teacher and the author of the unit.
    """
    user, error = _require_teacher(request)
    if error:
        return error
    sub = _current_sub(user)
    guard = _guard_unit_author(unit_id, sub)
    if guard:
        return guard
    try:
        deleted = REPO.delete_unit_owned(unit_id, sub)
    except Exception:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    if not deleted:
        return JSONResponse({"error": "not_found"}, status_code=404)
    return Response(status_code=204)


@teaching_router.get("/api/teaching/courses/{course_id}/modules")
async def list_course_modules(request: Request, course_id: str):
    """
    List modules for a course owned by the current teacher.

    Parameters:
        request: FastAPI request with authenticated session.
        course_id: Target course identifier (UUID string).

    Behavior:
        - 200 with modules ordered by position.
        - 403 when caller is not the owner.
        - 404 when the course does not exist.

    Permissions:
        Caller must be a teacher and the owner of the course.
    """
    user, error = _require_teacher(request)
    if error:
        return error
    sub = _current_sub(user)
    guard = _guard_course_owner(course_id, sub)
    if guard:
        return guard
    try:
        modules = REPO.list_course_modules_for_owner(course_id, sub)
    except Exception as exc:
        logger.warning("list_course_modules failed cid=%s err=%s", course_id[-6:], exc.__class__.__name__)
        return JSONResponse({"error": "forbidden"}, status_code=403)
    return [_serialize_module(m) for m in modules]


@teaching_router.post("/api/teaching/courses/{course_id}/modules")
async def create_course_module(request: Request, course_id: str, payload: CourseModuleCreatePayload):
    """
    Attach a unit as a module within a course owned by the caller.

    Parameters:
        request: FastAPI request.
        course_id: Target course identifier.
        payload: Body containing `unit_id` and optional `context_notes`.

    Behavior:
        - 201 with the created module (next available position).
        - 400 on invalid input (e.g., notes too long).
        - 403 when caller is not the owner or unit author.
        - 404 when course/unit is missing.
        - 409 when the unit is already attached to the course.

    Permissions:
        Caller must be a teacher, own the course, and be the author of the unit.
    """
    user, error = _require_teacher(request)
    if error:
        return error
    sub = _current_sub(user)
    unit_id = payload.unit_id
    if not _is_uuid_like(unit_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid unit_id"}, status_code=400)
    try:
        guard_course = _guard_course_owner(course_id, sub)
        if guard_course:
            return guard_course
        guard_unit = _guard_unit_author(unit_id, sub)
        if guard_unit:
            return guard_unit
        module = REPO.create_course_module_owned(
            course_id,
            sub,
            unit_id=unit_id,
            context_notes=payload.context_notes,
        )
    except ValueError as exc:
        detail = str(exc)
        if detail == "duplicate_module":
            return JSONResponse({"error": "conflict"}, status_code=409)
        return JSONResponse({"error": "bad_request", "detail": detail}, status_code=400)
    except PermissionError:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404)
    return JSONResponse(content=_serialize_module(module), status_code=201)


@teaching_router.post("/api/teaching/courses/{course_id}/modules/reorder")
async def reorder_course_modules(request: Request, course_id: str, payload: CourseModuleReorderPayload):
    """
    Reorder modules within a course atomically.

    Parameters:
        request: FastAPI request.
        course_id: Target course identifier.
        payload: Ordered list of module IDs representing the desired sequence.

    Behavior:
        - 200 with modules reflecting the new order.
        - 400 on validation errors (duplicates, missing IDs).
        - 403 when caller is not the owner.
        - 404 when any referenced module is missing.

    Permissions:
        Caller must be a teacher and the owner of the course.
    """
    user, error = _require_teacher(request)
    if error:
        return error
    module_ids = payload.module_ids
    if len(set(module_ids)) != len(module_ids):
        # Guard early so duplicates short-circuit with a clear validation error.
        return JSONResponse({"error": "bad_request", "detail": "duplicate module ids"}, status_code=400)
    if any(not _is_uuid_like(mid) for mid in module_ids):
        return JSONResponse({"error": "bad_request", "detail": "invalid module_ids"}, status_code=400)
    sub = _current_sub(user)
    guard = _guard_course_owner(course_id, sub)
    if guard:
        return guard
    try:
        modules = REPO.reorder_course_modules_owned(course_id, sub, module_ids)
    except ValueError as exc:
        detail = str(exc)
        return JSONResponse({"error": "bad_request", "detail": detail}, status_code=400)
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404)
    except PermissionError:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    return [_serialize_module(m) for m in modules]


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


def _serialize_unit(u) -> dict:
    if is_dataclass(u):
        return asdict(u)
    if isinstance(u, dict):
        return u
    return {
        "id": getattr(u, "id", None),
        "title": getattr(u, "title", None),
        "summary": getattr(u, "summary", None),
        "author_id": getattr(u, "author_id", None),
        "created_at": getattr(u, "created_at", None),
        "updated_at": getattr(u, "updated_at", None),
    }


def _serialize_module(m) -> dict:
    if is_dataclass(m):
        return asdict(m)
    if isinstance(m, dict):
        return m
    return {
        "id": getattr(m, "id", None),
        "course_id": getattr(m, "course_id", None),
        "unit_id": getattr(m, "unit_id", None),
        "position": getattr(m, "position", None),
        "context_notes": getattr(m, "context_notes", None),
        "created_at": getattr(m, "created_at", None),
        "updated_at": getattr(m, "updated_at", None),
    }


def _teacher_id_of(course) -> str | None:
    """Return the teacher_id from a Course (dataclass or dict)."""
    if isinstance(course, dict):
        return course.get("teacher_id")
    try:
        return getattr(course, "teacher_id", None)
    except Exception:
        return None

_RECENTLY_DELETED_TTL_SECONDS = 15.0
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


def _was_recently_deleted(owner_id: str, course_id: str) -> bool:
    _prune_recently_deleted(owner_id)
    bucket = _RECENTLY_DELETED_BY.get(owner_id)
    if not bucket:
        return False
    return course_id in bucket


def _resp_non_owner_or_unknown(course_id: str, owner_sub: str):
    """Return 404 when course does not exist, else 403 (non-owner).

    Why:
        Centralizes 404 vs 403 semantics to avoid duplication and subtle
        inconsistencies across endpoints. Uses a short "recently deleted"
        window to make immediate follow-ups deterministic for owners.

    Behavior:
        - If the same owner recently deleted the course: 404.
        - If `REPO.course_exists` deterministically returns False: 404.
        - Otherwise: 403 to avoid leaking information.
    """
    # Owner just deleted? Prefer 404 for immediate follow-ups
    if _was_recently_deleted(owner_sub, course_id):
        return JSONResponse({"error": "not_found"}, status_code=404)
    try:
        ex = REPO.course_exists(course_id)
    except Exception:
        ex = None
    if ex is False:
        # Deterministic contract: non-existent course -> 404
        return JSONResponse({"error": "not_found"}, status_code=404)
    return JSONResponse({"error": "forbidden"}, status_code=403)


@teaching_router.get("/api/teaching/courses/{course_id}/members")
async def list_members(request: Request, course_id: str, limit: int = 20, offset: int = 0):
    """List members for a course — owner-only, with names resolved via directory adapter.

    Why:
        Owners need to view roster with minimal PII. Names are resolved on-the-fly
        from identity directory using stable `sub` identifiers.

    Behavior:
        - 200 with [{ sub, name, joined_at }]
        - 403 when caller is not owner; 404 when the course does not exist
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
                return _resp_non_owner_or_unknown(course_id, sub)
            pairs = REPO.list_members_for_owner(course_id, sub, limit=limit, offset=offset)
        else:
            # Fallback in-memory owner check
            course = REPO.get_course(course_id)
            if not course:
                return JSONResponse({"error": "not_found"}, status_code=404)
            if _teacher_id_of(course) != sub:
                return JSONResponse({"error": "forbidden"}, status_code=403)
            pairs = REPO.list_members(course_id, limit=limit, offset=offset)
    except Exception as exc:
        # Defensive default: if DB helper path fails, do not risk information leakage.
        # Log for observability, avoid logging full identifiers to minimize PII exposure.
        cid_tail = (course_id or "").replace("-", "")[-6:]
        logger.warning("list_members failed: cid_tail=%s err=%s", cid_tail, exc.__class__.__name__)
        return JSONResponse({"error": "forbidden"}, status_code=403)
    subs = [sid for sid, _ in pairs]
    # Avoid blocking the event loop on synchronous network I/O
    names = await asyncio.to_thread(resolve_student_names, subs)
    result = []
    for sid, joined_at in pairs:
        result.append({"sub": sid, "name": names.get(sid, sid), "joined_at": joined_at})
    return result


class AddMember(BaseModel):
    # Keep optional to return 400 (not FastAPI 422) when missing/empty
    student_sub: str | None = None


@teaching_router.post("/api/teaching/courses/{course_id}/members")
async def add_member(request: Request, course_id: str, payload: AddMember):
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
    student_sub = getattr(payload, "student_sub", None)
    if not isinstance(student_sub, str) or not student_sub.strip():
        return JSONResponse({"error": "bad_request", "detail": "student_sub required"}, status_code=400)
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        if isinstance(REPO, DBTeachingRepo):
            # Ensure caller owns the course; otherwise decide 404/403 via helper
            if not REPO.course_exists_for_owner(course_id, sub):
                return _resp_non_owner_or_unknown(course_id, sub)
            created = REPO.add_member_owned(course_id, sub, student_sub.strip())
        else:
            # Fallback owner check
            course = REPO.get_course(course_id)
            if not course:
                return JSONResponse({"error": "not_found"}, status_code=404)
            if _teacher_id_of(course) != sub:
                return JSONResponse({"error": "forbidden"}, status_code=403)
            created = REPO.add_member(course_id, student_sub.strip())
    except Exception:
        # Fail closed: do not attempt mutation without clear ownership/existence semantics
        return _resp_non_owner_or_unknown(course_id, sub)
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
                return _resp_non_owner_or_unknown(course_id, sub)
            REPO.remove_member_owned(course_id, sub, str(student_sub))
        else:
            course = REPO.get_course(course_id)
            if not course:
                return JSONResponse({"error": "not_found"}, status_code=404)
            if _teacher_id_of(course) != sub:
                return JSONResponse({"error": "forbidden"}, status_code=403)
            REPO.remove_member(course_id, str(student_sub))
    except Exception:
        # Fail closed: do not attempt mutation without clear ownership/existence semantics
        return _resp_non_owner_or_unknown(course_id, sub)
    return Response(status_code=204)
