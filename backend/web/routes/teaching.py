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

import json
import time
from dataclasses import dataclass, asdict, is_dataclass
import os
import re
import sys as _sys
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple
import asyncio
from uuid import uuid4, UUID

import httpx
from fastapi import APIRouter, Request
from fastapi.routing import APIRoute
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from pydantic.functional_validators import field_validator

from backend.teaching.services.materials import MaterialFileSettings, MaterialsService
from backend.teaching.services.live_student_overview import MAX_UNIT_IDS, StudentLiveOverviewService
from backend.teaching.storage import NullStorageAdapter, StorageAdapterProtocol
from backend.storage.config import get_submissions_bucket
from backend.web.routes.teaching_shared import (
    _current_sub,
    _is_uuid_like,
    _json_private,
    _private_error,
    _require_teacher,
    _role_in,
)
from backend.web.routes.teaching_serialization import (
    _build_latest_submission_payload,
    _build_live_delta_cells,
    _build_live_summary_rows,
    _serialize_course,
    _serialize_material,
    _serialize_module,
    _serialize_section,
    _serialize_task,
    _serialize_unit,
    _serialize_unit_graph_edge,
    _serialize_unit_module,
    _serialize_unit_phase_public,
)
from backend.web.routes.teaching_task_services import (
    _get_tasks_service,
    configure_task_service_repo_provider,
)
from backend.web.routes import teaching_authoring, teaching_guards
from backend.web.routes.teaching_authoring import (
    _get_unit_module_section_id_for_author,
    _is_signature_compat_type_error,
    configure_teaching_authoring_repo_provider,
)
from backend.web.routes.teaching_guards import (
    configure_teaching_guard_repo_provider,
)
teaching_router = APIRouter(tags=["Teaching"])  # explicit paths below
logger = logging.getLogger("gustav.web.teaching")


def _unit_delete_storage_metadata_dsn(repo: object) -> str | None:
    """Return the DSN used to read storage keys before a unit delete."""

    return (
        str(getattr(repo, "_service_dsn", "") or "").strip()
        or str(getattr(repo, "_dsn", "") or "").strip()
        or None
    )


def _metadata_page_keys(internal_metadata: Any) -> list[str]:
    """Extract PDF-derived page keys from a learning submission metadata value."""

    metadata = internal_metadata
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except json.JSONDecodeError:
            return []
    if not isinstance(metadata, dict):
        return []
    raw_page_keys = metadata.get("page_keys")
    if not isinstance(raw_page_keys, list):
        return []
    return [str(key).strip() for key in raw_page_keys if str(key or "").strip()]


def _collect_unit_delete_storage_objects(repo: object, *, unit_id: str) -> list[tuple[str, str]]:
    """Collect object storage entries that must be removed before deleting a unit.

    Why:
        PostgreSQL cascades remove relational rows, but Supabase Storage objects
        live outside those foreign keys. The route reads keys first and deletes
        the files before the database delete so failures can still abort safely.

    Permissions:
        The caller must already have passed the author guard for this unit.
    """

    dsn = _unit_delete_storage_metadata_dsn(repo)
    if not dsn:
        return []
    from backend.web.db_cursor import open_repo_cursor

    objects: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add(bucket: str, key: str | None) -> None:
        normalized_key = str(key or "").strip()
        if not normalized_key:
            return
        item = (bucket, normalized_key)
        if item not in seen:
            seen.add(item)
            objects.append(item)

    try:
        with open_repo_cursor(dsn=dsn) as (_conn, cur):
            cur.execute(
                """
                select storage_key
                  from public.unit_materials
                 where unit_id = %s
                   and kind = 'file'
                   and storage_key is not null
                """,
                (unit_id,),
            )
            for row in cur.fetchall():
                add(MATERIAL_FILE_SETTINGS.storage_bucket, row[0])

            cur.execute(
                """
                select ls.storage_key, ls.internal_metadata
                  from public.learning_submissions ls
                  join public.unit_tasks t on t.id = ls.task_id
                 where t.unit_id = %s
                   and (ls.storage_key is not null or ls.internal_metadata ? 'page_keys')
                """,
                (unit_id,),
            )
            submissions_bucket = get_submissions_bucket()
            for storage_key, internal_metadata in cur.fetchall():
                add(submissions_bucket, storage_key)
                for page_key in _metadata_page_keys(internal_metadata):
                    add(submissions_bucket, page_key)
    except Exception:
        logger.warning("unit delete storage metadata unavailable unit_id=%s", unit_id, exc_info=True)
        raise RuntimeError("storage_metadata_unavailable")

    return objects


def _delete_unit_storage_objects(objects: list[tuple[str, str]]) -> None:
    """Delete collected storage objects, failing closed when storage is unavailable."""

    if not objects:
        return
    delete_object = getattr(STORAGE_ADAPTER, "delete_object", None)
    if not callable(delete_object):
        raise RuntimeError("storage_adapter_not_configured")
    for bucket, key in objects:
        delete_object(bucket=bucket, key=key)


def _safe_download_filename(filename: str | None, fallback: str) -> str:
    raw = str(filename or "").strip()
    candidate = raw or fallback
    cleaned = "".join(ch for ch in candidate if ch not in {'"', "\r", "\n"})
    return cleaned or fallback


async def _download_bytes_with_limit(*, url: str, max_bytes: int, headers: dict[str, str] | None = None) -> bytes | None:
    """Fetch a private file download into memory with a hard size limit."""

    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=False) as client:
            async with client.stream("GET", url, headers=headers) as resp:
                code = int(getattr(resp, "status_code", 500))
                if 300 <= code < 400 or code >= 400:
                    return None
                out = bytearray()
                async for chunk in resp.aiter_bytes():
                    if not chunk:
                        continue
                    out.extend(chunk)
                    if len(out) > int(max_bytes):
                        return None
                return bytes(out)
    except Exception:
        return None


def _teaching_submission_file_href(
    *,
    course_id: str,
    unit_id: str,
    task_id: str,
    student_sub: str,
    disposition: str,
) -> str:
    return (
        f"/api/teaching/courses/{course_id}/units/{unit_id}/tasks/{task_id}/students/{student_sub}/submissions/latest/file"
        f"?disposition={disposition}"
    )

# Optional storage wiring helper (lazy rewire for local Supabase E2E)
try:  # pragma: no cover - simple import guard
    from backend.web.storage_wiring import wire_supabase_adapter_if_configured as _wire_storage  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    _wire_storage = None  # type: ignore


# --- In-memory persistence (MVP) -------------------------------------------------

_UNSET = object()


def _is_unset(value: object) -> bool:
    """Return True for this route sentinel or a reloaded materials sentinel."""

    if value is _UNSET:
        return True
    if type(value) is object:
        return True
    for module_name in ("backend.teaching.services.materials",):
        module = _sys.modules.get(module_name)
        if module is not None and value is getattr(module, "_UNSET", None):
            return True
    return False


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
    unit_type: str
    title: str
    summary: str | None
    author_id: str
    created_at: str
    updated_at: str


@dataclass
class SectionData:
    id: str
    unit_id: str
    title: str
    position: int
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


@dataclass
class MaterialData:
    id: str
    unit_id: str
    section_id: str
    title: str
    body_md: str
    position: int
    created_at: str
    updated_at: str
    kind: str = "markdown"
    storage_key: Optional[str] | None = None
    filename_original: Optional[str] | None = None
    mime_type: Optional[str] | None = None
    size_bytes: Optional[int] | None = None
    sha256: Optional[str] | None = None
    alt_text: Optional[str] | None = None


@dataclass
class TaskData:
    id: str
    unit_id: str
    section_id: str
    instruction_md: str
    criteria: List[str]
    teacher_context_md: Optional[str] | None
    due_at: Optional[str] | None
    max_attempts: Optional[int] | None
    position: int
    created_at: str
    updated_at: str
    kind: str = "native"
    h5p_content_id: Optional[str] | None = None
    h5p_display_options: Dict[str, Any] | None = None


@dataclass
class ConcernBoxEntryData:
    id: str
    course_id: str
    student_sub: str
    message_text: str
    anonymous: bool
    created_at: str
    archived_at: Optional[str] | None = None
    archived_by: Optional[str] | None = None


class _Repo:
    def __init__(self) -> None:
        self.courses: Dict[str, Course] = {}
        # members[course_id] = { student_id: joined_at_iso }
        self.members: Dict[str, Dict[str, str]] = {}
        self.units: Dict[str, Unit] = {}
        self.sections: Dict[str, SectionData] = {}
        self.section_ids_by_unit: Dict[str, List[str]] = {}
        self.course_modules: Dict[str, CourseModuleData] = {}
        self.modules_by_course: Dict[str, List[str]] = {}
        self.materials: Dict[str, MaterialData] = {}
        self.material_ids_by_section: Dict[str, List[str]] = {}
        self.tasks: Dict[str, TaskData] = {}
        self.task_ids_by_section: Dict[str, List[str]] = {}
        self.upload_intents: Dict[str, Dict[str, Any]] = {}
        self.module_section_releases: Dict[tuple[str, str], Dict[str, Any]] = {}
        self.concern_box_entries: Dict[str, ConcernBoxEntryData] = {}

    def create_course(self, *, title: str, subject: str | None, grade_level: str | None, term: str | None, teacher_id: str) -> Course:
        normalized = (title or "").strip()
        if not normalized or len(normalized) > 200:
            raise ValueError("invalid_title")
        now = datetime.now(timezone.utc).isoformat()
        cid = str(uuid4())
        course = Course(
            id=cid,
            title=normalized,
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

    def student_has_course(self, course_id: str, student_sub: str) -> bool:
        return student_sub in (self.members.get(course_id) or {})

    def create_concern_box_entry(
        self,
        *,
        course_id: str,
        student_sub: str,
        message_text: str,
        anonymous: bool,
    ) -> dict[str, Any] | None:
        text = (message_text or "").strip()
        if not text:
            raise ValueError("invalid_message_text")
        if not self.student_has_course(course_id, student_sub):
            return None
        now = datetime.now(timezone.utc).isoformat()
        entry_id = str(uuid4())
        entry = ConcernBoxEntryData(
            id=entry_id,
            course_id=course_id,
            student_sub=student_sub,
            message_text=text,
            anonymous=bool(anonymous),
            created_at=now,
        )
        self.concern_box_entries[entry_id] = entry
        return {"id": entry_id, "created_at": now}

    def list_concern_box_entries_for_teacher(self, owner_sub: str, scope: str) -> list[dict[str, Any]]:
        include_archived = scope == "archived"
        entries: list[dict[str, Any]] = []
        for entry in self.concern_box_entries.values():
            course = self.courses.get(entry.course_id)
            if not course or course.teacher_id != owner_sub:
                continue
            if include_archived != bool(entry.archived_at):
                continue
            entries.append(
                {
                    "id": entry.id,
                    "course_id": entry.course_id,
                    "course_title": course.title,
                    "student_sub": entry.student_sub,
                    "message_text": entry.message_text,
                    "anonymous": entry.anonymous,
                    "created_at": entry.created_at,
                    "archived_at": entry.archived_at,
                }
            )
        entries.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
        return entries

    def archive_concern_box_entry_owned(self, entry_id: str, owner_sub: str) -> bool:
        entry = self.concern_box_entries.get(entry_id)
        if not entry:
            return False
        course = self.courses.get(entry.course_id)
        if not course or course.teacher_id != owner_sub:
            return False
        entry.archived_at = datetime.now(timezone.utc).isoformat()
        entry.archived_by = owner_sub
        self.concern_box_entries[entry_id] = entry
        return True

    def restore_concern_box_entry_owned(self, entry_id: str, owner_sub: str) -> bool:
        entry = self.concern_box_entries.get(entry_id)
        if not entry:
            return False
        course = self.courses.get(entry.course_id)
        if not course or course.teacher_id != owner_sub:
            return False
        entry.archived_at = None
        entry.archived_by = None
        self.concern_box_entries[entry_id] = entry
        return True

    def update_course(self, course_id: str, *, title=_UNSET, subject=_UNSET, grade_level=_UNSET, term=_UNSET) -> Course | None:
        c = self.courses.get(course_id)
        if not c:
            return None
        if not _is_unset(title):
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

    def create_unit(self, *, title: str, summary: str | None, author_id: str, unit_type: str | None = None) -> Unit:
        title = (title or "").strip()
        if not title or len(title) > 200:
            raise ValueError("invalid_title")
        if summary is not None:
            summary = summary.strip()
            if summary and len(summary) > 2000:
                raise ValueError("invalid_summary")
            if summary == "":
                summary = None
        norm_type = (unit_type or "linear").strip().lower()
        if norm_type not in ("linear", "modular"):
            raise ValueError("invalid_unit_type")
        now = datetime.now(timezone.utc).isoformat()
        uid = str(uuid4())
        unit = Unit(
            id=uid,
            unit_type=norm_type,
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

    def section_exists_for_author(self, unit_id: str, section_id: str, author_id: str) -> bool:
        unit = self.units.get(unit_id)
        if not unit or unit.author_id != author_id:
            return False
        sec = self.sections.get(section_id)
        return bool(sec and sec.unit_id == unit_id)

    # --- Unit sections (in-memory) --------------------------------------------
    def list_sections_for_author(self, unit_id: str, author_id: str) -> List[SectionData]:
        unit = self.units.get(unit_id)
        if not unit or unit.author_id != author_id:
            return []
        ids = list(self.section_ids_by_unit.get(unit_id, []))
        items = [self.sections[sid] for sid in ids if sid in self.sections]
        items.sort(key=lambda s: (s.position, s.id))
        return items

    def create_section(self, unit_id: str, title: str, author_id: str) -> SectionData:
        unit = self.units.get(unit_id)
        if not unit or unit.author_id != author_id:
            raise PermissionError("unit_forbidden")
        t = (title or "").strip()
        if not t or len(t) > 200:
            raise ValueError("invalid_title")
        now = datetime.now(timezone.utc).isoformat()
        sid = str(uuid4())
        pos = len(self.section_ids_by_unit.get(unit_id, [])) + 1
        sec = SectionData(id=sid, unit_id=unit_id, title=t, position=pos, created_at=now, updated_at=now)
        self.sections[sid] = sec
        self.section_ids_by_unit.setdefault(unit_id, []).append(sid)
        self.material_ids_by_section.setdefault(sid, [])
        return sec

    def update_section_title(self, unit_id: str, section_id: str, title: str, author_id: str) -> SectionData | None:
        unit = self.units.get(unit_id)
        if not unit or unit.author_id != author_id:
            return None
        sec = self.sections.get(section_id)
        if not sec or sec.unit_id != unit_id:
            return None
        if title is None:
            raise ValueError("invalid_title")
        t = (title or "").strip()
        if not t or len(t) > 200:
            raise ValueError("invalid_title")
        sec.title = t
        sec.updated_at = datetime.now(timezone.utc).isoformat()
        self.sections[section_id] = sec
        return sec

    def delete_section(self, unit_id: str, section_id: str, author_id: str) -> bool:
        unit = self.units.get(unit_id)
        if not unit or unit.author_id != author_id:
            return False
        ids = self.section_ids_by_unit.get(unit_id, [])
        if section_id not in ids:
            return False
        # Remove and resequence
        self.sections.pop(section_id, None)
        material_ids = self.material_ids_by_section.pop(section_id, [])
        for mid in material_ids:
            self.materials.pop(mid, None)
        ids = [sid for sid in ids if sid != section_id]
        self.section_ids_by_unit[unit_id] = ids
        self._resequence_unit_sections(unit_id)
        return True

    def reorder_unit_sections_owned(self, unit_id: str, author_id: str, section_ids: List[str]) -> List[SectionData]:
        unit = self.units.get(unit_id)
        if not unit or unit.author_id != author_id:
            raise PermissionError("unit_forbidden")
        existing = list(self.section_ids_by_unit.get(unit_id, []))
        if not existing:
            raise ValueError("section_mismatch")
        if set(existing) != set(section_ids) or len(existing) != len(section_ids):
            # Cross-unit or unknown IDs → treat as mismatch in memory fallback
            raise ValueError("section_mismatch")
        # Apply new order and resequence positions
        self.section_ids_by_unit[unit_id] = list(section_ids)
        self._resequence_unit_sections(unit_id)
        return self.list_sections_for_author(unit_id, author_id)

    def _resequence_unit_sections(self, unit_id: str) -> None:
        ids = self.section_ids_by_unit.get(unit_id, [])
        for idx, sid in enumerate(ids, start=1):
            if sid in self.sections:
                sec = self.sections[sid]
                sec.position = idx
                sec.updated_at = datetime.now(timezone.utc).isoformat()
                self.sections[sid] = sec

    # --- Section materials (in-memory) ----------------------------------------
    def list_materials_for_section_owned(self, unit_id: str, section_id: str, author_id: str) -> List[MaterialData]:
        if not self.section_exists_for_author(unit_id, section_id, author_id):
            return []
        ids = list(self.material_ids_by_section.get(section_id, []))
        items = [self.materials[mid] for mid in ids if mid in self.materials]
        items.sort(key=lambda m: (m.position, m.id))
        return items

    def create_markdown_material(
        self, unit_id: str, section_id: str, author_id: str, *, title: str, body_md: str
    ) -> MaterialData:
        if not self.section_exists_for_author(unit_id, section_id, author_id):
            raise LookupError("section_not_found")
        t = (title or "").strip()
        if not t or len(t) > 200:
            raise ValueError("invalid_title")
        if body_md is None or not isinstance(body_md, str):
            raise ValueError("invalid_body_md")
        now = datetime.now(timezone.utc).isoformat()
        mid = str(uuid4())
        pos = len(self.material_ids_by_section.get(section_id, [])) + 1
        material = MaterialData(
            id=mid,
            unit_id=unit_id,
            section_id=section_id,
            title=t,
            body_md=body_md,
            position=pos,
            created_at=now,
            updated_at=now,
        )
        self.materials[mid] = material
        self.material_ids_by_section.setdefault(section_id, []).append(mid)
        return material

    def create_file_upload_intent(
        self,
        unit_id: str,
        section_id: str,
        author_id: str,
        *,
        intent_id: str,
        material_id: str,
        storage_key: str,
        filename: str,
        mime_type: str,
        size_bytes: int,
        expires_at: datetime,
    ) -> Dict[str, Any]:
        if not self.section_exists_for_author(unit_id, section_id, author_id):
            raise LookupError("section_not_found")
        record = {
            "intent_id": intent_id,
            "material_id": material_id,
            "unit_id": unit_id,
            "section_id": section_id,
            "author_id": author_id,
            "storage_key": storage_key,
            "filename": filename,
            "mime_type": mime_type,
            "size_bytes": size_bytes,
            "expires_at": expires_at,
            "consumed_at": None,
        }
        self.upload_intents[intent_id] = record
        return {
            "intent_id": intent_id,
            "material_id": material_id,
            "storage_key": storage_key,
            "filename": filename,
            "mime_type": mime_type,
            "size_bytes": size_bytes,
            "expires_at": expires_at,
            "consumed_at": None,
        }

    def get_upload_intent_owned(
        self,
        intent_id: str,
        unit_id: str,
        section_id: str,
        author_id: str,
    ) -> Optional[Dict[str, Any]]:
        record = self.upload_intents.get(intent_id)
        if not record:
            return None
        if (
            record["unit_id"] != unit_id
            or record["section_id"] != section_id
            or record["author_id"] != author_id
        ):
            return None
        return {
            "intent_id": record["intent_id"],
            "material_id": record["material_id"],
            "storage_key": record["storage_key"],
            "filename": record["filename"],
            "mime_type": record["mime_type"],
            "size_bytes": record["size_bytes"],
            "expires_at": record["expires_at"],
            "consumed_at": record["consumed_at"],
        }

    def finalize_upload_intent_create_material(
        self,
        intent_id: str,
        unit_id: str,
        section_id: str,
        author_id: str,
        *,
        title: str,
        alt_text: Optional[str],
        sha256: str,
    ) -> Tuple[Dict[str, Any], bool]:
        intent = self.upload_intents.get(intent_id)
        if not intent:
            raise LookupError("intent_not_found")
        if (
            intent["unit_id"] != unit_id
            or intent["section_id"] != section_id
            or intent["author_id"] != author_id
        ):
            raise LookupError("intent_not_found")
        now = datetime.now(timezone.utc)
        if intent["consumed_at"] is not None:
            material = self.materials.get(intent["material_id"])
            if material is None:
                raise LookupError("material_not_found")
            return asdict(material), False
        if intent["expires_at"] <= now:
            raise ValueError("intent_expired")
        if not self.section_exists_for_author(unit_id, section_id, author_id):
            raise LookupError("section_not_found")
        pos = len(self.material_ids_by_section.get(section_id, [])) + 1
        material = MaterialData(
            id=intent["material_id"],
            unit_id=unit_id,
            section_id=section_id,
            title=title,
            body_md="",
            position=pos,
            created_at=now.isoformat(),
            updated_at=now.isoformat(),
            kind="file",
            storage_key=intent["storage_key"],
            filename_original=intent["filename"],
            mime_type=intent["mime_type"],
            size_bytes=intent["size_bytes"],
            sha256=sha256,
            alt_text=alt_text,
        )
        self.materials[material.id] = material
        bucket = self.material_ids_by_section.setdefault(section_id, [])
        bucket.append(material.id)
        self.upload_intents[intent_id]["consumed_at"] = now
        return asdict(material), True

    def get_material_owned(
        self, unit_id: str, section_id: str, material_id: str, author_id: str
    ) -> MaterialData | None:
        if not self.section_exists_for_author(unit_id, section_id, author_id):
            return None
        mat = self.materials.get(material_id)
        if mat and mat.unit_id == unit_id and mat.section_id == section_id:
            return mat
        return None

    def update_material(
        self,
        unit_id: str,
        section_id: str,
        material_id: str,
        author_id: str,
        *,
        title=_UNSET,
        body_md=_UNSET,
        alt_text=_UNSET,
    ) -> MaterialData | None:
        mat = self.get_material_owned(unit_id, section_id, material_id, author_id)
        if not mat:
            return None
        if title is not _UNSET:
            if title is None:
                raise ValueError("invalid_title")
            t = (title or "").strip()
            if not t or len(t) > 200:
                raise ValueError("invalid_title")
            mat.title = t
        if not _is_unset(body_md):
            if mat.kind != "markdown":
                raise ValueError("invalid_body_md")
            if body_md is None or not isinstance(body_md, str):
                raise ValueError("invalid_body_md")
            mat.body_md = body_md
        if not _is_unset(alt_text):
            if alt_text is None:
                mat.alt_text = None
            elif not isinstance(alt_text, str):
                raise ValueError("invalid_alt_text")
            else:
                normalized_alt = alt_text.strip()
                if len(normalized_alt) > 500:
                    raise ValueError("invalid_alt_text")
                mat.alt_text = normalized_alt or None
        mat.updated_at = datetime.now(timezone.utc).isoformat()
        self.materials[material_id] = mat
        return mat

    def delete_material(self, unit_id: str, section_id: str, material_id: str, author_id: str) -> bool:
        if not self.section_exists_for_author(unit_id, section_id, author_id):
            return False
        ids = self.material_ids_by_section.get(section_id, [])
        if material_id not in ids:
            return False
        self.materials.pop(material_id, None)
        ids = [mid for mid in ids if mid != material_id]
        self.material_ids_by_section[section_id] = ids
        self._resequence_materials(section_id)
        return True

    def reorder_section_materials(
        self,
        unit_id: str,
        section_id: str,
        author_id: str,
        material_ids: List[str],
    ) -> List[MaterialData]:
        if not self.section_exists_for_author(unit_id, section_id, author_id):
            raise PermissionError("section_forbidden")
        existing = list(self.material_ids_by_section.get(section_id, []))
        if not existing:
            raise ValueError("material_mismatch")
        if set(existing) != set(material_ids) or len(existing) != len(material_ids):
            raise ValueError("material_mismatch")
        self.material_ids_by_section[section_id] = list(material_ids)
        self._resequence_materials(section_id)
        return self.list_materials_for_section_owned(unit_id, section_id, author_id)

    def _resequence_materials(self, section_id: str) -> None:
        ids = self.material_ids_by_section.get(section_id, [])
        for idx, mid in enumerate(ids, start=1):
            if mid in self.materials:
                mat = self.materials[mid]
                mat.position = idx
                mat.updated_at = datetime.now(timezone.utc).isoformat()
                self.materials[mid] = mat

    # --- Section tasks (in-memory) -------------------------------------------
    def list_tasks_for_section_owned(self, unit_id: str, section_id: str, author_id: str) -> List[TaskData]:
        if not self.section_exists_for_author(unit_id, section_id, author_id):
            return []
        ids = list(self.task_ids_by_section.get(section_id, []))
        tasks = [self.tasks[tid] for tid in ids if tid in self.tasks]
        tasks.sort(key=lambda t: (t.position, t.id))
        return tasks

    def create_task(
        self,
        unit_id: str,
        section_id: str,
        author_id: str,
        *,
        instruction_md: str,
        criteria: Sequence[str] | None = None,
        teacher_context_md: str | None = None,
        due_at=None,
        max_attempts: int | None = None,
        kind: str = "native",
        h5p_content_id: str | None = None,
        h5p_display_options: Dict[str, Any] | None = None,
    ) -> TaskData:
        if not self.section_exists_for_author(unit_id, section_id, author_id):
            raise PermissionError("section_forbidden")
        instruction = (instruction_md or "").strip()
        if not instruction:
            raise ValueError("invalid_instruction_md")
        crit = list(criteria or [])
        now = datetime.now(timezone.utc).isoformat()
        tid = str(uuid4())
        pos = len(self.task_ids_by_section.get(section_id, [])) + 1
        due_iso = None
        if due_at is not None:
            if isinstance(due_at, datetime):
                due_iso = due_at.astimezone(timezone.utc).isoformat()
            elif isinstance(due_at, str):
                due_iso = due_at
        task = TaskData(
            id=tid,
            unit_id=unit_id,
            section_id=section_id,
            instruction_md=instruction,
            criteria=crit,
            teacher_context_md=teacher_context_md.strip()
            if isinstance(teacher_context_md, str) and teacher_context_md.strip()
            else None,
            due_at=due_iso,
            max_attempts=max_attempts,
            position=pos,
            created_at=now,
            updated_at=now,
            kind=kind,
            h5p_content_id=h5p_content_id,
            h5p_display_options=dict(h5p_display_options or {}),
        )
        self.tasks[tid] = task
        bucket = self.task_ids_by_section.setdefault(section_id, [])
        bucket.append(tid)
        return task

    def update_task(
        self,
        unit_id: str,
        section_id: str,
        task_id: str,
        author_id: str,
        *,
        instruction_md=_UNSET,
        criteria=_UNSET,
        teacher_context_md=_UNSET,
        due_at=_UNSET,
        max_attempts=_UNSET,
        kind=_UNSET,
        h5p_content_id=_UNSET,
        h5p_display_options=_UNSET,
    ) -> TaskData | None:
        task = self.tasks.get(task_id)
        if not task or task.unit_id != unit_id or task.section_id != section_id:
            return None
        if not self.section_exists_for_author(unit_id, section_id, author_id):
            return None
        if instruction_md is not _UNSET:
            text = (instruction_md or "").strip()
            if not text:
                raise ValueError("invalid_instruction_md")
            task.instruction_md = text
        if criteria is not _UNSET:
            if criteria is None:
                task.criteria = []
            else:
                task.criteria = list(criteria)
        if teacher_context_md is not _UNSET:
            if teacher_context_md is None:
                task.teacher_context_md = None
            elif isinstance(teacher_context_md, str):
                stripped = teacher_context_md.strip()
                task.teacher_context_md = stripped or None
        if due_at is not _UNSET:
            if due_at is None:
                task.due_at = None
            elif isinstance(due_at, datetime):
                task.due_at = due_at.astimezone(timezone.utc).isoformat()
            elif isinstance(due_at, str):
                task.due_at = due_at
        if max_attempts is not _UNSET:
            task.max_attempts = max_attempts
        if kind is not _UNSET:
            task.kind = str(kind or "native")
        if h5p_content_id is not _UNSET:
            task.h5p_content_id = None if h5p_content_id is None else str(h5p_content_id)
        if h5p_display_options is not _UNSET:
            task.h5p_display_options = dict(h5p_display_options or {})
        task.updated_at = datetime.now(timezone.utc).isoformat()
        self.tasks[task_id] = task
        return task

    def delete_task(self, unit_id: str, section_id: str, task_id: str, author_id: str) -> bool:
        if not self.section_exists_for_author(unit_id, section_id, author_id):
            return False
        ids = self.task_ids_by_section.get(section_id, [])
        if task_id not in ids:
            return False
        self.tasks.pop(task_id, None)
        ids = [tid for tid in ids if tid != task_id]
        self.task_ids_by_section[section_id] = ids
        self._resequence_tasks(section_id)
        return True

    def reorder_section_tasks(
        self,
        unit_id: str,
        section_id: str,
        author_id: str,
        task_ids: List[str],
    ) -> List[TaskData]:
        if not self.section_exists_for_author(unit_id, section_id, author_id):
            raise PermissionError("section_forbidden")
        existing = list(self.task_ids_by_section.get(section_id, []))
        if not existing:
            raise ValueError("task_mismatch")
        if set(existing) != set(task_ids) or len(existing) != len(task_ids):
            raise ValueError("task_mismatch")
        self.task_ids_by_section[section_id] = list(task_ids)
        self._resequence_tasks(section_id)
        return self.list_tasks_for_section_owned(unit_id, section_id, author_id)

    def _resequence_tasks(self, section_id: str) -> None:
        ids = self.task_ids_by_section.get(section_id, [])
        for idx, tid in enumerate(ids, start=1):
            if tid in self.tasks:
                task = self.tasks[tid]
                task.position = idx
                task.updated_at = datetime.now(timezone.utc).isoformat()
                self.tasks[tid] = task

    # --- Course modules (in-memory) --------------------------------------------
    def list_course_modules_for_owner(self, course_id: str, owner_id: str) -> List[CourseModuleData]:
        course = self.courses.get(course_id)
        if not course or course.teacher_id != owner_id:
            return []
        module_ids = self.modules_by_course.get(course_id, [])
        modules = [self.course_modules[mid] for mid in module_ids if mid in self.course_modules]
        modules.sort(key=lambda m: (m.position, m.id))
        return modules

    def list_course_units_for_owner(self, course_id: str, owner_id: str) -> List[dict]:
        """Return attached units with titles ordered by course module position."""
        out: List[dict] = []
        for module in self.list_course_modules_for_owner(course_id, owner_id):
            unit = self.units.get(module.unit_id)
            if not unit:
                continue
            out.append(
                {
                    "id": unit.id,
                    "title": unit.title,
                    "position": int(module.position),
                }
            )
        out.sort(key=lambda item: (int(item.get("position") or 0), str(item.get("id") or "")))
        return out

    def course_has_member(self, course_id: str, owner_id: str, student_sub: str) -> bool:
        course = self.courses.get(course_id)
        if not course or course.teacher_id != owner_id:
            return False
        return str(student_sub) in (self.members.get(course_id) or {})

    def list_tasks_for_course_unit_owner(self, course_id: str, unit_id: str, owner_id: str) -> List[dict]:
        attached_unit_ids = {module.unit_id for module in self.list_course_modules_for_owner(course_id, owner_id)}
        if unit_id not in attached_unit_ids:
            return []
        tasks: List[dict] = []
        for section in self.list_sections_for_author(unit_id, owner_id):
            sec_id = section["id"] if isinstance(section, dict) else section.id
            sec_position = (
                int(section.get("position") or 0)
                if isinstance(section, dict)
                else int(getattr(section, "position", 0) or 0)
            )
            for task in self.list_tasks_for_section_owned(unit_id, sec_id, owner_id):
                if isinstance(task, dict):
                    tasks.append(
                        {
                            "id": str(task.get("id") or ""),
                            "instruction_md": str(task.get("instruction_md") or ""),
                            "position": int(task.get("position") or 0),
                            "kind": str(task.get("kind") or "native"),
                            "_section_position": sec_position,
                        }
                    )
                else:
                    tasks.append(
                        {
                            "id": str(task.id),
                            "instruction_md": str(task.instruction_md or ""),
                            "position": int(task.position),
                            "kind": str(getattr(task, "kind", "native") or "native"),
                            "_section_position": sec_position,
                        }
                    )
        # Preserve section order first so the in-memory fallback matches the
        # DB-backed course-scoped task projection across multiple sections.
        tasks.sort(
            key=lambda item: (
                int(item.get("_section_position") or 0),
                int(item.get("position") or 0),
                str(item.get("id") or ""),
            )
        )
        for index, task in enumerate(tasks, start=1):
            task["position"] = index
            task.pop("_section_position", None)
        return tasks

    def list_tasks_for_course_units_owner(
        self,
        course_id: str,
        unit_ids: Sequence[str],
        owner_id: str,
    ) -> List[dict]:
        """Return tasks for multiple attached course units in one normalized list.

        Why:
            The student overview renders several course units at once. Returning a
            single flattened list keeps the service free from per-unit repo calls
            while preserving the existing in-memory fallback behavior.
        """
        out: List[dict] = []
        for unit_id in unit_ids:
            for task in self.list_tasks_for_course_unit_owner(course_id, str(unit_id), owner_id):
                out.append(
                    {
                        "unit_id": str(unit_id),
                        "id": str(task.get("id") or ""),
                        "instruction_md": str(task.get("instruction_md") or ""),
                        "position": int(task.get("position") or 0),
                        "kind": str(task.get("kind") or "native"),
                    }
                )
        return out

    def list_latest_submission_aggregates_for_owner(
        self,
        *,
        course_id: str,
        owner_sub: str,
        student_sub: str,
        unit_ids: Sequence[str],
    ) -> List[dict]:
        """Return minimal submission aggregates for the in-memory fallback repo.

        The in-memory teaching repo does not model learning submissions. Returning
        an empty list keeps the overview deterministic for offline tests.
        """
        return []

    def list_unit_latest_submission_aggregates_for_owner(
        self,
        *,
        course_id: str,
        unit_id: str,
        owner_sub: str,
        student_subs: Sequence[str],
    ) -> List[dict]:
        """Return latest submission aggregates for one unit and learner page.

        Why:
            The in-memory repo has no submission storage. Returning an empty list
            preserves deterministic fallback behavior for offline tests.
        """
        return []

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

    def delete_course_module_owned(self, course_id: str, module_id: str, owner_id: str) -> bool:
        """Delete a module from a course if owned by `owner_id` and resequence."""
        course = self.courses.get(course_id)
        if not course or course.teacher_id != owner_id:
            return False
        module = self.course_modules.get(module_id)
        if not module or module.course_id != course_id:
            return False
        # Remove from storage
        self.course_modules.pop(module_id, None)
        bucket = self.modules_by_course.get(course_id, [])
        bucket = [mid for mid in bucket if mid != module_id]
        self.modules_by_course[course_id] = bucket
        # Resequence positions
        for idx, mid in enumerate(bucket, start=1):
            m = self.course_modules.get(mid)
            if m:
                m.position = idx
                m.updated_at = datetime.now(timezone.utc).isoformat()
                self.course_modules[mid] = m
        return True

    def set_module_section_visibility(
        self,
        course_id: str,
        module_id: str,
        section_id: str,
        owner_id: str,
        visible: bool,
    ) -> Dict[str, Any]:
        course = self.courses.get(course_id)
        if not course or course.teacher_id != owner_id:
            raise PermissionError("course_forbidden")
        module = self.course_modules.get(module_id)
        if not module or module.course_id != course_id:
            raise LookupError("module_not_found")
        unit = self.units.get(module.unit_id)
        if not unit or unit.author_id != owner_id:
            raise PermissionError("unit_forbidden")
        section = self.sections.get(section_id)
        if not section or section.unit_id != module.unit_id:
            raise LookupError("section_not_in_module")
        released_at = datetime.now(timezone.utc).isoformat() if visible else None
        record = {
            "course_module_id": module_id,
            "section_id": section_id,
            "visible": bool(visible),
            "released_at": released_at,
            "released_by": owner_id,
        }
        self.module_section_releases[(module_id, section_id)] = record
        return dict(record)

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
    from backend.teaching.repo_db import DBTeachingRepo  # type: ignore
except Exception as exc:  # pragma: no cover - import failures in dev/test envs
    DBTeachingRepo = None  # type: ignore
    _DB_REPO_IMPORT_ERROR = exc
else:
    _DB_REPO_IMPORT_ERROR = None


def _build_default_repo():
    """Prefer DB-backed TeachingRepo; fall back to in-memory if unavailable.

    Matches the original project behavior so DB-based contract tests run when
    a fake psycopg/test DSN is provided; otherwise we degrade gracefully.
    """
    if DBTeachingRepo is None:
        if _DB_REPO_IMPORT_ERROR:
            logger.warning("Teaching repo import failed: %s", _DB_REPO_IMPORT_ERROR)
        return _Repo()
    try:
        return DBTeachingRepo()
    except Exception as exc:  # pragma: no cover - exercised when DSN missing
        logger.warning("Teaching repo unavailable (%s); using in-memory fallback", exc)
        return _Repo()


"""Lazy repo accessor to avoid import-time DB checks in tests."""
_REPO = None


def _current_teaching_module() -> object | None:
    """Return the currently active Teaching module instance when available."""
    return _sys.modules.get("backend.web.routes.teaching")

def _get_repo():  # pragma: no cover - simple accessor
    global _REPO, REPO
    module = _current_teaching_module()
    current_repo = getattr(module, "_REPO", None) if module is not None else _REPO
    if current_repo is None:
        current_repo = _build_default_repo()
        if module is not None:
            setattr(module, "_REPO", current_repo)
            setattr(module, "REPO", current_repo)
    # Keep the public module-level alias in sync for tests that do
    # `isinstance(routes_module.REPO, ...)`.
    _REPO = current_repo
    REPO = current_repo
    return current_repo


def _get_current_teaching_repo_for_provider() -> Any:
    """Resolve the active Teaching repository after legacy route-module reloads."""

    module = _current_teaching_module()
    getter = getattr(module, "_get_repo", None) if module is not None else None
    if callable(getter):
        return getter()
    return _get_repo()


configure_task_service_repo_provider(_get_current_teaching_repo_for_provider)
configure_teaching_guard_repo_provider(_get_current_teaching_repo_for_provider)
configure_teaching_authoring_repo_provider(_get_current_teaching_repo_for_provider)


# Back-compat symbol used in tests: set_repo() and _get_repo() keep this public
# alias in sync after the first real repository access. Keeping it empty at
# import time avoids DB connection attempts during route inventory and imports.
REPO = None

# Allow overriding the storage bucket via environment for deployments
_bucket = os.getenv("SUPABASE_STORAGE_BUCKET") or MaterialFileSettings().storage_bucket
MATERIAL_FILE_SETTINGS = MaterialFileSettings(storage_bucket=_bucket)
STORAGE_ADAPTER: StorageAdapterProtocol = NullStorageAdapter()
_STORAGE_ADAPTER_OVERRIDE_ACTIVE = False


def _sync_teaching_route_globals(*, adapter: StorageAdapterProtocol, override_active: bool) -> None:
    """Retarget already-registered Teaching route globals to the current adapter.

    Why:
        Some tests reload `backend.web.routes.teaching` while keeping the original FastAPI
        app instance alive. Route callables still reference the globals of the
        module instance they were created from. Without this sync, changing the
        adapter on a freshly imported module leaves old endpoints bound to a
        stale adapter and makes the suite order-dependent.
    """

    apps = []
    for module_name in ("backend.web.main",):
        main_module = _sys.modules.get(module_name)
        app = getattr(main_module, "app", None) if main_module is not None else None
        if app is not None:
            apps.append(app)
    try:
        from backend.web.app_composition import iter_registered_apps

        apps.extend(iter_registered_apps())
    except Exception:
        pass
    seen_apps: set[int] = set()
    for app in apps:
        app_id = id(app)
        if app_id in seen_apps:
            continue
        seen_apps.add(app_id)
        routes = getattr(app, "routes", None)
        if not routes:
            continue
        for route in routes:
            if not isinstance(route, APIRoute):
                continue
            if not str(getattr(route, "path", "")).startswith("/api/teaching"):
                continue
            route_globals = getattr(route.endpoint, "__globals__", None)
            if isinstance(route_globals, dict) and "STORAGE_ADAPTER" in route_globals:
                route_globals["STORAGE_ADAPTER"] = adapter
                route_globals["_STORAGE_ADAPTER_OVERRIDE_ACTIVE"] = override_active
                bound_teaching = route_globals.get("teaching_routes")
                if bound_teaching is not None:
                    setattr(bound_teaching, "STORAGE_ADAPTER", adapter)
                    setattr(bound_teaching, "_STORAGE_ADAPTER_OVERRIDE_ACTIVE", override_active)


def _sync_teaching_route_repo(repo: Any) -> None:
    """Retarget already-registered Teaching route globals to the current repo."""

    apps = []
    for module_name in ("backend.web.main",):
        main_module = _sys.modules.get(module_name)
        app = getattr(main_module, "app", None) if main_module is not None else None
        if app is not None:
            apps.append(app)
    try:
        from backend.web.app_composition import iter_registered_apps

        apps.extend(iter_registered_apps())
    except Exception:
        pass
    seen_apps: set[int] = set()
    for app in apps:
        app_id = id(app)
        if app_id in seen_apps:
            continue
        seen_apps.add(app_id)
        routes = getattr(app, "routes", None)
        if not routes:
            continue
        for route in routes:
            if not isinstance(route, APIRoute):
                continue
            if not str(getattr(route, "path", "")).startswith("/api/teaching"):
                continue
            route_globals = getattr(route.endpoint, "__globals__", None)
            if isinstance(route_globals, dict) and "_REPO" in route_globals:
                route_globals["_REPO"] = repo
                route_globals["REPO"] = repo
                bound_teaching = route_globals.get("teaching_routes")
                if bound_teaching is not None:
                    setattr(bound_teaching, "_REPO", repo)
                    setattr(bound_teaching, "REPO", repo)

def _get_materials_service() -> MaterialsService:
    return MaterialsService(_get_repo(), settings=MATERIAL_FILE_SETTINGS)

def _get_student_live_overview_service() -> StudentLiveOverviewService:
    return StudentLiveOverviewService(_get_repo())


def _current_download_bytes_with_limit() -> Any:
    """Resolve the active download helper after reloads or monkeypatching."""

    module = _current_teaching_module()
    downloader = getattr(module, "_download_bytes_with_limit", None) if module is not None else None
    return downloader or _download_bytes_with_limit


def set_repo(repo) -> None:
    """Allow tests to swap the teaching repository implementation."""
    global _REPO, REPO
    _REPO = repo
    REPO = repo
    for module_name in ("backend.web.routes.teaching",):
        module = _sys.modules.get(module_name)
        if module is None:
            continue
        setattr(module, "_REPO", repo)
        setattr(module, "REPO", repo)
    _sync_teaching_route_repo(repo)


def set_storage_adapter(adapter: StorageAdapterProtocol, *, override: bool = True) -> None:
    """Allow tests to provide a storage adapter (e.g., fake or stub)."""
    global STORAGE_ADAPTER, _STORAGE_ADAPTER_OVERRIDE_ACTIVE
    STORAGE_ADAPTER = adapter
    _STORAGE_ADAPTER_OVERRIDE_ACTIVE = bool(override)
    for module_name in ("backend.web.routes.teaching",):
        module = _sys.modules.get(module_name)
        if module is None:
            continue
        setattr(module, "STORAGE_ADAPTER", adapter)
        setattr(module, "_STORAGE_ADAPTER_OVERRIDE_ACTIVE", bool(override))
    _sync_teaching_route_globals(adapter=adapter, override_active=_STORAGE_ADAPTER_OVERRIDE_ACTIVE)


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


def _canonical_uuid(value: str) -> str:
    """Return canonical lowercase UUID string."""
    return str(UUID(str(value)))


def _safe_int(value: Any) -> Optional[int]:
    """Parse an optional integer defensively."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _validate_uuid_id_list(
    raw_ids: object,
    *,
    array_detail: str,
    empty_detail: str,
    duplicate_detail: str,
    invalid_detail: str,
) -> tuple[list[str] | None, JSONResponse | None]:
    """Validate reorder payload id arrays without raising on unhashable items."""
    if not isinstance(raw_ids, list):
        return None, _private_error({"error": "bad_request", "detail": array_detail}, status_code=400)
    if len(raw_ids) == 0:
        return None, _private_error({"error": "bad_request", "detail": empty_detail}, status_code=400)

    ids: list[str] = []
    for item in raw_ids:
        if not isinstance(item, str):
            return None, _private_error({"error": "bad_request", "detail": invalid_detail}, status_code=400)
        norm = item.strip()
        if not norm or not _is_uuid_like(norm):
            return None, _private_error({"error": "bad_request", "detail": invalid_detail}, status_code=400)
        ids.append(_canonical_uuid(norm))

    if len(ids) != len(set(ids)):
        return None, _private_error({"error": "bad_request", "detail": duplicate_detail}, status_code=400)
    return ids, None


def _clamp_limit_offset(
    *,
    limit: int | None,
    offset: int | None,
    default_limit: int,
    max_limit: int = 50,
    zero_means_default: bool = True,
) -> tuple[int, int]:
    """Clamp list pagination consistently across Teaching endpoints."""
    try:
        norm_limit = int(limit) if limit is not None else default_limit
    except (TypeError, ValueError):
        norm_limit = default_limit
    if zero_means_default and norm_limit == 0:
        norm_limit = default_limit
    norm_limit = max(1, min(max_limit, norm_limit))
    try:
        norm_offset = int(offset) if offset is not None else 0
    except (TypeError, ValueError):
        norm_offset = 0
    norm_offset = max(0, norm_offset)
    return norm_limit, norm_offset


def _require_modular_repo_methods(repo: object, *method_names: str) -> JSONResponse | None:
    """Ensure modular endpoints run only when the repo implements required methods."""
    for method_name in method_names:
        if not callable(getattr(repo, method_name, None)):
            return _private_error({"error": "service_unavailable"}, status_code=503)
    return None


_MODULAR_UNIT_CREATE_REQUIRED_METHODS: tuple[str, ...] = (
    "list_unit_phases_for_author",
    "create_unit_phase",
    "update_unit_phase_title",
    "delete_unit_phase_for_author",
    "reorder_unit_phases_owned",
    "list_unit_modules_for_author",
    "create_unit_module_for_author",
    "update_unit_module_owned",
    "delete_unit_module_for_author",
    "list_unit_module_edges_for_author",
    "create_unit_module_edge_for_author",
    "delete_unit_module_edge_for_author",
    "reorder_unit_phase_modules_owned",
)


def _list_unit_modules_for_author_compat(repo: object, *, unit_id: str, author_id: str):
    """Call module listing with keyword args and controlled signature fallback."""
    try:
        return repo.list_unit_modules_for_author(unit_id=unit_id, author_id=author_id)  # type: ignore[attr-defined]
    except TypeError as exc:
        if not _is_signature_compat_type_error(exc):
            raise
        return repo.list_unit_modules_for_author(unit_id, author_id)  # type: ignore[attr-defined]


def compute_average_score_from_analysis(analysis: object) -> float | None:
    """Compute the average criteria score on a 0..10 scale from analysis_json.

    Rules:
        - Only criteria with numeric `score` values are considered.
        - `max_score` normalises each criterion to a 0..10 scale (default: 10).
        - Returns None when no valid numeric scores are present.
    """
    if not isinstance(analysis, dict):
        return None

    criteria = analysis.get("criteria_results")
    if not isinstance(criteria, list):
        return None

    normalized: list[float] = []
    for item in criteria:
        if not isinstance(item, dict):
            continue
        raw_score = item.get("score")
        if raw_score is None:
            continue
        try:
            score_val = float(raw_score)
        except (TypeError, ValueError):
            continue

        raw_max = item.get("max_score")
        try:
            max_val = float(raw_max)
        except (TypeError, ValueError):
            max_val = 10.0
        if max_val <= 0:
            max_val = 10.0

        scaled = score_val if max_val == 10.0 else (score_val / max_val * 10.0)
        scaled = max(0.0, min(10.0, scaled))
        normalized.append(scaled)

    if not normalized:
        return None
    return sum(normalized) / len(normalized)


def _load_average_scores_by_submission_id(
    repo,
    owner_sub: str,
    submission_ids_by_student: dict[str, list[str]],
) -> dict[str, float | None]:
    """Load average scores for submissions where analysis is completed.

    Why:
        The teacher live matrix must only display an average score once the
        asynchronous analysis pipeline finished. Submissions that exist but are
        still pending must expose `average_score=None` (not 0.0).

    Security:
        Reads happen under RLS by impersonating each student via
        `app.current_sub`.
    """
    if not submission_ids_by_student:
        return {}
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore
        if isinstance(repo, DBTeachingRepo):
            return repo.list_unit_live_average_scores_by_submission_id(
                owner_sub=owner_sub,
                submission_ids_by_student=submission_ids_by_student,
            )
    except Exception as exc:
        logger.warning("Unit live average score lookup failed — %s", exc)
    return {}


def _load_latest_submission_state_by_task(
    repo,
    owner_sub: str,
    course_id: str,
    task_ids_by_student: dict[str, list[str]],
) -> dict[tuple[str, str], dict[str, Any]]:
    """Load the latest submission state per `(student_sub, task_id)` under RLS."""
    if not task_ids_by_student:
        return {}
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore
        if isinstance(repo, DBTeachingRepo):
            return repo.list_unit_live_submission_state_by_task(
                owner_sub=owner_sub,
                course_id=course_id,
                task_ids_by_student=task_ids_by_student,
            )
    except Exception as exc:
        logger.warning("Unit live latest submission lookup failed — %s", exc)
    return {}


def _load_unit_live_helper_rows(
    repo,
    *,
    owner_sub: str,
    course_id: str,
    unit_id: str,
    updated_since_dt: datetime | None,
    limit: int,
    offset: int,
) -> list[dict[str, Any]]:
    """Load live helper rows compatibly across the old and new DB helper shapes.

    Why:
        The live matrix and delta endpoints recently started reading
        `score_raw/score_max` from `get_unit_latest_submissions_for_owner(...)`.
        Snapshot imports or partially migrated environments can still expose the
        older helper shape without these columns. We probe the new shape first
        and roll back to a savepoint before retrying the legacy projection.

    Returns:
        A normalized list of rows with stable keys:
        `student_sub`, `task_id`, `submission_id`, `score_raw`, `score_max`,
        `created_at_iso`, `completed_at_iso`, `h5p_completed`.
    """
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore
        if isinstance(repo, DBTeachingRepo):
            return repo.list_unit_live_helper_rows(
                owner_sub=owner_sub,
                course_id=course_id,
                unit_id=unit_id,
                updated_since_dt=updated_since_dt,
                limit=int(limit),
                offset=int(offset),
            )
    except Exception as exc:
        logger.warning("Unit live helper row lookup failed — %s", exc)
    return []


# --- User directory adapter (mockable) ------------------------------------------

def resolve_student_names(subs: list[str]) -> dict[str, str]:
    """Resolve user IDs to display names via Keycloak directory (humanized).

    - Always attempt the directory call; on failure, fall back to "Unbekannt".
    - Humanize returned identifiers (emails/usernames) to "Vorname Nachname".
    - Never expose SUBs in the names returned by this function.
    """
    out: dict[str, str] = {}
    try:
        from backend.identity_access import directory  # type: ignore
        raw = directory.resolve_student_names(subs)
        for sid in subs:
            val = str((raw or {}).get(sid, "")).strip()
            if not val or val == sid:
                # Directory could not resolve the SUB. As a pragmatic fallback
                # for legacy imports, derive a display name from the identifier
                # itself when it clearly encodes an email (or legacy-email:...).
                # This prevents leaking raw emails: the humanizer strips the
                # domain and known prefixes.
                fallback = ""
                try:
                    if sid.startswith("legacy-email:") or ("@" in sid):
                        fallback = directory.humanize_identifier(sid)  # type: ignore[attr-defined]
                except Exception:
                    fallback = ""
                out[sid] = fallback or "Unbekannt"
            else:
                # Humanize emails/legacy/username patterns
                nice = directory.humanize_identifier(val)  # type: ignore[attr-defined]
                out[sid] = nice or "Unbekannt"
        return out
    except Exception:
        return {s: "Unbekannt" for s in subs}


def resolve_live_student_names_by_sub(subs: list[str]) -> dict[str, str]:
    """Resolve `/live` learner labels with person-name priority.

    Why:
        The live room should prefer a learner's first/last name, but still fall
        back to a stable login-style localpart when profile data is incomplete.
        The hot path must avoid fetching a fresh admin token for every single
        learner lookup.
    """
    try:
        from backend.identity_access import directory  # type: ignore
        return directory.resolve_live_student_names_by_sub(subs)  # type: ignore[attr-defined]
    except Exception:
        return _resolve_student_login_labels_runtime(subs)


def _summary_snapshot_cursor(repo: Any, owner_sub: str | None = None) -> str | None:
    """Return a DB-based live summary cursor when the teaching repo has a DSN.

    Why:
        The live dashboard seeds its next delta poll from the summary response.
        Using the database clock avoids host/DB skew that could otherwise hide a
        submission created right after the summary call. If the DB seed cannot be
        read, the caller must fail closed instead of silently inventing a host
        clock fallback.
    """
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore
        if not isinstance(repo, DBTeachingRepo):
            return None
        if owner_sub is None:
            owner_sub = ""
        return repo.get_statement_timestamp(owner_sub=owner_sub)
    except Exception:
        return None
    return None


_DEFAULT_SUMMARY_SNAPSHOT_CURSOR = _summary_snapshot_cursor


def _resolve_student_names_runtime(subs: list[str]) -> dict[str, str]:
    """Resolve student names via the currently active Teaching module."""

    return resolve_student_names(subs)


def _resolve_student_login_labels_runtime(subs: list[str]) -> dict[str, str]:
    """Resolve login labels via the currently active Teaching module."""

    return resolve_student_login_labels_by_sub(subs)


def _summary_snapshot_cursor_runtime(repo: Any, owner_sub: str) -> str | None:
    """Resolve the active live summary cursor helper from the current module."""

    default = globals().get("_DEFAULT_SUMMARY_SNAPSHOT_CURSOR")
    local = _summary_snapshot_cursor
    if default is not None and callable(local) and local is not default:
        resolver = local
    else:
        module = _current_teaching_module()
        current = getattr(module, "_summary_snapshot_cursor", None) if module is not None else None
        resolver = current if default is not None and callable(current) and current is not default else local
    try:
        return resolver(repo, owner_sub)
    except TypeError:
        return resolver(repo)


def _current_max_unit_ids() -> int:
    """Return the active live-overview unit-id limit."""

    try:
        return max(1, int(MAX_UNIT_IDS))
    except Exception:
        return MAX_UNIT_IDS


def resolve_student_login_labels_by_sub(subs: list[str]) -> dict[str, str]:
    """Resolve user ids to login-style labels via direct directory lookups.

    Why:
        Live teacher views should show stable login identifiers, but must avoid
        the O(directory) role-member scan that the members page uses.
    """
    unique_subs = list(dict.fromkeys(str(sid or "").strip() for sid in subs if str(sid or "").strip()))
    if not unique_subs:
        return {}
    out: dict[str, str] = {}

    def _normalize_login_label(raw: str) -> str:
        value = str(raw or "").strip()
        if not value:
            return ""
        if value.startswith("legacy-email:"):
            value = value.split(":", 1)[1].strip()
        if "@" in value:
            value = value.split("@", 1)[0].strip()
        return value

    try:
        from backend.identity_access import directory  # type: ignore

        raw = directory.resolve_student_login_labels_by_sub(unique_subs)  # type: ignore[attr-defined]
        for sid in unique_subs:
            label = _normalize_login_label((raw or {}).get(sid, ""))
            if label and label.lower() != "unbekannt":
                out[sid] = label
                continue
            fallback = ""
            try:
                fallback = directory.localpart_identifier(sid)  # type: ignore[attr-defined]
            except Exception:
                fallback = ""
            out[sid] = fallback or "Unbekannt"
        return out
    except Exception:
        try:
            from backend.identity_access import directory  # type: ignore

            return {
                sid: (directory.localpart_identifier(sid) or "Unbekannt")  # type: ignore[attr-defined]
                for sid in unique_subs
            }
        except Exception:
            return {sid: "Unbekannt" for sid in unique_subs}


# --- Routes ----------------------------------------------------------------------

async def list_courses(request: Request, limit: int = 10, offset: int = 0):
    """
    List courses for the current user with simple pagination.

    Behavior:
        - Teachers: return owned courses.
        - Students: return courses the student is a member of (empty in MVP unless managed elsewhere).
    """
    user = getattr(request.state, "user", None)
    sub = _current_sub(user)
    limit, offset = _clamp_limit_offset(limit=limit, offset=offset, default_limit=10, max_limit=50)
    repo = _get_repo()
    if _role_in(user, "teacher"):
        items = repo.list_courses_for_teacher(teacher_id=sub, limit=limit, offset=offset)
    else:
        items = repo.list_courses_for_student(student_id=sub, limit=limit, offset=offset)
    return _json_private([_serialize_course(c) for c in items], status_code=200)


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
        return _private_error({"error": "forbidden"}, status_code=403)
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    sub = _current_sub(user)
    try:
        course = _get_repo().create_course(
            title=payload.title.strip(),
            subject=payload.subject,
            grade_level=payload.grade_level,
            term=payload.term,
            teacher_id=sub,
        )
    except ValueError:
        # Map repo validation to contract 400
        return _private_error({"error": "bad_request", "detail": "invalid_input"}, status_code=400)
    # Security: return private, no-store to prevent caching of owner-scoped data
    return _json_private(_serialize_course(course), status_code=201)


async def get_course(request: Request, course_id: str):
    """Get a course by id — owner-only.

    Why:
        UI (edit form, members page) and API clients need a direct lookup that
        respects ownership without scanning lists.

    Behavior:
        - 200 with `Course` when the caller owns the course
        - 404 when the course does not exist
        - 403 when the caller is not the owner

    Permissions:
        Caller must be a teacher AND owner of the course.
    """
    repo = _get_repo()
    user = getattr(request.state, "user", None)
    sub = _current_sub(user)
    if not _role_in(user, "teacher"):
        return _private_error({"error": "forbidden"}, status_code=403)
    # Validate path parameter format early to avoid unintended 500s
    if not _is_uuid_like(course_id):
        return _private_error({"error": "bad_request", "detail": "invalid_course_id"}, status_code=400)
    guard = teaching_guards._guard_course_owner(course_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    # Owner confirmed; fetch course and return
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore
        if isinstance(repo, DBTeachingRepo):
            # Use owner-scoped helper under RLS
            c = repo.get_course_for_owner(course_id, sub)
        else:
            c = repo.get_course(course_id)
    except Exception:
        c = repo.get_course(course_id)
    if not c:
        return _private_error({"error": "not_found"}, status_code=404)
    return _json_private(_serialize_course(c), status_code=200)

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
    unit_type: str | None = Field(default=None)
    title: str | None = Field(default=None)
    summary: str | None = Field(default=None)

    @field_validator("unit_type")
    @classmethod
    def _normalize_unit_type(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if isinstance(v, str):
            stripped = v.strip().lower()
            return stripped or None
        return v

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
    # Accept loose typing to avoid FastAPI 422 and map contract errors to 400
    module_ids: object | None = None


class ModuleSectionVisibilityPayload(BaseModel):
    # Accept loose typing to avoid FastAPI 422 and surface contract error codes.
    visible: object | None = None


# --- Phases (modular Units) ----------------------------------------------------

class UnitPhaseCreatePayload(BaseModel):
    # Accept any length; enforce 1..200 in handler to return 400 (not 422)
    title: str | None = Field(default=None)

    @field_validator("title")
    @classmethod
    def _normalize_title(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            s = v.strip()
            return s or None
        return v


class UnitPhaseUpdatePayload(BaseModel):
    # Accept any length; enforce 1..200 in handler to return 400 (not 422)
    title: str | None = Field(default=None)

    @field_validator("title", mode="before")
    @classmethod
    def _normalize_title(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return None
            return s
        return v


class UnitPhaseReorderPayload(BaseModel):
    # Use loose typing to avoid FastAPI 422, then validate type manually
    phase_ids: object | None = None


# --- Modules (modular Units; Option B) ---------------------------------------

class UnitModuleCreatePayload(BaseModel):
    # Accept raw strings (including empty) and validate in handler to return 400
    title: str | None = Field(default=None)
    phase_id: str | None = Field(default=None)

    @field_validator("title")
    @classmethod
    def _normalize_title(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            s = v.strip()
            return s or None
        return v

    @field_validator("phase_id")
    @classmethod
    def _normalize_phase_id(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            s = v.strip()
            return s or None
        return v


class UnitModuleUpdatePayload(BaseModel):
    # Accept any length; enforce 1..200 in handler to return 400 (not 422)
    title: str | None = Field(default=None)
    # Use loose typing to avoid FastAPI 422, then validate type manually.
    required_prereq_count: object | None = None

    @field_validator("title", mode="before")
    @classmethod
    def _normalize_title(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return None
            return s
        return v


class UnitModuleReorderPayload(BaseModel):
    # Use loose typing to avoid FastAPI 422, then validate type manually
    module_ids: object | None = None


class UnitModuleEdgePayload(BaseModel):
    # Accept raw strings (including empty) and validate in handler to return 400
    from_module_id: str | None = Field(default=None)
    to_module_id: str | None = Field(default=None)

    @field_validator("from_module_id", "to_module_id")
    @classmethod
    def _normalize_ids(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            s = v.strip()
            return s or None
        return v


# --- Sections (per Unit) --------------------------------------------------------

class SectionCreatePayload(BaseModel):
    # Accept any length; enforce 1..200 in handler to return 400 (not 422)
    title: str | None = Field(default=None)

    @field_validator("title")
    @classmethod
    def _normalize_title(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            s = v.strip()
            return s or None
        return v


class SectionUpdatePayload(BaseModel):
    # Accept any length; enforce 1..200 in handler to return 400 (not 422)
    title: str | None = Field(default=None)

    @field_validator("title", mode="before")
    @classmethod
    def _normalize_title(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return None
            return s
        return v


class SectionReorderPayload(BaseModel):
    # Use loose typing to avoid FastAPI 422, then validate type manually
    section_ids: object | None = None


class MaterialCreatePayload(BaseModel):
    title: str | None = Field(default=None)
    body_md: object | None = None

    @field_validator("title")
    @classmethod
    def _normalize_title(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            stripped = v.strip()
            return stripped or None
        return v


class MaterialUploadIntentPayload(BaseModel):
    filename: str = Field(..., min_length=1, max_length=255)
    mime_type: str = Field(..., min_length=1, max_length=128)
    size_bytes: int = Field(..., ge=1)

    @field_validator("filename")
    @classmethod
    def _normalize_filename(cls, value: str) -> str:
        return value.strip()

    @field_validator("mime_type")
    @classmethod
    def _normalize_mime(cls, value: str) -> str:
        return value.strip()


class MaterialFinalizePayload(BaseModel):
    intent_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1, max_length=200)
    # Keep len constraints loose to allow server-side 400 mapping instead of FastAPI 422.
    sha256: str = Field(..., min_length=1, max_length=128)
    # Do not enforce max_length here to avoid FastAPI 422; service maps to 400 invalid_alt_text
    alt_text: str | None = Field(default=None)

    @field_validator("intent_id", "title", "sha256", "alt_text")
    @classmethod
    def _strip_strings(cls, value):
        if value is None:
            return None
        if isinstance(value, str):
            return value.strip()
        return value


class MaterialUpdatePayload(BaseModel):
    title: str | None = Field(default=None)
    body_md: object | None = None
    alt_text: str | None = Field(default=None, max_length=500)

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

    @field_validator("alt_text", mode="before")
    @classmethod
    def _normalize_alt_text(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            stripped = v.strip()
            return stripped or None
        return v


class MaterialReorderPayload(BaseModel):
    material_ids: object | None = None


class TaskCreatePayload(BaseModel):
    instruction_md: object | None = None
    criteria: object | None = None
    teacher_context_md: object | None = None
    due_at: object | None = None
    max_attempts: object | None = None
    h5p: object | None = None
    visual: object | None = None
    scratch: object | None = None
    calliope: object | None = None
    filius: object | None = None


class TaskUpdatePayload(BaseModel):
    instruction_md: object | None = None
    criteria: object | None = None
    teacher_context_md: object | None = None
    due_at: object | None = None
    max_attempts: object | None = None
    h5p: object | None = None
    visual: object | None = None
    scratch: object | None = None
    calliope: object | None = None
    filius: object | None = None


class TaskReorderPayload(BaseModel):
    task_ids: object | None = None


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
    repo = _get_repo()
    user = getattr(request.state, "user", None)
    sub = _current_sub(user)
    if not _role_in(user, "teacher"):
        return _private_error({"error": "forbidden"}, status_code=403)
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    updates = payload.model_dump(mode="python", exclude_unset=True)
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore
        if isinstance(repo, DBTeachingRepo):
            # Contract-aligned semantics: disambiguate 404 vs 403 prior to mutation
            if not repo.course_exists_for_owner(course_id, sub):
                ex = repo.course_exists(course_id)
                if ex is False:
                    return _private_error({"error": "not_found"}, status_code=404)
                return _private_error({"error": "forbidden"}, status_code=403)
            updated = repo.update_course_owned(
                course_id,
                sub,
                **updates,
            )
        else:
            course = repo.get_course(course_id)
            if not course:
                return _private_error({"error": "not_found"}, status_code=404)
            owner_id = course["teacher_id"] if isinstance(course, dict) else getattr(course, "teacher_id", None)
            if sub != owner_id:
                return _private_error({"error": "forbidden"}, status_code=403)
            updated = repo.update_course(
                course_id,
                **updates,
            )
    except ValueError:
        return _private_error({"error": "bad_request", "detail": "invalid_field"}, status_code=400)
    if not updated:
        # Should not normally happen after existence/ownership checks; keep conservative 403
        return _private_error({"error": "forbidden"}, status_code=403)
    return _json_private(_serialize_course(updated), status_code=200, vary_origin=True)


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
    repo = _get_repo()
    user = getattr(request.state, "user", None)
    sub = _current_sub(user)
    if not _role_in(user, "teacher"):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    # CSRF defense-in-depth for browser clients
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore
        if isinstance(repo, DBTeachingRepo):
            # Owner check with ability to disambiguate 404 vs 403
            if not repo.course_exists_for_owner(course_id, sub):
                ex = repo.course_exists(course_id)
                if ex is False:
                    return JSONResponse({"error": "not_found"}, status_code=404)
                return JSONResponse({"error": "forbidden"}, status_code=403)
            repo.delete_course_owned(course_id, sub)
            _mark_recently_deleted(sub, course_id)
            return Response(status_code=204, headers={"Cache-Control": "private, no-store"})
        else:
            course = repo.get_course(course_id)
            if not course:
                return JSONResponse({"error": "not_found"}, status_code=404)
            owner_id = course["teacher_id"] if isinstance(course, dict) else getattr(course, "teacher_id", None)
            if sub != owner_id:
                return JSONResponse({"error": "forbidden"}, status_code=403)
            repo.delete_course(course_id)
            _mark_recently_deleted(sub, course_id)
            return Response(status_code=204, headers={"Cache-Control": "private, no-store"})
    except Exception:
        # Conservative default: do not claim deletion if ownership/existence cannot be determined
        return JSONResponse({"error": "forbidden"}, status_code=403)

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
    limit, offset = _clamp_limit_offset(limit=limit, offset=offset, default_limit=20, max_limit=50)
    sub = _current_sub(user)
    try:
        units = _get_repo().list_units_for_author(author_id=sub, limit=limit, offset=offset)
    except Exception as exc:
        logger.warning("list_units failed for sub=%s err=%s", sub[-6:], exc.__class__.__name__)
        return _private_error({"error": "forbidden"}, status_code=403)
    return _json_private([_serialize_unit(u) for u in units], status_code=200)


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
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    sub = _current_sub(user)
    repo = _get_repo()
    unit_type = str(payload.unit_type or "").strip().lower()
    if unit_type == "modular":
        repo_error = _require_modular_repo_methods(repo, *_MODULAR_UNIT_CREATE_REQUIRED_METHODS)
        if repo_error:
            return repo_error
    try:
        title = payload.title or ""
        unit = repo.create_unit(title=title, summary=payload.summary, author_id=sub, unit_type=payload.unit_type)
    except ValueError as exc:
        detail = str(exc)
        if detail in {"invalid_title", "invalid_summary", "invalid_unit_type"}:
            return _private_error({"error": "bad_request", "detail": detail}, status_code=400)
        return _private_error({"error": "bad_request"}, status_code=400)
    except PermissionError:
        return _private_error({"error": "forbidden"}, status_code=403)
    return _json_private(_serialize_unit(unit), status_code=201)


async def get_unit(request: Request, unit_id: str):
    """
    Get a learning unit by id — author only.

    Why:
        The SSR edit form and API clients need a direct lookup to prefill
        fields without scanning a paginated list.

    Behavior:
        - 200 with `Unit` when the caller authored the unit
        - 400 when `unit_id` is not UUID-like
        - 404 when the unit does not exist
        - 403 when the caller is not the author

    Permissions:
        Caller must be a teacher and the author of the unit.
    """
    repo = _get_repo()
    user, error = _require_teacher(request)
    if error:
        return error
    if not _is_uuid_like(unit_id):
        return _private_error({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    # Author confirmed; fetch the unit via repo (DB or in-memory)
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore
        if isinstance(repo, DBTeachingRepo):
            u = repo.get_unit_for_author(unit_id, sub)
        else:
            u = repo.get_unit_for_author(unit_id, sub)
    except Exception:
        u = repo.get_unit_for_author(unit_id, sub)
    if not u:
        return _private_error({"error": "not_found"}, status_code=404)
    return _json_private(_serialize_unit(u), status_code=200)


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
    repo = _get_repo()
    user, error = _require_teacher(request)
    if error:
        return error
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    updates = payload.model_dump(mode="python", exclude_unset=True)
    if not updates:
        return JSONResponse({"error": "bad_request", "detail": "empty_payload"}, status_code=400)
    try:
        updated = repo.update_unit_owned(unit_id, sub, **updates)
    except ValueError as exc:
        detail = str(exc)
        return JSONResponse({"error": "bad_request", "detail": detail}, status_code=400)
    if not updated:
        return JSONResponse({"error": "not_found"}, status_code=404)
    return _json_private(_serialize_unit(updated), status_code=200)


async def delete_unit(request: Request, unit_id: str):
    """
    Delete a unit owned by the current teacher.

    Behavior:
        - 204 on success, cascading removal of associated modules.
        - 502 when a storage object could not be deleted.
        - 503 when storage metadata or adapter access is unavailable.
        - 403 when caller is not the author.
        - 404 when the unit does not exist.

    Permissions:
        Caller must be a teacher and the author of the unit.
    """
    repo = _get_repo()
    user, error = _require_teacher(request)
    if error:
        return error
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    try:
        storage_objects = _collect_unit_delete_storage_objects(repo, unit_id=unit_id)
        _delete_unit_storage_objects(storage_objects)
        deleted = repo.delete_unit_owned(unit_id, sub)
    except RuntimeError as exc:
        detail = str(exc) or "storage_delete_failed"
        if detail in {"storage_adapter_not_configured", "storage_metadata_unavailable"}:
            return JSONResponse(
                {"error": "service_unavailable", "detail": "storage_adapter_unavailable"},
                status_code=503,
            )
        return JSONResponse(
            {"error": "bad_gateway", "detail": "storage_delete_failed"},
            status_code=502,
        )
    except Exception:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    if not deleted:
        return JSONResponse({"error": "not_found"}, status_code=404)
    # No content but still enforce private, no-store to be explicit in proxies
    return Response(status_code=204, headers={"Cache-Control": "private, no-store"})




async def list_unit_phases(request: Request, unit_id: str):
    """List phases of a modular unit (author only)."""
    repo = _get_repo()
    user, error = _require_teacher(request)
    if error:
        return error
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    repo_error = _require_modular_repo_methods(repo, "list_unit_phases_for_author")
    if repo_error:
        return repo_error
    try:
        items = repo.list_unit_phases_for_author(unit_id, sub)
    except ValueError as exc:
        detail = str(exc) or "bad_request"
        if detail == "invalid_unit_type":
            return _private_error({"error": "bad_request", "detail": "invalid_unit_type"}, status_code=400)
        return _private_error({"error": "bad_request", "detail": detail}, status_code=400)
    except PermissionError:
        return _private_error({"error": "forbidden"}, status_code=403)
    except Exception:
        raise
    return _json_private([_serialize_unit_phase_public(p) for p in items], status_code=200)


async def create_unit_phase(request: Request, unit_id: str, payload: UnitPhaseCreatePayload):
    """Create a phase in a modular unit (author only); appends at the next position."""
    repo = _get_repo()
    user, error = _require_teacher(request)
    if error:
        return error
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    repo_error = _require_modular_repo_methods(repo, "create_unit_phase")
    if repo_error:
        return repo_error
    title = payload.title or ""
    try:
        phase = repo.create_unit_phase(unit_id, title, sub)
    except ValueError as exc:
        detail = str(exc) or "invalid_input"
        if detail in {"invalid_unit_type", "invalid_title"}:
            return _private_error({"error": "bad_request", "detail": detail}, status_code=400)
        return _private_error({"error": "bad_request", "detail": "invalid_input"}, status_code=400)
    except PermissionError:
        return _private_error({"error": "forbidden"}, status_code=403)
    return _json_private(_serialize_unit_phase_public(phase), status_code=201, vary_origin=True)


async def update_unit_phase(
    request: Request,
    unit_id: str,
    phase_id: str,
    payload: UnitPhaseUpdatePayload,
):
    """Rename a phase in a modular unit (author only)."""
    repo = _get_repo()
    user, error = _require_teacher(request)
    if error:
        return error
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    if not _is_uuid_like(unit_id) or not _is_uuid_like(phase_id):
        return _private_error({"error": "bad_request", "detail": "invalid_path_params"}, status_code=400)
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    repo_error = _require_modular_repo_methods(repo, "update_unit_phase_title")
    if repo_error:
        return repo_error
    updates = payload.model_dump(mode="python", exclude_unset=True)
    if not updates:
        return _private_error({"error": "bad_request", "detail": "empty_payload"}, status_code=400)
    try:
        updated = repo.update_unit_phase_title(unit_id, phase_id, updates.get("title"), sub)
    except ValueError as exc:
        detail = str(exc) or "invalid_input"
        if detail in {"invalid_unit_type", "invalid_title"}:
            return _private_error({"error": "bad_request", "detail": detail}, status_code=400)
        return _private_error({"error": "bad_request", "detail": "invalid_input"}, status_code=400)
    except PermissionError:
        return _private_error({"error": "forbidden"}, status_code=403)
    if not updated:
        return _private_error({"error": "not_found"}, status_code=404)
    return _json_private(_serialize_unit_phase_public(updated), status_code=200, vary_origin=True)


async def delete_unit_phase(request: Request, unit_id: str, phase_id: str):
    """Delete a phase (and all modules/edges/content inside it) (author only)."""
    repo = _get_repo()
    user, error = _require_teacher(request)
    if error:
        return error
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    if not _is_uuid_like(unit_id):
        return _private_error({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    if not _is_uuid_like(phase_id):
        return _private_error({"error": "bad_request", "detail": "invalid_phase_id"}, status_code=400)
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    repo_error = _require_modular_repo_methods(repo, "delete_unit_phase_for_author")
    if repo_error:
        return repo_error
    try:
        deleted = repo.delete_unit_phase_for_author(unit_id=unit_id, phase_id=phase_id, author_id=sub)
    except ValueError as exc:
        detail = str(exc) or "bad_request"
        if detail == "invalid_unit_type":
            return _private_error({"error": "bad_request", "detail": "invalid_unit_type"}, status_code=400)
        return _private_error({"error": "bad_request", "detail": detail}, status_code=400)
    except PermissionError:
        return _private_error({"error": "forbidden"}, status_code=403)
    if not deleted:
        return _private_error({"error": "not_found"}, status_code=404)
    return Response(status_code=204, headers={"Cache-Control": "private, no-store"})


async def reorder_unit_phases(request: Request, unit_id: str, payload: UnitPhaseReorderPayload):
    """Reorder phases (author only) transactionally to positions 1..n as provided."""
    repo = _get_repo()
    user, error = _require_teacher(request)
    if error:
        return error
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    if not _is_uuid_like(unit_id):
        return _private_error({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    sub = _current_sub(user)
    # Security-first: verify authorship before deep payload validation to avoid error oracle
    guard = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    repo_error = _require_modular_repo_methods(repo, "reorder_unit_phases_owned")
    if repo_error:
        return repo_error
    ids, ids_error = _validate_uuid_id_list(
        payload.phase_ids,
        array_detail="phase_ids_must_be_array",
        empty_detail="empty_phase_ids",
        duplicate_detail="duplicate_phase_ids",
        invalid_detail="invalid_phase_ids",
    )
    if ids_error:
        return ids_error
    try:
        ordered = repo.reorder_unit_phases_owned(unit_id, sub, ids)
    except ValueError as exc:
        detail = str(exc) or "bad_request"
        return _private_error({"error": "bad_request", "detail": detail}, status_code=400)
    except LookupError:
        return _private_error({"error": "not_found"}, status_code=404)
    except PermissionError:
        return _private_error({"error": "forbidden"}, status_code=403)
    except Exception as exc:
        sqlstate = getattr(exc, "sqlstate", None) or getattr(exc, "pgcode", None)
        if sqlstate == "23514":  # check_violation
            return _private_error(
                {"error": "bad_request", "detail": "edge_constraint_violation"},
                status_code=400,
            )
        raise
    return _json_private([_serialize_unit_phase_public(p) for p in ordered], status_code=200, vary_origin=True)


async def get_unit_modules_graph(request: Request, unit_id: str):
    """Return the authoring graph payload for a modular unit (author only)."""
    repo = _get_repo()
    user, error = _require_teacher(request)
    if error:
        return error
    if not _is_uuid_like(unit_id):
        return _private_error({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    repo_error = _require_modular_repo_methods(
        repo,
        "list_unit_phases_for_author",
        "list_unit_modules_for_author",
        "list_unit_module_edges_for_author",
    )
    if repo_error:
        return repo_error
    try:
        phases = repo.list_unit_phases_for_author(unit_id, sub)
        modules = repo.list_unit_modules_for_author(unit_id=unit_id, author_id=sub)
        edges = repo.list_unit_module_edges_for_author(unit_id=unit_id, author_id=sub)
    except ValueError as exc:
        detail = str(exc) or "bad_request"
        if detail == "invalid_unit_type":
            return _private_error({"error": "bad_request", "detail": "invalid_unit_type"}, status_code=400)
        return _private_error({"error": "bad_request", "detail": detail}, status_code=400)
    except LookupError:
        return _private_error({"error": "not_found"}, status_code=404)
    except PermissionError:
        return _private_error({"error": "forbidden"}, status_code=403)

    payload = {
        "unit_id": unit_id,
        "phases": [_serialize_unit_phase_public(p) for p in phases],
        "modules": [_serialize_unit_module(m) for m in modules],
        "edges": [_serialize_unit_graph_edge(e) for e in edges],
    }
    return _json_private(payload, status_code=200)


async def get_unit_module_content_target(request: Request, unit_id: str, module_id: str):
    """Return the backing section id for a modular unit module."""
    repo = _get_repo()
    user, error = _require_teacher(request)
    if error:
        return error
    if not _is_uuid_like(unit_id):
        return _private_error({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    if not _is_uuid_like(module_id):
        return _private_error({"error": "bad_request", "detail": "invalid_module_id"}, status_code=400)
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    if not hasattr(repo, "get_unit_module_for_author"):
        return _private_error({"error": "service_unavailable", "detail": "modular_repo_unavailable"}, status_code=503)
    try:
        section_id = _get_unit_module_section_id_for_author(repo, unit_id=unit_id, module_id=module_id, author_id=sub)
    except LookupError:
        return _private_error({"error": "not_found"}, status_code=404)
    except PermissionError:
        return _private_error({"error": "forbidden"}, status_code=403)
    if not section_id:
        return _private_error({"error": "not_found"}, status_code=404)
    return _json_private({"module_id": str(module_id), "section_id": str(section_id)}, status_code=200)


async def create_unit_module(request: Request, unit_id: str, payload: UnitModuleCreatePayload):
    """Create a module (graph node) inside a phase (author only)."""
    repo = _get_repo()
    user, error = _require_teacher(request)
    if error:
        return error
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    if not _is_uuid_like(unit_id):
        return _private_error({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    repo_error = _require_modular_repo_methods(repo, "create_unit_module_for_author")
    if repo_error:
        return repo_error
    title = payload.title or ""
    phase_id = payload.phase_id or ""
    if not _is_uuid_like(phase_id):
        return _private_error({"error": "bad_request", "detail": "invalid_phase_id"}, status_code=400)
    if not title or len(title) > 200:
        return _private_error({"error": "bad_request", "detail": "invalid_title"}, status_code=400)
    try:
        created = repo.create_unit_module_for_author(unit_id=unit_id, phase_id=phase_id, title=title, author_id=sub)
    except ValueError as exc:
        detail = str(exc) or "invalid_input"
        if detail in {"invalid_unit_type", "invalid_title"}:
            return _private_error({"error": "bad_request", "detail": detail}, status_code=400)
        return _private_error({"error": "bad_request", "detail": "invalid_input"}, status_code=400)
    except LookupError:
        return _private_error({"error": "not_found"}, status_code=404)
    except PermissionError:
        return _private_error({"error": "forbidden"}, status_code=403)
    return _json_private(_serialize_unit_module(created), status_code=201, vary_origin=True)


async def create_unit_module_edge(request: Request, unit_id: str, payload: UnitModuleEdgePayload):
    """Create a directed dependency edge within a modular unit (author only)."""
    repo = _get_repo()
    user, error = _require_teacher(request)
    if error:
        return error
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    if not _is_uuid_like(unit_id):
        return _private_error({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    repo_error = _require_modular_repo_methods(
        repo,
        "list_unit_modules_for_author",
        "create_unit_module_edge_for_author",
    )
    if repo_error:
        return repo_error

    from_id = payload.from_module_id or ""
    to_id = payload.to_module_id or ""
    if not _is_uuid_like(from_id) or not _is_uuid_like(to_id):
        return _private_error({"error": "bad_request", "detail": "invalid_module_ids"}, status_code=400)
    from_id = _canonical_uuid(from_id)
    to_id = _canonical_uuid(to_id)
    try:
        modules = _list_unit_modules_for_author_compat(repo, unit_id=unit_id, author_id=sub)
    except ValueError as exc:
        detail = str(exc) or "bad_request"
        if detail == "invalid_unit_type":
            return _private_error({"error": "bad_request", "detail": "invalid_unit_type"}, status_code=400)
        return _private_error({"error": "bad_request", "detail": detail}, status_code=400)
    except PermissionError:
        return _private_error({"error": "forbidden"}, status_code=403)
    except LookupError:
        return _private_error({"error": "not_found"}, status_code=404)
    module_ids: set[str] = set()
    for item in (modules or []):
        raw_id = str((item or {}).get("id")) if isinstance(item, dict) else str(getattr(item, "id", ""))
        if _is_uuid_like(raw_id):
            module_ids.add(_canonical_uuid(raw_id))
    if from_id not in module_ids or to_id not in module_ids:
        return _private_error({"error": "not_found"}, status_code=404)
    try:
        created = repo.create_unit_module_edge_for_author(
            unit_id=unit_id, from_module_id=from_id, to_module_id=to_id, author_id=sub
        )
    except ValueError as exc:
        detail = str(exc) or "bad_request"
        if detail == "invalid_unit_type":
            return _private_error({"error": "bad_request", "detail": "invalid_unit_type"}, status_code=400)
        return _private_error({"error": "bad_request", "detail": detail}, status_code=400)
    except PermissionError:
        return _private_error({"error": "forbidden"}, status_code=403)
    except Exception as exc:
        sqlstate = getattr(exc, "sqlstate", None) or getattr(exc, "pgcode", None)
        if sqlstate == "23514":  # check_violation
            return _private_error({"error": "bad_request", "detail": "edge_constraint_violation"}, status_code=400)
        if sqlstate == "23503":  # foreign_key_violation
            return _private_error({"error": "not_found"}, status_code=404)
        if sqlstate == "23505":  # unique_violation
            return _private_error({"error": "conflict", "detail": "duplicate_edge"}, status_code=409)
        raise
    return _json_private(_serialize_unit_graph_edge(created), status_code=201, vary_origin=True)


def _delete_unit_module_edge_common(*, request: Request, unit_id: str, from_id: str, to_id: str):
    """Delete a directed dependency edge within a modular unit (author only)."""
    repo = _get_repo()
    user, error = _require_teacher(request)
    if error:
        return error
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    if not _is_uuid_like(unit_id):
        return _private_error({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    repo_error = _require_modular_repo_methods(repo, "delete_unit_module_edge_for_author")
    if repo_error:
        return repo_error

    if not _is_uuid_like(from_id) or not _is_uuid_like(to_id):
        return _private_error({"error": "bad_request", "detail": "invalid_module_ids"}, status_code=400)
    try:
        deleted = repo.delete_unit_module_edge_for_author(
            unit_id=unit_id,
            from_module_id=from_id,
            to_module_id=to_id,
            author_id=sub,
        )
    except ValueError:
        return _private_error({"error": "bad_request", "detail": "invalid_unit_type"}, status_code=400)
    except PermissionError:
        return _private_error({"error": "forbidden"}, status_code=403)
    if not deleted:
        return _private_error({"error": "not_found"}, status_code=404)
    return Response(status_code=204, headers={"Cache-Control": "private, no-store"})


_LEGACY_EDGE_DELETE_SUNSET_HTTP = "Tue, 30 Jun 2026 23:59:59 GMT"
_LEGACY_EDGE_DELETE_SUCCESSOR_LINK_TEMPLATE = (
    '</api/teaching/units/{unit_id}/modules/{from_module_id}/edges/{to_module_id}>; rel="successor-version"'
)


def _legacy_edge_delete_successor_link(*, unit_id: str, from_module_id: str, to_module_id: str) -> str:
    """Build the successor Link header for the path-based delete endpoint."""
    if not (_is_uuid_like(unit_id) and _is_uuid_like(from_module_id) and _is_uuid_like(to_module_id)):
        return _LEGACY_EDGE_DELETE_SUCCESSOR_LINK_TEMPLATE
    return (
        f'</api/teaching/units/{_canonical_uuid(unit_id)}/modules/'
        f'{_canonical_uuid(from_module_id)}/edges/{_canonical_uuid(to_module_id)}>; rel="successor-version"'
    )


async def delete_unit_module_edge(request: Request, unit_id: str, payload: UnitModuleEdgePayload):
    """Delete a dependency edge using request-body module ids (author only).

    Note:
        Kept for backward compatibility. New clients should prefer the path-based
        delete endpoint to avoid intermediaries that ignore DELETE request bodies.
    """
    response = _delete_unit_module_edge_common(
        request=request,
        unit_id=unit_id,
        from_id=str(payload.from_module_id or ""),
        to_id=str(payload.to_module_id or ""),
    )
    if int(getattr(response, "status_code", 0)) == 204:
        response.headers.setdefault("Deprecation", "true")
        response.headers.setdefault("Sunset", _LEGACY_EDGE_DELETE_SUNSET_HTTP)
        response.headers.setdefault(
            "Link",
            _legacy_edge_delete_successor_link(
                unit_id=unit_id,
                from_module_id=str(payload.from_module_id or ""),
                to_module_id=str(payload.to_module_id or ""),
            ),
        )
    return response


async def delete_unit_module_edge_by_path(
    request: Request,
    unit_id: str,
    from_module_id: str,
    to_module_id: str,
):
    """Delete a dependency edge using path params (author only)."""
    return _delete_unit_module_edge_common(
        request=request,
        unit_id=unit_id,
        from_id=str(from_module_id or ""),
        to_id=str(to_module_id or ""),
    )


async def update_unit_module(
    request: Request,
    unit_id: str,
    module_id: str,
    payload: UnitModuleUpdatePayload,
):
    """Update module settings (author only)."""
    repo = _get_repo()
    user, error = _require_teacher(request)
    if error:
        return error
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    if not _is_uuid_like(unit_id):
        return _private_error({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    if not _is_uuid_like(module_id):
        return _private_error({"error": "bad_request", "detail": "invalid_module_id"}, status_code=400)
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    repo_error = _require_modular_repo_methods(repo, "update_unit_module_owned")
    if repo_error:
        return repo_error
    title_provided = "title" in payload.model_fields_set
    k_provided = "required_prereq_count" in payload.model_fields_set
    if not (title_provided or k_provided):
        return _private_error({"error": "bad_request", "detail": "empty_payload"}, status_code=400)

    title = payload.title if title_provided else _UNSET
    if title is not _UNSET and (title is None or (not str(title).strip()) or len(str(title).strip()) > 200):
        return _private_error({"error": "bad_request", "detail": "invalid_title"}, status_code=400)

    k = payload.required_prereq_count if k_provided else _UNSET
    if k is not _UNSET:
        if k is None or isinstance(k, bool) or (not isinstance(k, int)) or int(k) < 0:
            return _private_error(
                {"error": "bad_request", "detail": "invalid_required_prereq_count"},
                status_code=400,
            )
    try:
        update_kwargs: dict[str, object] = {}
        if title_provided:
            update_kwargs["title"] = title
        if k_provided:
            update_kwargs["required_prereq_count"] = k
        updated = repo.update_unit_module_owned(
            unit_id=unit_id,
            module_id=module_id,
            author_id=sub,
            **update_kwargs,
        )
    except ValueError as exc:
        detail = str(exc) or "invalid_input"
        if detail in {"invalid_unit_type", "invalid_title", "invalid_required_prereq_count"}:
            return _private_error({"error": "bad_request", "detail": detail}, status_code=400)
        return _private_error({"error": "bad_request", "detail": "invalid_input"}, status_code=400)
    except PermissionError:
        return _private_error({"error": "forbidden"}, status_code=403)
    if not updated:
        return _private_error({"error": "not_found"}, status_code=404)
    return _json_private(_serialize_unit_module(updated), status_code=200, vary_origin=True)


async def delete_unit_module(request: Request, unit_id: str, module_id: str):
    """Delete a module and its backing content (author only)."""
    repo = _get_repo()
    user, error = _require_teacher(request)
    if error:
        return error
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    if not _is_uuid_like(unit_id):
        return _private_error({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    if not _is_uuid_like(module_id):
        return _private_error({"error": "bad_request", "detail": "invalid_module_id"}, status_code=400)
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    repo_error = _require_modular_repo_methods(repo, "delete_unit_module_for_author")
    if repo_error:
        return repo_error
    try:
        deleted = repo.delete_unit_module_for_author(unit_id=unit_id, module_id=module_id, author_id=sub)
    except ValueError as exc:
        detail = str(exc) or "bad_request"
        if detail == "invalid_unit_type":
            return _private_error({"error": "bad_request", "detail": "invalid_unit_type"}, status_code=400)
        return _private_error({"error": "bad_request", "detail": detail}, status_code=400)
    except PermissionError:
        return _private_error({"error": "forbidden"}, status_code=403)
    if not deleted:
        return _private_error({"error": "not_found"}, status_code=404)
    return Response(status_code=204, headers={"Cache-Control": "private, no-store"})


async def reorder_unit_phase_modules(request: Request, unit_id: str, phase_id: str, payload: UnitModuleReorderPayload):
    """Reorder (and move) modules for a phase (author only)."""
    repo = _get_repo()
    user, error = _require_teacher(request)
    if error:
        return error
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    if not _is_uuid_like(unit_id):
        return _private_error({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    if not _is_uuid_like(phase_id):
        return _private_error({"error": "bad_request", "detail": "invalid_phase_id"}, status_code=400)
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    repo_error = _require_modular_repo_methods(repo, "reorder_unit_phase_modules_owned")
    if repo_error:
        return repo_error

    ids, ids_error = _validate_uuid_id_list(
        payload.module_ids,
        array_detail="module_ids_must_be_array",
        empty_detail="empty_module_ids",
        duplicate_detail="duplicate_module_ids",
        invalid_detail="invalid_module_ids",
    )
    if ids_error:
        return ids_error

    try:
        ordered = repo.reorder_unit_phase_modules_owned(unit_id=unit_id, phase_id=phase_id, author_id=sub, module_ids=ids)
    except ValueError as exc:
        detail = str(exc) or "bad_request"
        if detail == "invalid_unit_type":
            return _private_error({"error": "bad_request", "detail": "invalid_unit_type"}, status_code=400)
        return _private_error({"error": "bad_request", "detail": detail}, status_code=400)
    except LookupError as exc:
        detail = str(exc) or ""
        if detail in {"module_not_in_unit", "phase_not_found"}:
            return _private_error({"error": "not_found"}, status_code=404)
        return _private_error({"error": "bad_request", "detail": "invalid_module_ids"}, status_code=400)
    except PermissionError:
        return _private_error({"error": "forbidden"}, status_code=403)
    except Exception as exc:
        sqlstate = getattr(exc, "sqlstate", None) or getattr(exc, "pgcode", None)
        if sqlstate == "23514":  # check_violation
            return _private_error(
                {"error": "bad_request", "detail": "edge_constraint_violation"},
                status_code=400,
            )
        raise

    return _json_private([_serialize_unit_module(m) for m in ordered], status_code=200, vary_origin=True)


async def list_sections(request: Request, unit_id: str):
    """List sections of a learning unit (author only).

    Why:
        UI needs the ordered section list for authoring and release workflows.

    Behavior:
        - 200 with sections sorted by ascending position when unit is owned by caller.
        - 400 when `unit_id` is not a UUID.
        - 403 when caller lacks teacher role or is not the author (may be 404).
        - 404 when the unit does not exist.
    """
    user, error = _require_teacher(request)
    if error:
        # Unauthenticated/role → 403 (middleware may map unauth to 401 earlier)
        return error
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    try:
        items = _get_repo().list_sections_for_author(unit_id, sub)
    except Exception:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    return _json_private([_serialize_section(s) for s in items], status_code=200)


async def create_section(request: Request, unit_id: str, payload: SectionCreatePayload):
    """Create a section in a unit (author only); appends at the next position.

    Why:
        Authors add new content blocks to a unit; default append keeps mental
        model simple. Reordering is available separately.

    Behavior:
        - 201 with created section.
        - 400 on invalid input (missing/empty/too long title or bad UUID).
        - 403 when caller is not the author (may be 404).
        - 404 when the unit does not exist.
    """
    user, error = _require_teacher(request)
    if error:
        return error
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    title = payload.title or ""
    try:
        sec = _get_repo().create_section(unit_id, title, sub)
    except ValueError:
        return JSONResponse({"error": "bad_request", "detail": "invalid_title"}, status_code=400)
    except PermissionError:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    return JSONResponse(content=_serialize_section(sec), status_code=201)


async def update_section(request: Request, unit_id: str, section_id: str, payload: SectionUpdatePayload):
    """Update a section (author only). Only `title` is updatable in this slice.

    Why:
        Allow small edits without affecting order; more fields can be added later
        without breaking the contract.

    Behavior:
        - 200 with updated section.
        - 400 when payload is empty or identifiers invalid.
        - 403/404 on ownership/unknown semantics based on unit guard and visibility.
    """
    repo = _get_repo()
    user, error = _require_teacher(request)
    if error:
        return error
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    if not _is_uuid_like(unit_id) or not _is_uuid_like(section_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_path_params"}, status_code=400)
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    updates = payload.model_dump(mode="python", exclude_unset=True)
    if not updates:
        return JSONResponse({"error": "bad_request", "detail": "empty_payload"}, status_code=400)
    try:
        updated = repo.update_section_title(unit_id, section_id, updates.get("title"), sub)
    except ValueError:
        return JSONResponse({"error": "bad_request", "detail": "invalid_title"}, status_code=400)
    if not updated:
        return JSONResponse({"error": "not_found"}, status_code=404)
    return JSONResponse(content=_serialize_section(updated), status_code=200)


async def delete_section(request: Request, unit_id: str, section_id: str):
    """Delete a section in a unit (author only); resequences remaining positions.

    Why:
        Keep positions contiguous (1..n) for a predictable UI and simpler bulk
        operations later (e.g., release toggles).

    Behavior:
        - 204 on success.
        - 400 when identifiers are invalid UUIDs.
        - 403/404 based on ownership and existence.
    """
    repo = _get_repo()
    user, error = _require_teacher(request)
    if error:
        return error
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    if not _is_uuid_like(unit_id) or not _is_uuid_like(section_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_path_params"}, status_code=400)
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    deleted = repo.delete_section(unit_id, section_id, sub)
    if not deleted:
        return JSONResponse({"error": "not_found"}, status_code=404)
    return Response(status_code=204, headers={"Cache-Control": "private, no-store"})


async def reorder_sections(request: Request, unit_id: str, payload: SectionReorderPayload):
    """Reorder sections (author only) transactionally to positions 1..n as provided.

    Why:
        Authoring needs precise control of order; transactional update prevents
        duplicates/gaps under concurrency.

    Behavior:
        - 200 on success with updated ordered list.
        - 400 on invalid payload (empty, non-array, duplicates, invalid UUIDs, mismatch).
        - 403/404 based on ownership and existence semantics.
    """
    repo = _get_repo()
    user, error = _require_teacher(request)
    if error:
        return error
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    if not _is_uuid_like(unit_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    sub = _current_sub(user)
    # Security-first: verify authorship before deep payload validation to avoid error oracle
    guard = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    ids = payload.section_ids
    if not isinstance(ids, list):
        return JSONResponse({"error": "bad_request", "detail": "section_ids_must_be_array"}, status_code=400)
    if len(ids) == 0:
        return JSONResponse({"error": "bad_request", "detail": "empty_section_ids"}, status_code=400)
    if len(ids) != len(set(ids)):
        return JSONResponse({"error": "bad_request", "detail": "duplicate_section_ids"}, status_code=400)
    if any(not _is_uuid_like(sid) for sid in ids):
        return JSONResponse({"error": "bad_request", "detail": "invalid_section_ids"}, status_code=400)
    try:
        ordered = repo.reorder_unit_sections_owned(unit_id, sub, ids)
    except ValueError as exc:
        return JSONResponse({"error": "bad_request", "detail": str(exc)}, status_code=400)
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404)
    except PermissionError:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    # Uniform API shape: explicit JSONResponse with status 200
    return JSONResponse(content=[_serialize_section(s) for s in ordered], status_code=200)


async def list_section_tasks(request: Request, unit_id: str, section_id: str):
    """List tasks of a section for the authoring teacher.

    Cache policy: private, no-store (teacher-scoped data must not be cached).
    """

    user, error = _require_teacher(request)
    if error:
        return error
    if not _is_uuid_like(unit_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    if not _is_uuid_like(section_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_section_id"}, status_code=400)
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    try:
        items = _get_tasks_service().list_tasks(unit_id, section_id, sub)
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404)
    return _json_private([_serialize_task(t) for t in items], status_code=200)


async def create_section_task(request: Request, unit_id: str, section_id: str, payload: TaskCreatePayload):
    """Create a task within a section (author only)."""

    user, error = _require_teacher(request)
    if error:
        return error
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    if not _is_uuid_like(unit_id):
        return _private_error({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    if not _is_uuid_like(section_id):
        return _private_error({"error": "bad_request", "detail": "invalid_section_id"}, status_code=400)
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    try:
        task = _get_tasks_service().create_task(
            unit_id,
            section_id,
            sub,
            instruction_md=payload.instruction_md,
            criteria=payload.criteria,
            teacher_context_md=payload.teacher_context_md,
            due_at=payload.due_at,
            max_attempts=payload.max_attempts,
            h5p=payload.h5p,
            visual=payload.visual,
            scratch=payload.scratch,
            calliope=payload.calliope,
            filius=payload.filius,
        )
    except LookupError:
        return _private_error({"error": "not_found"}, status_code=404)
    except ValueError as exc:
        detail = str(exc) or "invalid_input"
        if detail not in {
            "invalid_instruction_md",
            "invalid_criteria",
            "invalid_due_at",
            "invalid_max_attempts",
            "invalid_teacher_context_md",
            "invalid_h5p_config",
            "invalid_visual_config",
            "invalid_scratch_config",
            "invalid_calliope_config",
            "invalid_filius_config",
            "invalid_task_kind_config",
        }:
            detail = "invalid_input"
        return _private_error({"error": "bad_request", "detail": detail}, status_code=400)
    except PermissionError:
        return _private_error({"error": "forbidden"}, status_code=403)
    return _json_private(_serialize_task(task), status_code=201)


async def update_section_task(
    request: Request,
    unit_id: str,
    section_id: str,
    task_id: str,
    payload: TaskUpdatePayload,
):
    """Update task fields for an author's section."""

    user, error = _require_teacher(request)
    if error:
        return error
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    if not _is_uuid_like(unit_id):
        return _private_error({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    if not _is_uuid_like(section_id):
        return _private_error({"error": "bad_request", "detail": "invalid_section_id"}, status_code=400)
    if not _is_uuid_like(task_id):
        return _private_error({"error": "bad_request", "detail": "invalid_task_id"}, status_code=400)
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    raw_updates = payload.model_dump(mode="python", exclude_unset=True)
    if not raw_updates:
        return _private_error({"error": "bad_request", "detail": "empty_payload"}, status_code=400)
    kwargs: Dict[str, object] = {}
    if "instruction_md" in raw_updates:
        kwargs["instruction_md"] = raw_updates["instruction_md"]
    if "criteria" in raw_updates:
        kwargs["criteria"] = raw_updates["criteria"]
    if "teacher_context_md" in raw_updates:
        kwargs["teacher_context_md"] = raw_updates["teacher_context_md"]
    if "due_at" in raw_updates:
        kwargs["due_at"] = raw_updates["due_at"]
    if "max_attempts" in raw_updates:
        kwargs["max_attempts"] = raw_updates["max_attempts"]
    if "h5p" in raw_updates:
        kwargs["h5p"] = raw_updates["h5p"]
    if "visual" in raw_updates:
        kwargs["visual"] = raw_updates["visual"]
    if "scratch" in raw_updates:
        kwargs["scratch"] = raw_updates["scratch"]
    if "calliope" in raw_updates:
        kwargs["calliope"] = raw_updates["calliope"]
    if "filius" in raw_updates:
        kwargs["filius"] = raw_updates["filius"]
    try:
        updated = _get_tasks_service().update_task(
            unit_id,
            section_id,
            task_id,
            sub,
            **kwargs,
        )
    except ValueError as exc:
        detail = str(exc) or "invalid_input"
        if detail not in {
            "invalid_instruction_md",
            "invalid_criteria",
            "invalid_due_at",
            "invalid_max_attempts",
            "invalid_teacher_context_md",
            "invalid_h5p_config",
            "invalid_visual_config",
            "invalid_scratch_config",
            "invalid_calliope_config",
            "invalid_filius_config",
            "invalid_task_kind_config",
        }:
            detail = "invalid_input"
        return _private_error({"error": "bad_request", "detail": detail}, status_code=400)
    except LookupError:
        return _private_error({"error": "not_found"}, status_code=404)
    except PermissionError:
        return _private_error({"error": "forbidden"}, status_code=403)
    return _json_private(_serialize_task(updated), status_code=200)


async def delete_section_task(request: Request, unit_id: str, section_id: str, task_id: str):
    """Delete a task and resequence positions."""

    user, error = _require_teacher(request)
    if error:
        return error
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    if not _is_uuid_like(unit_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    if not _is_uuid_like(section_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_section_id"}, status_code=400)
    if not _is_uuid_like(task_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_task_id"}, status_code=400)
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    try:
        _get_tasks_service().delete_task(unit_id, section_id, task_id, sub)
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404)
    except PermissionError:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    return Response(status_code=204, headers={"Cache-Control": "private, no-store"})


async def create_module_task(request: Request, unit_id: str, module_id: str, payload: TaskCreatePayload):
    """Create a task in a module-backed section with write scope only."""

    section_id, error = teaching_authoring._resolve_module_section_for_authoring_mutation(
        request,
        unit_id=unit_id,
        module_id=module_id,
        repo_provider=_get_repo,
    )
    if error:
        return error
    return await create_section_task(request, unit_id, str(section_id), payload)


async def update_module_task(
    request: Request,
    unit_id: str,
    module_id: str,
    task_id: str,
    payload: TaskUpdatePayload,
):
    """Update a task in a module-backed section with write scope only."""

    section_id, error = teaching_authoring._resolve_module_section_for_authoring_mutation(
        request,
        unit_id=unit_id,
        module_id=module_id,
        repo_provider=_get_repo,
    )
    if error:
        return error
    return await update_section_task(request, unit_id, str(section_id), task_id, payload)


async def delete_module_task(request: Request, unit_id: str, module_id: str, task_id: str):
    """Delete a task in a module-backed section with delete scope only."""

    section_id, error = teaching_authoring._resolve_module_section_for_authoring_mutation(
        request,
        unit_id=unit_id,
        module_id=module_id,
        repo_provider=_get_repo,
    )
    if error:
        return error
    return await delete_section_task(request, unit_id, str(section_id), task_id)


async def reorder_module_tasks(request: Request, unit_id: str, module_id: str, payload: TaskReorderPayload):
    """Reorder tasks in a module-backed section with write scope only."""

    section_id, error = teaching_authoring._resolve_module_section_for_authoring_mutation(
        request,
        unit_id=unit_id,
        module_id=module_id,
        repo_provider=_get_repo,
    )
    if error:
        return error
    return await reorder_section_tasks(request, unit_id, str(section_id), payload)


async def reorder_section_tasks(
    request: Request,
    unit_id: str,
    section_id: str,
    payload: TaskReorderPayload,
):
    """Reorder tasks (author only)."""

    user, error = _require_teacher(request)
    if error:
        return error
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    if not _is_uuid_like(unit_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    if not _is_uuid_like(section_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_section_id"}, status_code=400)
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    ids = payload.task_ids
    if not isinstance(ids, list):
        return JSONResponse({"error": "bad_request", "detail": "task_ids_must_be_array"}, status_code=400)
    if len(ids) == 0:
        return JSONResponse({"error": "bad_request", "detail": "empty_task_ids"}, status_code=400)
    if len(ids) != len(set(ids)):
        return JSONResponse({"error": "bad_request", "detail": "duplicate_task_ids"}, status_code=400)
    if any(not _is_uuid_like(tid) for tid in ids):
        return JSONResponse({"error": "bad_request", "detail": "invalid_task_ids"}, status_code=400)
    try:
        _get_tasks_service().list_tasks(unit_id, section_id, sub)
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404)
    try:
        ordered = _get_tasks_service().reorder_tasks(unit_id, section_id, sub, ids)
    except ValueError as exc:
        detail = str(exc) or "task_mismatch"
        return JSONResponse({"error": "bad_request", "detail": detail}, status_code=400)
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404)
    except PermissionError:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    return JSONResponse(content=[_serialize_task(t) for t in ordered], status_code=200)


async def list_section_materials(request: Request, unit_id: str, section_id: str):
    """
    List markdown materials of a section for its author.

    Why:
        The authoring UI needs an ordered list of materials per Abschnitt.

    Parameters:
        request: FastAPI request carrying the authenticated teacher session.
        unit_id: UUID of the learning unit (path parameter).
        section_id: UUID of the section within the unit (path parameter).

    Expected behavior:
        - 200 with ordered materials (position asc) when the section exists for the author.
        - 400 when `unit_id` or `section_id` are not UUID-like.
        - 403 via `_guard_unit_author` if caller is not the unit author.
        - 404 when the section is unknown to the author.

    Permissions:
        Caller must be a teacher and the author of the unit.
    """
    user, error = _require_teacher(request)
    if error:
        return error
    if not _is_uuid_like(unit_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    if not _is_uuid_like(section_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_section_id"}, status_code=400)
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    try:
        items = _get_materials_service().list_markdown_materials(unit_id, section_id, sub)
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404)
    return _json_private([_serialize_material(m) for m in items], status_code=200)


async def create_section_material(
    request: Request,
    unit_id: str,
    section_id: str,
    payload: MaterialCreatePayload,
):
    """
    Create a markdown material in a section (author only).

    Why:
        Teachers add textual resources to each Abschnitt; default behavior appends to the end.

    Parameters:
        request: FastAPI request with authenticated teacher.
        unit_id: UUID of the learning unit.
        section_id: UUID of the section where the material will live.
        payload: JSON body containing `title` and `body_md`.

    Expected behavior:
        - 201 with the created material when validation passes.
        - 400 for invalid titles/bodies or malformed UUIDs.
        - 403 when caller is not the author (guard catches earlier).
        - 404 when the section is not owned/found.

    Permissions:
        Caller must be a teacher and author of the unit/section.
    """
    user, error = _require_teacher(request)
    if error:
        return error
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    if not _is_uuid_like(unit_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    if not _is_uuid_like(section_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_section_id"}, status_code=400)
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    try:
        _get_materials_service().ensure_section_owned(unit_id, section_id, sub)
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404)
    title = payload.title or ""
    if not title or len(title) > 200:
        return JSONResponse({"error": "bad_request", "detail": "invalid_title"}, status_code=400)
    body = payload.body_md
    if body is None or not isinstance(body, str):
        return JSONResponse({"error": "bad_request", "detail": "invalid_body_md"}, status_code=400)
    try:
        material = _get_materials_service().create_markdown_material(
            unit_id,
            section_id,
            sub,
            title=title,
            body_md=body,
        )
    except ValueError as exc:
        return JSONResponse({"error": "bad_request", "detail": str(exc)}, status_code=400)
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404)
    except PermissionError:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    return _json_private(_serialize_material(material), status_code=201)


async def update_section_material(
    request: Request,
    unit_id: str,
    section_id: str,
    material_id: str,
    payload: MaterialUpdatePayload,
):
    """
    Update mutable fields of a markdown material (author only).

    Why:
        Enables fine-grained edits to titles or Markdown content without reordering.

    Parameters:
        request: FastAPI request with teacher session.
        unit_id: UUID of the learning unit (path).
        section_id: UUID of the section (path).
        material_id: UUID of the material (path).
        payload: Partial JSON body with optional `title` and/or `body_md`.

    Expected behavior:
        - 200 with updated material when at least one field is valid.
        - 400 for invalid payloads (empty, out-of-range title, non-string body).
        - 404 when the material (or section) is not owned/found.

    Permissions:
        Caller must be a teacher and author of the unit/section.
    """
    user, error = _require_teacher(request)
    if error:
        return error
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    if not _is_uuid_like(unit_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    if not _is_uuid_like(section_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_section_id"}, status_code=400)
    if not _is_uuid_like(material_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_material_id"}, status_code=400)
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    try:
        _get_materials_service().ensure_section_owned(unit_id, section_id, sub)
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404)
    if _get_materials_service().get_material_owned(unit_id, section_id, material_id, sub) is None:
        return JSONResponse({"error": "not_found"}, status_code=404)
    # Include None for provided fields to detect intentionally empty values (e.g., title="")
    raw_updates = payload.model_dump(mode="python", exclude_unset=True)
    fields_set = payload.model_fields_set
    if not fields_set:
        return JSONResponse({"error": "bad_request", "detail": "empty_payload"}, status_code=400)
    # Manual validation keeps responses aligned with our 400-contract (FastAPI would emit 422 otherwise).
    kwargs = {}
    if "title" in fields_set:
        # Normalizer maps empty/blank strings to None; treat as invalid_title when provided
        if raw_updates.get("title") is None:
            return JSONResponse({"error": "bad_request", "detail": "invalid_title"}, status_code=400)
        title_val = raw_updates.get("title") or ""
        if not title_val or len(title_val) > 200:
            return JSONResponse({"error": "bad_request", "detail": "invalid_title"}, status_code=400)
        kwargs["title"] = title_val
    if "body_md" in fields_set:
        body_val = raw_updates.get("body_md")
        if body_val is None or not isinstance(body_val, str):
            return JSONResponse({"error": "bad_request", "detail": "invalid_body_md"}, status_code=400)
        kwargs["body_md"] = body_val
    if "alt_text" in fields_set:
        alt_val = raw_updates.get("alt_text")
        if alt_val is not None and not isinstance(alt_val, str):
            return JSONResponse({"error": "bad_request", "detail": "invalid_alt_text"}, status_code=400)
        normalized_alt = (alt_val or "").strip() if isinstance(alt_val, str) else None
        kwargs["alt_text"] = normalized_alt or None
    try:
        updated = _get_materials_service().update_material(
            unit_id,
            section_id,
            material_id,
            sub,
            **kwargs,
        )
    except ValueError as exc:
        detail = str(exc) or "invalid_input"
        if detail not in {"invalid_title", "invalid_body_md", "invalid_alt_text"}:
            detail = "invalid_input"
        return JSONResponse({"error": "bad_request", "detail": detail}, status_code=400)
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404)
    except PermissionError:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    return JSONResponse(content=_serialize_material(updated), status_code=200)


async def delete_section_material(request: Request, unit_id: str, section_id: str, material_id: str):
    """
    Delete a markdown material (author only) and resequence positions.

    Why:
        Keeps material ordering contiguous (1..n) after removals.

    Parameters:
        request: FastAPI request with teacher session.
        unit_id: UUID of the learning unit.
        section_id: UUID of the section.
        material_id: UUID of the material to delete.

    Expected behavior:
        - 204 on success.
        - 400 for malformed UUIDs.
        - 404 when the material is unknown to the author.

    Permissions:
        Caller must be a teacher and the author of the unit/section.
    """
    user, error = _require_teacher(request)
    if error:
        return error
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    if not _is_uuid_like(unit_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    if not _is_uuid_like(section_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_section_id"}, status_code=400)
    if not _is_uuid_like(material_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_material_id"}, status_code=400)
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    try:
        _get_materials_service().ensure_section_owned(unit_id, section_id, sub)
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404)
    material_obj = _get_materials_service().get_material_owned(unit_id, section_id, material_id, sub)
    if material_obj is None:
        return JSONResponse({"error": "not_found"}, status_code=404)
    material_snapshot = _serialize_material(material_obj)
    storage_key = material_snapshot.get("storage_key")
    material_kind = material_snapshot.get("kind")
    # Delete storage object first to avoid orphaning when storage fails after DB deletion.
    if material_kind == "file" and storage_key:
        # Delete from storage if the adapter supports it. Some tests inject a
        # minimal FakeStorageAdapter without a delete_object method — treat that
        # as a no-op rather than failing the request.
        try:
            delete_fn = getattr(STORAGE_ADAPTER, "delete_object", None)
            if callable(delete_fn):
                delete_fn(
                    bucket=MATERIAL_FILE_SETTINGS.storage_bucket,
                    key=storage_key,
                )
        except RuntimeError as exc:  # pragma: no cover - defensive log path
            if str(exc) == "storage_adapter_not_configured":
                logger.error(
                    "Storage adapter unavailable during delete for material %s", material_id
                )
                return JSONResponse({"error": "service_unavailable"}, status_code=503)
            raise
        except Exception:  # pragma: no cover - log unexpected storage failures
            logger.exception("Failed deleting storage object for material %s", material_id)
            return JSONResponse(
                {"error": "bad_gateway", "detail": "storage_delete_failed"},
                status_code=502,
            )
    # After storage deletion succeeded (or not required), remove DB record and resequence.
    try:
        _get_materials_service().delete_material(unit_id, section_id, material_id, sub)
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404)
    except PermissionError:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    return Response(status_code=204, headers={"Cache-Control": "private, no-store"})


async def create_section_material_upload_intent(
    request: Request,
    unit_id: str,
    section_id: str,
    payload: MaterialUploadIntentPayload,
):
    """Create a presigned upload intent for a file material (author only)."""

    user, error = _require_teacher(request)
    if error:
        return error
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    if not _is_uuid_like(unit_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    if not _is_uuid_like(section_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_section_id"}, status_code=400)
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    # Keep Teaching aligned with Learning: when startup wiring failed because
    # Supabase was not reachable yet, the first real upload-intent should retry
    # wiring before failing closed with 503.
    if (
        isinstance(STORAGE_ADAPTER, NullStorageAdapter)
        and not _STORAGE_ADAPTER_OVERRIDE_ACTIVE
        and callable(_wire_storage)
    ):  # type: ignore[arg-type]
        try:
            _wire_storage()  # type: ignore[misc]
        except Exception:
            # Non-fatal; the service still fails closed below if wiring did not succeed.
            pass
    try:
        intent = _get_materials_service().create_file_upload_intent(
            unit_id,
            section_id,
            sub,
            filename=payload.filename,
            mime_type=payload.mime_type,
            size_bytes=int(payload.size_bytes),
            storage=STORAGE_ADAPTER,
        )
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404)
    except ValueError as exc:
        detail = str(exc) or "invalid_input"
        if detail not in {"mime_not_allowed", "size_exceeded", "invalid_filename"}:
            detail = "invalid_input"
        return JSONResponse({"error": "bad_request", "detail": detail}, status_code=400)
    except RuntimeError as exc:
        if str(exc) == "storage_adapter_not_configured":
            return JSONResponse({"error": "service_unavailable"}, status_code=503)
        raise
    return JSONResponse(content=intent, status_code=200)


async def finalize_section_material_upload(
    request: Request,
    unit_id: str,
    section_id: str,
    payload: MaterialFinalizePayload,
):
    """Finalize an upload intent and persist the file material."""

    user, error = _require_teacher(request)
    if error:
        return error
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    if not _is_uuid_like(unit_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    if not _is_uuid_like(section_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_section_id"}, status_code=400)
    if not _is_uuid_like(payload.intent_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_intent_id"}, status_code=400)
    # Server-side sha256 pattern validation to align with OpenAPI and avoid 422 from Pydantic.
    normalized_sha = (payload.sha256 or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", normalized_sha):
        return JSONResponse({"error": "bad_request", "detail": "checksum_mismatch"}, status_code=400)
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    try:
        material, created = _get_materials_service().finalize_file_material(
            unit_id,
            section_id,
            sub,
            intent_id=payload.intent_id,
            title=payload.title,
            sha256=payload.sha256,
            alt_text=payload.alt_text,
            storage=STORAGE_ADAPTER,
        )
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404)
    except ValueError as exc:
        detail = str(exc) or "invalid_input"
        if detail not in {
            "intent_expired",
            "checksum_mismatch",
            "invalid_title",
            "mime_not_allowed",
            "invalid_alt_text",
        }:
            detail = "invalid_input"
        return JSONResponse({"error": "bad_request", "detail": detail}, status_code=400)
    except RuntimeError as exc:
        if str(exc) == "storage_adapter_not_configured":
            return JSONResponse({"error": "service_unavailable"}, status_code=503)
        raise
    status_code = 201 if created else 200
    return JSONResponse(content=_serialize_material(material), status_code=status_code)


async def create_module_material(
    request: Request,
    unit_id: str,
    module_id: str,
    payload: MaterialCreatePayload,
):
    """Create a material in a module-backed section with write scope only."""

    section_id, error = teaching_authoring._resolve_module_section_for_authoring_mutation(
        request,
        unit_id=unit_id,
        module_id=module_id,
        repo_provider=_get_repo,
    )
    if error:
        return error
    return await create_section_material(request, unit_id, str(section_id), payload)


async def update_module_material(
    request: Request,
    unit_id: str,
    module_id: str,
    material_id: str,
    payload: MaterialUpdatePayload,
):
    """Update a material in a module-backed section with write scope only."""

    section_id, error = teaching_authoring._resolve_module_section_for_authoring_mutation(
        request,
        unit_id=unit_id,
        module_id=module_id,
        repo_provider=_get_repo,
    )
    if error:
        return error
    return await update_section_material(request, unit_id, str(section_id), material_id, payload)


async def delete_module_material(request: Request, unit_id: str, module_id: str, material_id: str):
    """Delete a material in a module-backed section with delete scope only."""

    section_id, error = teaching_authoring._resolve_module_section_for_authoring_mutation(
        request,
        unit_id=unit_id,
        module_id=module_id,
        repo_provider=_get_repo,
    )
    if error:
        return error
    return await delete_section_material(request, unit_id, str(section_id), material_id)


async def reorder_module_materials(
    request: Request,
    unit_id: str,
    module_id: str,
    payload: MaterialReorderPayload,
):
    """Reorder materials in a module-backed section with write scope only."""

    section_id, error = teaching_authoring._resolve_module_section_for_authoring_mutation(
        request,
        unit_id=unit_id,
        module_id=module_id,
        repo_provider=_get_repo,
    )
    if error:
        return error
    return await reorder_section_materials(request, unit_id, str(section_id), payload)


async def create_module_material_upload_intent(
    request: Request,
    unit_id: str,
    module_id: str,
    payload: MaterialUploadIntentPayload,
):
    """Create a file-material upload intent in a module with write scope only."""

    section_id, error = teaching_authoring._resolve_module_section_for_authoring_mutation(
        request,
        unit_id=unit_id,
        module_id=module_id,
        repo_provider=_get_repo,
    )
    if error:
        return error
    return await create_section_material_upload_intent(request, unit_id, str(section_id), payload)


async def finalize_module_material_upload(
    request: Request,
    unit_id: str,
    module_id: str,
    payload: MaterialFinalizePayload,
):
    """Finalize a file-material upload in a module with write scope only."""

    section_id, error = teaching_authoring._resolve_module_section_for_authoring_mutation(
        request,
        unit_id=unit_id,
        module_id=module_id,
        repo_provider=_get_repo,
    )
    if error:
        return error
    return await finalize_section_material_upload(request, unit_id, str(section_id), payload)


async def get_section_material_download_url(
    request: Request,
    unit_id: str,
    section_id: str,
    material_id: str,
    disposition: Optional[str] = None,
):
    """Generate a short-lived download URL for a file material."""

    user, error = _require_teacher(request)
    if error:
        return error
    if not _is_uuid_like(unit_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    if not _is_uuid_like(section_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_section_id"}, status_code=400)
    if not _is_uuid_like(material_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_material_id"}, status_code=400)
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    # Normalize and validate disposition at the route layer to return 400 (not FastAPI 422).
    normalized_disposition = (disposition or "attachment").strip().lower()
    if normalized_disposition not in {"inline", "attachment"}:
        return JSONResponse({"error": "bad_request", "detail": "invalid_disposition"}, status_code=400)
    try:
        payload = _get_materials_service().generate_file_download_url(
            unit_id,
            section_id,
            material_id,
            sub,
            disposition=normalized_disposition,
            storage=STORAGE_ADAPTER,
        )
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404)
    except ValueError as exc:
        detail = str(exc) or "invalid_input"
        if detail not in {"invalid_disposition"}:
            detail = "invalid_input"
        return JSONResponse({"error": "bad_request", "detail": detail}, status_code=400)
    except RuntimeError as exc:
        if str(exc) == "storage_adapter_not_configured":
            return JSONResponse({"error": "service_unavailable"}, status_code=503)
        raise
    return JSONResponse(content=payload, status_code=200, headers={"Cache-Control": "private, no-store"})


async def reorder_section_materials(
    request: Request,
    unit_id: str,
    section_id: str,
    payload: MaterialReorderPayload,
):
    """
    Reorder materials within a section (author only).

    Why:
        Allows teachers to define the pedagogical flow; uses deferrable constraints for atomic swaps.

    Parameters:
        request: FastAPI request with teacher session.
        unit_id: Learning unit UUID (path).
        section_id: Section UUID (path).
        payload: JSON body containing `material_ids` as the desired order.

    Expected behavior:
        - 200 with the reordered materials list.
        - 400 for invalid payload shapes (non-array, empty, duplicates, non-UUIDs, mismatch).
        - 404 when submitted IDs refer to unknown materials in the unit.

    Permissions:
        Caller must be a teacher and author of the unit/section.
    """
    user, error = _require_teacher(request)
    if error:
        return error
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    if not _is_uuid_like(unit_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    if not _is_uuid_like(section_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_section_id"}, status_code=400)
    sub = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    ids = payload.material_ids
    # Validate payload shape before delegating to the service to avoid leaking database semantics.
    if not isinstance(ids, list):
        return JSONResponse({"error": "bad_request", "detail": "material_ids_must_be_array"}, status_code=400)
    if len(ids) == 0:
        return JSONResponse({"error": "bad_request", "detail": "empty_material_ids"}, status_code=400)
    if len(ids) != len(set(ids)):
        return JSONResponse({"error": "bad_request", "detail": "duplicate_material_ids"}, status_code=400)
    if any(not _is_uuid_like(mid) for mid in ids):
        return JSONResponse({"error": "bad_request", "detail": "invalid_material_ids"}, status_code=400)
    try:
        _get_materials_service().ensure_section_owned(unit_id, section_id, sub)
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404)
    try:
        ordered = _get_materials_service().reorder_markdown_materials(unit_id, section_id, sub, ids)
    except ValueError as exc:
        return JSONResponse({"error": "bad_request", "detail": str(exc)}, status_code=400)
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404)
    except PermissionError:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    return JSONResponse(content=[_serialize_material(m) for m in ordered], status_code=200)


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
    guard = teaching_guards._guard_course_owner(course_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    try:
        modules = _get_repo().list_course_modules_for_owner(course_id, sub)
    except Exception as exc:
        logger.warning("list_course_modules failed cid=%s err=%s", course_id[-6:], exc.__class__.__name__)
        return JSONResponse({"error": "forbidden"}, status_code=403)
    return JSONResponse(content=[_serialize_module(m) for m in modules], status_code=200)


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
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    sub = _current_sub(user)
    unit_id = payload.unit_id
    if not _is_uuid_like(unit_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    try:
        guard_course = teaching_guards._guard_course_owner(course_id, sub, repo_provider=_get_repo)
        if guard_course:
            return guard_course
        guard_unit = teaching_guards._guard_unit_author(unit_id, sub, repo_provider=_get_repo)
        if guard_unit:
            return guard_unit
        module = _get_repo().create_course_module_owned(
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
    return _json_private(_serialize_module(module), status_code=201)


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
    repo = _get_repo()
    user, error = _require_teacher(request)
    if error:
        return error
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    if not _is_uuid_like(course_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_course_id"}, status_code=400)
    sub = _current_sub(user)
    # Security-first: check ownership before deep payload validation to avoid error oracle
    guard = teaching_guards._guard_course_owner(course_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    module_ids = payload.module_ids
    # Validate JSON structure and constraints explicitly (400s, not FastAPI 422)
    if not isinstance(module_ids, list):
        return JSONResponse({"error": "bad_request", "detail": "invalid_module_ids"}, status_code=400)
    if len(module_ids) == 0:
        return JSONResponse({"error": "bad_request", "detail": "empty_reorder"}, status_code=400)
    if len(set(module_ids)) != len(module_ids):
        return JSONResponse({"error": "bad_request", "detail": "duplicate_module_ids"}, status_code=400)
    if any(not _is_uuid_like(mid) for mid in module_ids):
        return JSONResponse({"error": "bad_request", "detail": "invalid_module_ids"}, status_code=400)
    try:
        modules = repo.reorder_course_modules_owned(course_id, sub, module_ids)
    except ValueError as exc:
        detail = str(exc)
        return JSONResponse({"error": "bad_request", "detail": detail}, status_code=400)
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404)
    except PermissionError:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    # Uniform API shape: explicit JSONResponse with status 200
    return JSONResponse(content=[_serialize_module(m) for m in modules], status_code=200)


async def delete_course_module(request: Request, course_id: str, module_id: str):
    """
    Remove a unit from a course (owner only).

    Why:
        Teachers need to detach mistakenly added units and keep positions tidy.

    Behavior:
        - 204 on success.
        - 400 when `course_id` or `module_id` are not UUID-like.
        - 403/404 via ownership guard and RLS visibility.

    Permissions:
        Caller must be a teacher and the owner of the course.
    """
    user, error = _require_teacher(request)
    if error:
        return error
    if not _is_uuid_like(course_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_course_id"}, status_code=400)
    if not _is_uuid_like(module_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_module_id"}, status_code=400)
    sub = _current_sub(user)
    guard = teaching_guards._guard_course_owner(course_id, sub, repo_provider=_get_repo)
    if guard:
        return guard
    try:
        # CSRF guard for DELETE
        csrf = teaching_guards._csrf_guard(request)
        if csrf:
            return csrf
        deleted = _get_repo().delete_course_module_owned(course_id, module_id, sub)
    except PermissionError:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    if not deleted:
        return JSONResponse({"error": "not_found"}, status_code=404)
    return Response(status_code=204, headers={"Cache-Control": "private, no-store"})

async def update_module_section_visibility(
    request: Request,
    course_id: str,
    module_id: str,
    section_id: str,
    payload: ModuleSectionVisibilityPayload,
):
    """
    Toggle the visibility of a section within a course module.

    Why:
        Course owners decide when students can access individual sections.

    Parameters:
        request: FastAPI request containing the authenticated session.
        course_id: Course identifier whose module will be updated.
        module_id: Identifier of the course module referencing the unit.
        section_id: Identifier of the section to release or hide.
        payload: Body containing the `visible` flag.

    Security:
        - Requires role `teacher` and course ownership (RLS enforced in repo).
        - Enforces same-origin for browser requests (Origin/Referer must match).
        - All responses include `Cache-Control: private, no-store`.

    Behavior:
        - 200 with the persisted visibility record.
        - 400 on invalid identifiers or payload (`missing_visible`, `invalid_visible_type`).
        - 403 when caller is not the course owner or on CSRF violation (`detail=csrf_violation`).
        - 404 when the module or section is unknown for the course.
    """
    user, error = _require_teacher(request)
    if error:
        return _private_error({"error": "forbidden"}, status_code=403, vary_origin=True)

    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf

    if not _is_uuid_like(course_id):
        return _private_error(
            {"error": "bad_request", "detail": "invalid_course_id"},
            status_code=400,
            vary_origin=True,
        )
    if not _is_uuid_like(module_id):
        return _private_error(
            {"error": "bad_request", "detail": "invalid_module_id"},
            status_code=400,
            vary_origin=True,
        )
    if not _is_uuid_like(section_id):
        return _private_error(
            {"error": "bad_request", "detail": "invalid_section_id"},
            status_code=400,
            vary_origin=True,
        )
    sub = _current_sub(user)
    guard = teaching_guards._guard_course_owner(course_id, sub, repo_provider=_get_repo)
    if guard:
        # Normalize guard response to include private cache header
        if isinstance(guard, JSONResponse):
            guard.headers.setdefault("Cache-Control", "private, no-store")
            guard.headers.setdefault("Vary", "Origin")
            return guard
        return _private_error({"error": "forbidden"}, status_code=403, vary_origin=True)
    visible_value = payload.visible
    if visible_value is None:
        return _private_error(
            {"error": "bad_request", "detail": "missing_visible"},
            status_code=400,
            vary_origin=True,
        )
    if not isinstance(visible_value, bool):
        return _private_error(
            {"error": "bad_request", "detail": "invalid_visible_type"},
            status_code=400,
            vary_origin=True,
        )
    try:
        # Repository applies transactional upsert with RLS enforcement.
        record = _get_repo().set_module_section_visibility(course_id, module_id, section_id, sub, visible_value)
    except LookupError as exc:
        detail = str(exc) or None
        body = {"error": "not_found", "detail": (detail or "not_found")}
        return _private_error(body, status_code=404, vary_origin=True)
    except PermissionError:
        return _private_error({"error": "forbidden"}, status_code=403, vary_origin=True)
    return _json_private(record, status_code=200, vary_origin=True)


async def list_module_section_releases(request: Request, course_id: str, module_id: str):
    """List release state entries for sections in a module (owner only).

    Permissions:
        Caller must be a teacher and the owner of the course.
    """
    user = getattr(request.state, "user", None)
    sub = _current_sub(user)
    if not _role_in(user, "teacher"):
        return _private_error({"error": "forbidden"}, status_code=403, vary_origin=True)
    if not _is_uuid_like(course_id):
        return _private_error({"error": "bad_request", "detail": "invalid_course_id"}, status_code=400, vary_origin=True)
    if not _is_uuid_like(module_id):
        return _private_error({"error": "bad_request", "detail": "invalid_module_id"}, status_code=400, vary_origin=True)
    # Guard ownership (403/404 semantics handled by helper)
    guard = teaching_guards._guard_course_owner(course_id, sub, repo_provider=_get_repo)
    if guard:
        if isinstance(guard, JSONResponse):
            guard.headers.setdefault("Cache-Control", "private, no-store")
            guard.headers.setdefault("Vary", "Origin")
            return guard
        return _private_error({"error": "forbidden"}, status_code=403, vary_origin=True)
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore
        repo = _get_repo()
        if isinstance(repo, DBTeachingRepo):
            releases = repo.list_module_section_releases_owned(course_id, module_id, sub)
        else:
            # In-memory: derive from internal state
            entries = []
            # Sections for module's unit
            module = repo.course_modules.get(module_id)
            if not module or module.course_id != course_id:
                return _private_error({"error": "not_found"}, status_code=404, vary_origin=True)
            for (mid, sid), rec in repo.module_section_releases.items():
                if mid == module_id:
                    entries.append(rec)
            releases = entries
    except LookupError:
        return _private_error({"error": "not_found"}, status_code=404, vary_origin=True)
    except PermissionError:
        return _private_error({"error": "forbidden"}, status_code=403, vary_origin=True)
    return _json_private(releases, status_code=200, vary_origin=True)


async def list_module_sections_with_visibility(request: Request, course_id: str, module_id: str):
    """List sections of the unit attached to a module, with visibility state.

    Why:
        The Unterricht view needs a single owner-scoped listing that combines
        ordered unit sections with the release state stored in
        `module_section_releases`. This allows teachers to toggle visibility
        without switching pages.

    Behavior:
        - 200: Returns an array of sections sorted by `position` with fields
          `{id, unit_id, title, position, visible, released_at}`. Missing release
          rows imply `visible=false`, `released_at=null`.
        - 400: Invalid UUIDs (detail: `invalid_course_id` | `invalid_module_id`).
        - 401/403: Unauthenticated or not the course owner.
        - 404: The module is unknown for the given course (or not owned).

    Permissions:
        Caller must be a teacher and the owner of the course. RLS and explicit
        ownership guards apply. Responses are private and non-cacheable.
    """
    repo = _get_repo()
    user, error = _require_teacher(request)
    if error:
        # Normalize error with private cache headers and Origin variance
        error.headers.setdefault("Cache-Control", "private, no-store")
        error.headers.setdefault("Vary", "Origin")
        return error
    if not _is_uuid_like(course_id):
        return _private_error({"error": "bad_request", "detail": "invalid_course_id"}, status_code=400, vary_origin=True)
    if not _is_uuid_like(module_id):
        return _private_error({"error": "bad_request", "detail": "invalid_module_id"}, status_code=400, vary_origin=True)

    sub = _current_sub(user)
    # Owner guard (ensures teacher owns the course)
    guard = teaching_guards._guard_course_owner(course_id, sub, repo_provider=_get_repo)
    if guard:
        if isinstance(guard, JSONResponse):
            guard.headers.setdefault("Cache-Control", "private, no-store")
            guard.headers.setdefault("Vary", "Origin")
            return guard
        return _private_error({"error": "forbidden"}, status_code=403, vary_origin=True)

    unit_id: str | None = None
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore
        if isinstance(repo, DBTeachingRepo):
            modules = repo.list_course_modules_for_owner(course_id, sub)
            for m in modules:
                if str(m.get("id")) == str(module_id):
                    unit_id = str(m.get("unit_id") or "")
                    break
        else:
            # In-memory fallback
            mods = [asdict(m) if is_dataclass(m) else m for m in repo.list_course_modules_for_owner(course_id, sub)]
            for m in mods:
                if str(m.get("id")) == str(module_id):
                    unit_id = str(m.get("unit_id") or "")
                    break
    except Exception:
        unit_id = None

    if not unit_id:
        return _private_error({"error": "not_found"}, status_code=404, vary_origin=True)

    # Fetch sections (ordered) and release rows; then merge in Python.
    sections: list[dict] = []
    releases: list[dict] = []
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore
        repo = _get_repo()
        if isinstance(repo, DBTeachingRepo):
            sections = repo.list_sections_for_author(unit_id, sub)
            releases = repo.list_module_section_releases_owned(course_id, module_id, sub)
        else:
            # In-memory
            sections = [
                _serialize_section(s)
                for s in repo.list_sections_for_author(unit_id, sub)
            ]
            releases = repo.list_module_section_releases_owned(course_id, module_id, sub)
    except LookupError:
        return _private_error({"error": "not_found"}, status_code=404, vary_origin=True)
    except PermissionError:
        return _private_error({"error": "forbidden"}, status_code=403, vary_origin=True)
    except Exception:
        sections, releases = [], []

    rel_map: dict[str, dict] = {str(r.get("section_id")): r for r in releases}
    out: list[dict] = []
    for s in sections:
        sid = str(s.get("id"))
        r = rel_map.get(sid)
        visible = bool(r.get("visible")) if isinstance(r, dict) else False
        released_at = r.get("released_at") if (isinstance(r, dict) and visible) else None
        out.append(
            {
                "id": sid,
                "unit_id": str(s.get("unit_id") or ""),
                "title": str(s.get("title") or ""),
                # Contract: position is 1-based; clamp to minimum 1 for safety.
                "position": max(1, int(s.get("position") or 1)),
                "visible": visible,
                "released_at": released_at,
            }
        )

    return _json_private(out, status_code=200, vary_origin=True)


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
        - If `repo.course_exists` deterministically returns False: 404.
        - Otherwise: 403 to avoid leaking information.
    """
    repo = _get_repo()
    # Owner just deleted? Prefer 404 for immediate follow-ups
    if _was_recently_deleted(owner_sub, course_id):
        return _private_error({"error": "not_found"}, status_code=404)
    try:
        ex = repo.course_exists(course_id)
    except Exception:
        ex = None
    if ex is False:
        # Deterministic contract: non-existent course -> 404
        return _private_error({"error": "not_found"}, status_code=404)
    return _private_error({"error": "forbidden"}, status_code=403)


async def list_members(request: Request, course_id: str, limit: int = 10, offset: int = 0):
    """List members for a course — owner-only, with names resolved via directory adapter.

    Why:
        Owners need to view roster with minimal PII. Names are resolved on-the-fly
        from identity directory using stable `sub` identifiers.

    Behavior:
        - 200 with [{ sub, name, joined_at }]
        - 403 when caller is not owner; 404 when the course does not exist
        - Pagination via limit (1..50) and offset (>=0); default limit = 10

    Permissions:
        Caller must be a teacher AND owner of the course.
    """
    user = getattr(request.state, "user", None)
    sub = _current_sub(user)
    if not _role_in(user, "teacher"):
        return _private_error({"error": "forbidden"}, status_code=403)
    limit, offset = _clamp_limit_offset(limit=limit, offset=offset, default_limit=10, max_limit=50)
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore
        repo = _get_repo()
        if isinstance(repo, DBTeachingRepo):
            if not repo.course_exists_for_owner(course_id, sub):
                return _resp_non_owner_or_unknown(course_id, sub)
            pairs = repo.list_members_for_owner(course_id, sub, limit=limit, offset=offset)
        else:
            # Fallback in-memory owner check
            course = repo.get_course(course_id)
            if not course:
                return _private_error({"error": "not_found"}, status_code=404)
            if _teacher_id_of(course) != sub:
                return _private_error({"error": "forbidden"}, status_code=403)
            pairs = repo.list_members(course_id, limit=limit, offset=offset)
    except Exception as exc:
        # Defensive default: if DB helper path fails, do not risk information leakage.
        # Log for observability, avoid logging full identifiers to minimize PII exposure.
        cid_tail = (course_id or "").replace("-", "")[-6:]
        logger.warning("list_members failed: cid_tail=%s err=%s", cid_tail, exc.__class__.__name__)
        return _private_error({"error": "forbidden"}, status_code=403)
    subs = [sid for sid, _ in pairs]
    # Avoid blocking the event loop on synchronous network I/O
    names = await asyncio.to_thread(_resolve_student_names_runtime, subs)
    result = []
    for sid, joined_at in pairs:
        result.append({"sub": sid, "name": names.get(sid, sid), "joined_at": joined_at})
    return _json_private(result, status_code=200)


class AddMember(BaseModel):
    # Keep optional to return 400 (not FastAPI 422) when missing/empty
    # Accept both contract key `student_sub` (preferred) and legacy/test key `sub`.
    student_sub: str | None = None
    sub: str | None = None
    name: str | None = None  # ignored by API, accepted for compatibility


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
        return _private_error({"error": "forbidden"}, status_code=403)
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    # Prefer the contract key; fall back to legacy `sub` for compatibility with older callers/tests.
    student_sub = getattr(payload, "student_sub", None) or getattr(payload, "sub", None)
    if not isinstance(student_sub, str) or not student_sub.strip():
        return _private_error({"error": "bad_request", "detail": "student_sub_required"}, status_code=400)
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore
        repo = _get_repo()
        if isinstance(repo, DBTeachingRepo):
            # Ensure caller owns the course; otherwise decide 404/403 via helper
            if not repo.course_exists_for_owner(course_id, sub):
                return _resp_non_owner_or_unknown(course_id, sub)
            created = repo.add_member_owned(course_id, sub, student_sub.strip())
        else:
            # Fallback owner check
            course = repo.get_course(course_id)
            if not course:
                return _private_error({"error": "not_found"}, status_code=404)
            if _teacher_id_of(course) != sub:
                return _private_error({"error": "forbidden"}, status_code=403)
            created = repo.add_member(course_id, student_sub.strip())
    except Exception:
        # Fail closed: do not attempt mutation without clear ownership/existence semantics
        return _resp_non_owner_or_unknown(course_id, sub)
    if created:
        return _json_private({}, status_code=201)
    return Response(status_code=204, headers={"Cache-Control": "private, no-store"})


async def remove_member(request: Request, course_id: str, student_sub: str):
    """Remove a student from a course — owner-only; idempotent 204.

    Behavior:
        - 204 even if the student is not currently a member
        - 403 when caller is not owner

    Permissions:
        Caller must be a teacher AND owner of the course.
    """
    repo = _get_repo()
    user = getattr(request.state, "user", None)
    sub = _current_sub(user)
    if not _role_in(user, "teacher"):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    # CSRF guard for membership mutation
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore
        if isinstance(repo, DBTeachingRepo):
            if not repo.course_exists_for_owner(course_id, sub):
                return _resp_non_owner_or_unknown(course_id, sub)
            repo.remove_member_owned(course_id, sub, str(student_sub))
        else:
            course = repo.get_course(course_id)
            if not course:
                return JSONResponse({"error": "not_found"}, status_code=404)
            if _teacher_id_of(course) != sub:
                return JSONResponse({"error": "forbidden"}, status_code=403)
            repo.remove_member(course_id, str(student_sub))
    except Exception:
        # Fail closed: do not attempt mutation without clear ownership/existence semantics
        return _resp_non_owner_or_unknown(course_id, sub)
    return Response(status_code=204, headers={"Cache-Control": "private, no-store"})


async def get_unit_live_summary(
    request: Request,
    course_id: str,
    unit_id: str,
    updated_since: str | None = None,
    limit: int = 100,
    offset: int = 0,
    include_students: bool = True,
):
    """
    Live overview for a unit (owner): tasks and student rows with minimal status.

    Why:
        Provide a compact matrix (students × unit tasks) indicating only whether
        a submission exists per cell. Teachers can then drill into details
        without loading content in the summary call.

    Security:
        - Requires `teacher` role and course ownership.
        - Unit must be attached to the course for the owner.
        - Responses use private, no-store caching and vary by Origin.

    Notes:
        - Tasks are fetched via the owner scope; a dedicated application use case
          will consolidate this logic in a later iteration.
        - Submission lookups prefer the SECURITY DEFINER helper. When the helper
          is missing or inaccessible (e.g. migration not applied) we log a
          warning and fall back to RLS-safe bulk queries.
        - `updated_since` is optional; invalid timestamps produce
          `400 invalid_timestamp` so clients adjust their cursors.
    """
    repo = _get_repo()
    user, forbidden = _require_teacher(request)
    if forbidden:
        forbidden.headers.setdefault("Cache-Control", "private, no-store")
        forbidden.headers.setdefault("Vary", "Origin")
        return forbidden
    if not (_is_uuid_like(course_id) and _is_uuid_like(unit_id)):
        return _private_error({"error": "bad_request", "detail": "invalid_uuid"}, status_code=400, vary_origin=True)
    sub = _current_sub(user)

    updated_since_dt: datetime | None = None
    if updated_since:
        try:
            normalized = updated_since.replace("Z", "+00:00")
            parsed = datetime.fromisoformat(normalized)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            updated_since_dt = parsed.astimezone(timezone.utc)
        except ValueError:
            return _private_error({"error": "bad_request", "detail": "invalid_timestamp"}, status_code=400, vary_origin=True)

    # Ownership guard
    guard = teaching_guards._guard_course_owner(course_id, sub, repo_provider=_get_repo)
    if guard:
        if isinstance(guard, JSONResponse):
            guard.headers.setdefault("Cache-Control", "private, no-store")
            guard.headers.setdefault("Vary", "Origin")
            return guard
        return _private_error({"error": "forbidden"}, status_code=403, vary_origin=True)

    # Verify unit is attached to course for the owner
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore
        repo = _get_repo()
        if isinstance(repo, DBTeachingRepo):
            modules = repo.list_course_modules_for_owner(course_id, sub)
        else:
            modules = [asdict(m) if is_dataclass(m) else m for m in repo.list_course_modules_for_owner(course_id, sub)]
    except Exception:
        modules = []
    if str(unit_id) not in {str(m.get("unit_id")) for m in modules}:
        return _private_error({"error": "not_found"}, status_code=404, vary_origin=True)
    snapshot_cursor = _summary_snapshot_cursor_runtime(repo, sub)
    if not snapshot_cursor:
        return _private_error(
            {"error": "service_unavailable", "detail": "summary_cursor_unavailable"},
            status_code=503,
            vary_origin=True,
        )

    # Build task list across the unit in position order
    tasks: list[dict] = []
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore
        if isinstance(repo, DBTeachingRepo):
            sections = repo.list_sections_for_author(unit_id, sub)  # owner==author in tests
            for sec in sections:
                sec_tasks = repo.list_tasks_for_section_owned(unit_id, sec["id"], sub)
                for t in sec_tasks:
                    tasks.append({
                        "id": t["id"],
                        # API contract: tasks carry instruction_md (not a separate title)
                        "instruction_md": t.get("instruction_md") or "",
                        "position": int(t.get("position") or 0),
                        "kind": str(t.get("kind") or "native"),
                    })
        else:
            # In-memory repo fallback
            section_ids = [sid for sid, sd in repo.sections.items() if sd.unit_id == unit_id]
            section_ids.sort(key=lambda sid: repo.sections[sid].position)
            for sid in section_ids:
                tids = repo.task_ids_by_section.get(sid, [])
                for tid in tids:
                    td = repo.tasks[tid]
                    tasks.append({
                        "id": td.id,
                        "instruction_md": td.instruction_md or "",
                        "position": int(td.position),
                        "kind": str(getattr(td, "kind", "native") or "native"),
                    })
    except Exception:
        tasks = []

    rows_out: list[dict] = []
    if include_students:
        roster: list[tuple[str, str]] = []
        try:
            from backend.teaching.repo_db import DBTeachingRepo  # type: ignore
            if isinstance(repo, DBTeachingRepo):
                roster = repo.list_members_for_owner(course_id, sub, limit=limit, offset=offset)
            else:
                members = repo.members.get(course_id, {})
                roster = sorted([(k, v) for k, v in members.items()], key=lambda kv: kv[1])
                roster = roster[offset: offset + limit]
        except Exception:
            roster = []
        member_subs = [sid for sid, _ in roster]
        names = await asyncio.to_thread(resolve_live_student_names_by_sub, member_subs)

        has_map: set[tuple[str, str]] = set()
        avg_map: dict[tuple[str, str], float | None] = {}
        h5p_map: dict[tuple[str, str], bool] = {}
        score_map: dict[tuple[str, str], tuple[int | None, int | None]] = {}
        created_at_map: dict[tuple[str, str], str | None] = {}
        try:
            from backend.teaching.repo_db import DBTeachingRepo  # type: ignore
            if isinstance(repo, DBTeachingRepo):
                try:
                    aggregate_rows = repo.list_unit_latest_submission_aggregates_for_owner(
                        course_id=course_id,
                        unit_id=unit_id,
                        owner_sub=sub,
                        student_subs=member_subs,
                    )
                    has_map = {
                        (str(row.get("student_sub") or ""), str(row.get("task_id") or ""))
                        for row in aggregate_rows
                        if bool(row.get("has_submission"))
                    }
                    avg_map = {
                        (str(row.get("student_sub") or ""), str(row.get("task_id") or "")): row.get("average_score")
                        for row in aggregate_rows
                    }
                    h5p_map = {
                        (str(row.get("student_sub") or ""), str(row.get("task_id") or "")): bool(row.get("h5p_completed"))
                        for row in aggregate_rows
                        if row.get("h5p_completed") is not None
                    }
                    score_map = {
                        (str(row.get("student_sub") or ""), str(row.get("task_id") or "")): (
                            _safe_int(row.get("score_raw")),
                            _safe_int(row.get("score_max")),
                        )
                        for row in aggregate_rows
                    }
                    created_at_map = {
                        (str(row.get("student_sub") or ""), str(row.get("task_id") or "")): str(row.get("created_at_iso") or "")
                        for row in aggregate_rows
                        if row.get("created_at_iso")
                    }
                except Exception as exc:
                    logger.warning(
                        "Unit summary bulk aggregate fallback: get_unit_latest_submission_aggregates_for_owner unavailable — %s",
                        exc,
                        extra={"course_id": course_id, "unit_id": unit_id},
                    )
                    helper_rows: list[dict[str, Any]] = []
                    try:
                        helper_rows = _load_unit_live_helper_rows(
                            repo,
                            owner_sub=sub,
                            course_id=course_id,
                            unit_id=unit_id,
                            updated_since_dt=updated_since_dt,
                            limit=int(limit),
                            offset=int(offset),
                        )
                        has_map = {(str(row["student_sub"]), str(row["task_id"])) for row in helper_rows}
                        task_ids_by_student: dict[str, list[str]] = {}
                        for row in helper_rows:
                            student_sub = str(row["student_sub"])
                            task_ids_by_student.setdefault(student_sub, []).append(str(row["task_id"]))
                        latest_state_by_task = (
                            _load_latest_submission_state_by_task(repo, sub, course_id, task_ids_by_student)
                            if any(
                                row.get("score_raw") is None or row.get("score_max") is None
                                for row in helper_rows
                            )
                            else {}
                        )
                        submission_ids_by_student: dict[str, list[str]] = {}
                        for row in helper_rows:
                            student_sub = str(row["student_sub"])
                            task_id = str(row["task_id"])
                            latest_state = latest_state_by_task.get((student_sub, task_id), {})
                            submission_id = latest_state.get("submission_id") or row.get("submission_id")
                            if submission_id:
                                submission_ids_by_student.setdefault(student_sub, []).append(submission_id)
                            score_raw = _safe_int(row.get("score_raw"))
                            score_max = _safe_int(row.get("score_max"))
                            if score_raw is None or score_max is None:
                                score_raw = latest_state.get("score_raw", score_raw)
                                score_max = latest_state.get("score_max", score_max)
                            score_map[(student_sub, task_id)] = (score_raw, score_max)
                        avg_by_id = _load_average_scores_by_submission_id(repo, sub, submission_ids_by_student)
                        avg_map = {
                            (
                                str(row["student_sub"]),
                                str(row["task_id"]),
                            ): avg_by_id.get(
                                latest_state_by_task.get((str(row["student_sub"]), str(row["task_id"])), {}).get(
                                    "submission_id"
                                )
                                or row.get("submission_id")
                            )
                            for row in helper_rows
                        }
                        h5p_map = {
                            (str(row["student_sub"]), str(row["task_id"])): bool(row["h5p_completed"])
                            for row in helper_rows
                            if row.get("h5p_completed") is not None
                        }
                        created_at_map = {
                            (str(row["student_sub"]), str(row["task_id"])): str(row.get("created_at_iso") or "")
                            for row in helper_rows
                            if row.get("created_at_iso")
                        }

                        if tasks and member_subs:
                            task_ids = [t["id"] for t in tasks]
                            if not has_map:
                                fallback_rows = repo.list_unit_live_summary_fallback_rows(
                                    owner_sub=sub,
                                    course_id=course_id,
                                    task_ids=task_ids,
                                    member_subs=member_subs,
                                )
                                has_map = {(str(student_sub), str(task_id)) for student_sub, task_id, _ in fallback_rows}
                                created_at_map.update(
                                    {
                                        (str(student_sub), str(task_id)): str(created_at_iso or "")
                                        for student_sub, task_id, created_at_iso in fallback_rows
                                        if created_at_iso
                                    }
                                )
                            if not has_map:
                                for sid in member_subs:
                                    sid_rows = repo.list_unit_live_task_ids_for_student(
                                        owner_sub=sub,
                                        course_id=course_id,
                                        student_sub=sid,
                                        task_ids=task_ids,
                                    )
                                    for task_id, created_at_iso in sid_rows:
                                        has_map.add((sid, task_id))
                                        if created_at_iso:
                                            created_at_map[(sid, task_id)] = str(created_at_iso)
                    except Exception as legacy_exc:
                        logger.warning(
                            "Unit summary fallback: get_unit_latest_submissions_for_owner unavailable — %s",
                            legacy_exc,
                            extra={"course_id": course_id, "unit_id": unit_id},
                        )
                        helper_rows = []
        except Exception:
            has_map = set()
            avg_map = {}
            h5p_map = {}
            score_map = {}
            created_at_map = {}

        rows_out = _build_live_summary_rows(
            members=member_subs,
            names=names,
            tasks=tasks,
            has_map=has_map,
            avg_map=avg_map,
            created_at_map=created_at_map,
            score_map=score_map,
            h5p_map=h5p_map,
        )

    payload = {
        "cursor": snapshot_cursor,
        "tasks": tasks,
        "rows": rows_out,
    }
    # private + Vary: Origin per contract
    return _json_private(payload, status_code=200, vary_origin=True)


async def get_unit_live_delta(
    request: Request,
    course_id: str,
    unit_id: str,
    updated_since: str,
    limit: int = 200,
    offset: int = 0,
):
    """Return only changed submission cells since `updated_since` (owner-only).

    Intent (Why):
        Supports polling-based live updates for the teacher's unit view. Instead
        of streaming, the client periodically requests only changed cells since
        the last known cursor to keep payloads small and behaviour simple.

    Parameters:
        - course_id: UUID of the course (path). Must be owned by the caller.
        - unit_id: UUID of the unit (path). Must be attached to the course.
        - updated_since: ISO-8601 timestamp (with timezone). The endpoint returns
          only cells whose "change timestamp" is strictly greater than this value.
        - limit/offset: Pagination of changed cells (server clamps range).

    Expected behaviour:
        - 200 with {"cells": [...]} when there are changes. Each cell contains
          student_sub, task_id, has_submission (bool), changed_at (ISO, microseconds).
        - 204 No Content when there are no changes since the cursor.
        - 400 for invalid UUIDs or malformed timestamps.
        - 403 when the caller is not the course owner; 404 when the unit is not
          attached to the course.

    Security / Permissions:
        - Caller must be a teacher and owner of the course (RLS enforced via
          `gustav_limited` + app.current_sub, plus explicit ownership checks).
        - No content (student work) is returned, only minimal status/IDs.
        - Responses use "private, no-store" and vary by Origin to prevent leaks.
    """
    repo = _get_repo()
    user, forbidden = _require_teacher(request)
    if forbidden:
        forbidden.headers.setdefault("Cache-Control", "private, no-store")
        forbidden.headers.setdefault("Vary", "Origin")
        return forbidden
    if not (_is_uuid_like(course_id) and _is_uuid_like(unit_id)):
        return _private_error({"error": "bad_request", "detail": "invalid_uuid"}, status_code=400, vary_origin=True)

    limit = max(1, min(int(limit or 200), 500))
    offset = max(0, int(offset or 0))

    try:
        normalized = updated_since.replace("Z", "+00:00")
        updated_since_dt = datetime.fromisoformat(normalized)
        if updated_since_dt.tzinfo is None:
            updated_since_dt = updated_since_dt.replace(tzinfo=timezone.utc)
        updated_since_dt = updated_since_dt.astimezone(timezone.utc)
        original_updated_dt = updated_since_dt
        # Use the client's cursor as the DB lower bound (exclusive in SQL helper).
        # We rely on strict in-memory filtering to avoid duplicates.
        db_lower_bound = original_updated_dt
    except ValueError:
        return _private_error({"error": "bad_request", "detail": "invalid_timestamp"}, status_code=400, vary_origin=True)

    sub = _current_sub(user)
    guard = teaching_guards._guard_course_owner(course_id, sub, repo_provider=_get_repo)
    if guard:
        if isinstance(guard, JSONResponse):
            guard.headers.setdefault("Cache-Control", "private, no-store")
            guard.headers.setdefault("Vary", "Origin")
            return guard
        return _private_error({"error": "forbidden"}, status_code=403, vary_origin=True)

    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore
        if isinstance(repo, DBTeachingRepo):
            modules = repo.list_course_modules_for_owner(course_id, sub)
        else:
            modules = [asdict(m) if is_dataclass(m) else m for m in repo.list_course_modules_for_owner(course_id, sub)]
    except Exception:
        modules = []
    if str(unit_id) not in {str(m.get("unit_id")) for m in modules}:
        return _private_error({"error": "not_found"}, status_code=404, vary_origin=True)

    cells: list[dict] = []
    debug = (os.getenv("DEBUG_DELTA", "").strip() == "1")
    EPS = timedelta(seconds=1)
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore
        if isinstance(repo, DBTeachingRepo):
            helper_rows: list[dict[str, Any]] = []
            helper_ok = True
            avg_by_id: dict[str, float | None] = {}
            try:
                helper_rows = _load_unit_live_helper_rows(
                    repo,
                    owner_sub=sub,
                    course_id=course_id,
                    unit_id=unit_id,
                    updated_since_dt=db_lower_bound,
                    limit=int(limit),
                    offset=int(offset),
                )
                task_ids_by_student: dict[str, list[str]] = {}
                for row in helper_rows:
                    student_sub = str(row["student_sub"])
                    task_ids_by_student.setdefault(student_sub, []).append(str(row["task_id"]))
                latest_state_by_task = (
                    _load_latest_submission_state_by_task(repo, sub, course_id, task_ids_by_student)
                    if any(
                        row.get("score_raw") is None or row.get("score_max") is None
                        for row in helper_rows
                    )
                    else {}
                )
                latest_changed_by_pair = repo.list_unit_live_latest_changed_at_by_pairs(
                    owner_sub=sub,
                    course_id=course_id,
                    task_ids_by_student=task_ids_by_student,
                )
                submission_ids_by_student: dict[str, list[str]] = {}
                for row in helper_rows:
                    student_sub = str(row["student_sub"])
                    task_id = str(row["task_id"])
                    submission_id = (
                        latest_state_by_task.get((student_sub, task_id), {}).get("submission_id")
                        or row.get("submission_id")
                    )
                    if submission_id:
                        submission_ids_by_student.setdefault(student_sub, []).append(submission_id)
                avg_by_id = _load_average_scores_by_submission_id(repo, sub, submission_ids_by_student)
            except Exception as exc:
                logger.warning(
                    "Unit delta fallback: helper unavailable — %s",
                    exc,
                    extra={"course_id": course_id, "unit_id": unit_id},
                )
                helper_rows = []
                helper_ok = False

            if helper_ok:
                cells = _build_live_delta_cells(
                    helper_rows=helper_rows,
                    latest_state_by_task=latest_state_by_task,
                    avg_by_id=avg_by_id,
                    latest_changed_by_pair=latest_changed_by_pair,
                    original_updated_dt=original_updated_dt,
                    logger_obj=logger,
                    debug=logger.isEnabledFor(logging.DEBUG) or debug,
                    timestamp_provider=lambda: datetime.now(timezone.utc),
                    epsilon_seconds=1,
                )

            if not helper_ok:
                try:
                    fallback_rows = repo.list_unit_live_delta_fallback_rows(
                        owner_sub=sub,
                        course_id=course_id,
                        changed_since=db_lower_bound,
                        limit=int(limit),
                        offset=int(offset),
                    )
                except Exception:
                    fallback_rows = []
                for student_sub, task_id, changed_ts in fallback_rows:
                    try:
                        changed_dt = changed_ts.astimezone(timezone.utc)
                    except Exception:
                        changed_dt = datetime.now(timezone.utc)
                    include = changed_dt > (original_updated_dt - EPS)
                    if not include:
                        continue
                    emit_dt = (changed_dt + EPS) if changed_dt > original_updated_dt else (original_updated_dt + EPS)
                    changed_iso = emit_dt.isoformat(timespec="microseconds")
                    cells.append(
                        {
                            "student_sub": student_sub,
                            "task_id": task_id,
                            "has_submission": True,
                            "average_score": None,
                            "changed_at": changed_iso,
                        }
                    )

    except Exception as exc:
        logger.warning(
            "Unit delta query failed falling back to empty delta — %s",
            exc,
            extra={"course_id": course_id, "unit_id": unit_id},
        )

    if not cells:
        return Response(status_code=204, headers={"Cache-Control": "private, no-store", "Vary": "Origin"})

    payload = {"cells": cells}
    return _json_private(payload, status_code=200, vary_origin=True)


async def get_student_live_overview(request: Request, course_id: str, student_sub: str):
    """Return a teacher-facing live overview for one student across course units.

    Why:
        Teachers need the inverse perspective of the unit live matrix:
        `course x student x selected units`. The endpoint exposes only task-level
        status aggregates and keeps the richer submission detail on the existing
        latest-submission endpoint.
    """
    user, forbidden = _require_teacher(request)
    if forbidden:
        forbidden.headers.setdefault("Cache-Control", "private, no-store")
        forbidden.headers.setdefault("Vary", "Origin")
        return forbidden
    if not _is_uuid_like(course_id):
        return _private_error({"error": "bad_request", "detail": "invalid_uuid"}, status_code=400, vary_origin=True)

    raw_unit_ids = request.query_params.getlist("unit_ids") if "unit_ids" in request.query_params else None
    normalized_unit_ids: list[str] | None = None
    if raw_unit_ids is not None:
        normalized_unit_ids = []
        seen: set[str] = set()
        for raw in raw_unit_ids:
            trimmed = str(raw or "").strip()
            if not trimmed:
                continue
            if not _is_uuid_like(trimmed):
                return _private_error({"error": "bad_request", "detail": "invalid_uuid"}, status_code=400, vary_origin=True)
            canonical = _canonical_uuid(trimmed)
            if canonical in seen:
                continue
            seen.add(canonical)
            normalized_unit_ids.append(canonical)
        if len(normalized_unit_ids) > _current_max_unit_ids():
            return _private_error({"error": "bad_request", "detail": "too_many_unit_ids"}, status_code=400, vary_origin=True)

    sub = _current_sub(user)
    guard = teaching_guards._guard_course_owner(course_id, sub, repo_provider=_get_repo)
    if guard:
        if isinstance(guard, JSONResponse):
            guard.headers.setdefault("Cache-Control", "private, no-store")
            guard.headers.setdefault("Vary", "Origin")
            return guard
        return _private_error({"error": "forbidden"}, status_code=403, vary_origin=True)

    try:
        overview = _get_student_live_overview_service().build(
            course_id=course_id,
            owner_sub=sub,
            student_sub=student_sub,
            raw_unit_ids=normalized_unit_ids,
        )
    except ValueError as exc:
        return _private_error({"error": "bad_request", "detail": str(exc)}, status_code=400, vary_origin=True)
    except LookupError:
        return _private_error({"error": "not_found"}, status_code=404, vary_origin=True)

    names = _resolve_student_login_labels_runtime([str(student_sub)])
    display_name = names.get(str(student_sub), "Unbekannt")
    return _json_private(overview.to_dict(student_name=display_name), status_code=200, vary_origin=True)


async def get_latest_submission_detail(
    request: Request,
    course_id: str,
    unit_id: str,
    task_id: str,
    student_sub: str,
):
    """Latest submission detail for a student-task within a course-unit (owner-only).

    Intent:
        Allow teachers (course owners) to inspect the latest submission of a
        particular student for a given task in the selected unit, without
        exposing bulk content in the live matrix.

    Permissions:
        Caller must be a teacher and the owner of the course. Unit must belong
        to the course (best-effort verification). Returns 204 when no
        submission exists.
    """
    def _issue_h5p_review_token(
        *,
        owner_sub: str,
        course_id_in: str,
        task_id_in: str,
        student_sub_in: str,
        content_id_in: str,
    ) -> Optional[str]:
        """Return a short-lived, signed H5P review capability token.

        Why:
            The teacher review UI must load the student's H5P userState without
            exposing a generic "impersonate user" query parameter. We therefore
            issue a short-lived capability token that binds:
              - teacher (owner_sub),
              - student,
              - course,
              - task context,
              - H5P content id.

        Permissions:
            Caller must already have verified course ownership (teacher-only).
        """
        secret = (os.getenv("H5P_REVIEW_TOKEN_SECRET") or "").strip()
        if not secret:
            return None
        try:
            import base64
            import hashlib
            import hmac
            import json

            now = int(time.time())
            exp = now + 10 * 60
            payload_obj = {
                "teacher_sub": owner_sub,
                "student_sub": student_sub_in,
                "course_id": course_id_in,
                "task_id": task_id_in,
                "content_id": content_id_in,
                "exp": exp,
            }
            raw_json = json.dumps(payload_obj, separators=(",", ":"), sort_keys=True).encode("utf-8")
            payload_b64 = base64.urlsafe_b64encode(raw_json).decode("ascii").rstrip("=")
            sig = hmac.new(secret.encode("utf-8"), raw_json, hashlib.sha256).digest()
            sig_b64 = base64.urlsafe_b64encode(sig).decode("ascii").rstrip("=")
            return f"{payload_b64}.{sig_b64}"
        except Exception:
            return None

    repo = _get_repo()
    user, forbidden = _require_teacher(request)
    if forbidden:
        forbidden.headers.setdefault("Cache-Control", "private, no-store")
        forbidden.headers.setdefault("Vary", "Origin")
        return forbidden
    # Validate identifiers
    if not (_is_uuid_like(course_id) and _is_uuid_like(unit_id) and _is_uuid_like(task_id)):
        return _private_error({"error": "bad_request", "detail": "invalid_uuid"}, status_code=400, vary_origin=True)

    sub = _current_sub(user)
    # Ownership guard
    guard = teaching_guards._guard_course_owner(course_id, sub, repo_provider=_get_repo)
    if guard:
        if isinstance(guard, JSONResponse):
            guard.headers.setdefault("Cache-Control", "private, no-store")
            guard.headers.setdefault("Vary", "Origin")
            return guard
        return _private_error({"error": "forbidden"}, status_code=403, vary_origin=True)

    # Strict verification that task belongs to unit and unit is attached to course
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore
        modules = []
        if isinstance(repo, DBTeachingRepo):
            modules = repo.list_course_modules_for_owner(course_id, sub)
        else:
            modules = [asdict(m) if is_dataclass(m) else m for m in repo.list_course_modules_for_owner(course_id, sub)]
        attached_unit_ids = {str(m.get("unit_id")) for m in modules}
        if str(unit_id) not in attached_unit_ids:
            return _private_error({"error": "not_found"}, status_code=404, vary_origin=True)
    except Exception:
        # Fail closed on relation check errors
        return _private_error({"error": "not_found"}, status_code=404, vary_origin=True)

    # Query latest submission via SECURITY DEFINER helper (owner scope)
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore
        if isinstance(repo, DBTeachingRepo):
            from backend.web.db_cursor import open_repo_cursor

            dsn = getattr(repo, "_dsn", None)
            if dsn:
                with open_repo_cursor(dsn=dsn) as (_conn, cur):
                    cur.execute("select set_config('app.current_sub', %s, true)", (sub,))
                    # Enforce task ∈ unit via explicit relation check (DB)
                    cur.execute(
                        """
                        select t.kind::text,
                               t.instruction_md,
                               t.h5p_content_id::text
                          from public.unit_tasks t
                          join public.unit_sections s on s.id = t.section_id
                          join public.course_modules m on m.unit_id = s.unit_id
                         where m.course_id = %s
                           and s.unit_id = %s::uuid
                           and t.id = %s::uuid
                         limit 1
                        """,
                        (course_id, unit_id, task_id),
                    )
                    task_row = cur.fetchone()
                    if task_row is None:
                        return _private_error({"error": "not_found"}, status_code=404, vary_origin=True)
                    task_kind, task_instruction_md, task_h5p_content_id = task_row
                    try:
                        # SECURITY DEFINER helper encapsulates owner checks and RLS-aware access
                        cur.execute(
                            """
                            select id::text,
                                   task_id::text,
                                   student_sub::text,
                                   created_at,
                                   completed_at,
                                   kind,
                                   score_raw,
                                   score_max,
                                   text_body,
                                   mime_type,
                                   size_bytes,
                                   storage_key,
                                   feedback_md,
                                   analysis_json
                              from public.get_latest_submission_for_owner(%s, %s, %s, %s, %s)
                            """,
                            (sub, course_id, unit_id, task_id, student_sub),
                        )
                    except Exception as exc:
                        logger.warning("latest submission helper unavailable — %s", exc)
                        # Safe fallback under RLS with strict relation + owner scope; may still be restricted
                        cur.execute(
                            """
                            select id::text, task_id::text, student_sub::text, created_at, completed_at, kind,
                                   score_raw, score_max,
                                   text_body, mime_type, size_bytes, storage_key, feedback_md, analysis_json
                              from public.learning_submissions
                             where course_id = %s
                               and task_id = %s::uuid
                               and student_sub = %s
                             order by created_at desc, attempt_nr desc, id desc
                             limit 1
                            """,
                            (course_id, task_id, student_sub),
                        )
                    row = cur.fetchone()
                    if not row:
                        return Response(status_code=204, headers={"Cache-Control": "private, no-store", "Vary": "Origin"})
                    (
                        sid,
                        tid,
                        ssub,
                        created_at,
                        completed_at,
                        kind,
                        score_raw,
                        score_max,
                        text_body,
                        mime_type,
                        size_bytes,
                        storage_key,
                        feedback_md,
                        analysis_json,
                    ) = row
                    review_token = None
                    if str(kind or "") == "h5p" and isinstance(task_h5p_content_id, str) and task_h5p_content_id:
                        review_token = _issue_h5p_review_token(
                            owner_sub=str(sub),
                            course_id_in=str(course_id),
                            task_id_in=str(task_id),
                            student_sub_in=str(student_sub),
                            content_id_in=str(task_h5p_content_id),
                        )
                    payload = _build_latest_submission_payload(
                        course_id=str(course_id),
                        unit_id=str(unit_id),
                        file_href_builder=_teaching_submission_file_href,
                        sid=sid,
                        tid=tid,
                        ssub=ssub,
                        instruction_md=task_instruction_md,
                        created_at=created_at,
                        completed_at=completed_at,
                        kind=kind,
                        score_raw=score_raw,
                        score_max=score_max,
                        h5p_content_id=(task_h5p_content_id if str(task_kind or "") == "h5p" else None),
                        h5p_review_token=review_token,
                        text_body=text_body,
                        mime_type=mime_type,
                        size_bytes=size_bytes,
                        storage_key=storage_key,
                        feedback_md=feedback_md,
                        analysis_json=analysis_json,
                        include_files=True,
                    )
                    return _json_private(payload, status_code=200, vary_origin=True)
    except Exception as exc:
        logger.warning("latest submission query failed — %s", exc, extra={"course_id": course_id, "task_id": task_id})
        # Defensive fallback: when helper or extended query fails (e.g. during migrations),
        # try a minimal direct lookup that only relies on the core columns.
        try:
            from backend.teaching.repo_db import DBTeachingRepo  # type: ignore
            if isinstance(repo, DBTeachingRepo):
                from backend.web.db_cursor import open_repo_cursor

                dsn = getattr(repo, "_dsn", None)
                if dsn:
                    with open_repo_cursor(dsn=dsn) as (_conn, cur):
                        cur.execute("select set_config('app.current_sub', %s, true)", (sub,))
                        # Re-apply the strict task ∈ unit ∈ course relation check in the
                        # fallback path as well so mismatched unit/task combinations still
                        # fail with 404 instead of accidentally leaking submissions.
                        cur.execute(
                            """
                            select t.kind::text,
                                   t.instruction_md,
                                   t.h5p_content_id::text
                              from public.unit_tasks t
                              join public.unit_sections s on s.id = t.section_id
                              join public.course_modules m on m.unit_id = s.unit_id
                             where m.course_id = %s
                               and s.unit_id = %s::uuid
                               and t.id = %s::uuid
                             limit 1
                            """,
                            (course_id, unit_id, task_id),
                        )
                        task_row = cur.fetchone()
                        if task_row is None:
                            return _private_error(
                                {"error": "not_found"}, status_code=404, vary_origin=True
                            )
                        task_kind, task_instruction_md, task_h5p_content_id = task_row
                        cur.execute(
                            """
                            select id::text,
                                   task_id::text,
                                   student_sub::text,
                                   created_at,
                                   completed_at,
                                   kind,
                                   score_raw,
                                   score_max,
                                   text_body,
                                   mime_type,
                                   size_bytes,
                                   storage_key,
                                   feedback_md,
                                   analysis_json
                              from public.learning_submissions
                             where course_id = %s
                               and task_id = %s::uuid
                               and student_sub = %s
                             order by created_at desc, attempt_nr desc, id desc
                             limit 1
                            """,
                            (course_id, task_id, student_sub),
                        )
                        row = cur.fetchone()
                        if not row:
                            return Response(
                                status_code=204,
                                headers={"Cache-Control": "private, no-store", "Vary": "Origin"},
                            )
                        (
                            sid,
                            tid,
                            ssub,
                            created_at,
                            completed_at,
                            kind,
                            score_raw,
                            score_max,
                            text_body,
                            mime_type,
                            size_bytes,
                            storage_key,
                            feedback_md,
                            analysis_json,
                        ) = row
                        review_token = None
                        if str(kind or "") == "h5p" and isinstance(task_h5p_content_id, str) and task_h5p_content_id:
                            review_token = _issue_h5p_review_token(
                                owner_sub=str(sub),
                                course_id_in=str(course_id),
                                task_id_in=str(task_id),
                                student_sub_in=str(student_sub),
                                content_id_in=str(task_h5p_content_id),
                            )
                        payload = _build_latest_submission_payload(
                            course_id=str(course_id),
                            unit_id=str(unit_id),
                            file_href_builder=_teaching_submission_file_href,
                            sid=sid,
                            tid=tid,
                            ssub=ssub,
                            instruction_md=task_instruction_md,
                            created_at=created_at,
                            completed_at=completed_at,
                            kind=kind,
                            score_raw=score_raw,
                            score_max=score_max,
                            h5p_content_id=(task_h5p_content_id if str(task_kind or "") == "h5p" else None),
                            h5p_review_token=review_token,
                            text_body=text_body,
                            mime_type=mime_type,
                            size_bytes=size_bytes,
                            storage_key=storage_key,
                            feedback_md=feedback_md,
                            analysis_json=analysis_json,
                            include_files=False,
                        )
                        return _json_private(payload, status_code=200, vary_origin=True)
        except Exception:
            # Conservatively fall through to 204 when even the direct lookup fails.
            pass

    # Fallback when DB path not available or no submission was found
    return Response(status_code=204, headers={"Cache-Control": "private, no-store", "Vary": "Origin"})


async def get_teaching_submission_file(
    request: Request,
    course_id: str,
    unit_id: str,
    task_id: str,
    student_sub: str,
    disposition: Optional[str] = None,
):
    """Stream a teacher-visible submission file through a stable same-origin route."""

    user, forbidden = _require_teacher(request)
    if forbidden:
        forbidden.headers.setdefault("Cache-Control", "private, no-store")
        forbidden.headers.setdefault("Vary", "Origin")
        return forbidden

    if not (_is_uuid_like(course_id) and _is_uuid_like(unit_id) and _is_uuid_like(task_id)):
        return _private_error({"error": "bad_request", "detail": "invalid_uuid"}, status_code=400, vary_origin=True)

    normalized_disposition = (disposition or "inline").strip().lower()
    if normalized_disposition not in {"inline", "attachment"}:
        return _private_error({"error": "bad_request", "detail": "invalid_disposition"}, status_code=400, vary_origin=True)

    sub = _current_sub(user)
    guard = teaching_guards._guard_course_owner(course_id, sub, repo_provider=_get_repo)
    if guard:
        if isinstance(guard, JSONResponse):
            guard.headers.setdefault("Cache-Control", "private, no-store")
            guard.headers.setdefault("Vary", "Origin")
            return guard
        return _private_error({"error": "forbidden"}, status_code=403, vary_origin=True)

    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore
        repo = _get_repo()
        if not isinstance(repo, DBTeachingRepo):
            return _private_error({"error": "service_unavailable"}, status_code=503, vary_origin=True)

        from backend.web.db_cursor import open_repo_cursor

        dsn = getattr(repo, "_dsn", None)
        if not dsn:
            return _private_error({"error": "service_unavailable"}, status_code=503, vary_origin=True)

        with open_repo_cursor(dsn=dsn) as (_conn, cur):
            cur.execute("select set_config('app.current_sub', %s, true)", (sub,))
            cur.execute(
                """
                select exists(
                         select 1
                           from public.course_modules
                          where course_id = %s
                            and unit_id = %s::uuid
                     )
                """,
                (course_id, unit_id),
            )
            if not bool((cur.fetchone() or [False])[0]):
                return _private_error({"error": "not_found"}, status_code=404, vary_origin=True)
            cur.execute(
                """
                select s.mime_type,
                       s.size_bytes,
                       s.storage_key
                  from public.get_latest_submission_for_owner(%s, %s, %s, %s, %s) s
                 where s.id::text is not null
                 limit 1
                """,
                (sub, course_id, unit_id, task_id, student_sub),
            )
            row = cur.fetchone()
    except Exception:
        row = None

    if not row:
        return _private_error({"error": "not_found"}, status_code=404, vary_origin=True)

    mime_type, size_bytes_raw, storage_key = row
    mime_type = str(mime_type or "").strip().lower()
    storage_key = str(storage_key or "").strip()
    try:
        size_bytes = max(0, int(size_bytes_raw or 0))
    except (TypeError, ValueError):
        size_bytes = 0
    if not mime_type or not storage_key:
        return _private_error({"error": "not_found"}, status_code=404, vary_origin=True)

    try:
        from backend.web.routes import learning as learning_routes  # type: ignore

        adapter = getattr(learning_routes, "STORAGE_ADAPTER", STORAGE_ADAPTER)
    except Exception:
        adapter = STORAGE_ADAPTER

    if adapter is None or isinstance(adapter, NullStorageAdapter):
        return _private_error({"error": "service_unavailable"}, status_code=503, vary_origin=True)

    try:
        presigned = adapter.presign_download(  # type: ignore[union-attr]
            bucket=get_submissions_bucket(),
            key=storage_key,
            expires_in=60,
            disposition=normalized_disposition,
        )
    except Exception:
        presigned = None

    url = str((presigned or {}).get("url") or "").strip()
    headers = (presigned or {}).get("headers") if isinstance(presigned, dict) else None
    try:
        forward_headers = {str(k): str(v) for k, v in dict(headers or {}).items() if k and v}
    except Exception:
        forward_headers = None
    if not url:
        return _private_error({"error": "service_unavailable"}, status_code=503, vary_origin=True)

    downloader = _current_download_bytes_with_limit()
    body = await downloader(url=url, max_bytes=max(10 * 1024 * 1024, size_bytes), headers=forward_headers)
    if body is None:
        return _private_error({"error": "service_unavailable"}, status_code=503, vary_origin=True)

    filename = _safe_download_filename(os.path.basename(storage_key), "submission.bin")
    return Response(
        content=body,
        media_type=mime_type or "application/octet-stream",
        headers={
            "Cache-Control": "private, no-store",
            "Vary": "Origin",
            "Content-Disposition": f'{normalized_disposition}; filename="{filename}"',
        },
    )
