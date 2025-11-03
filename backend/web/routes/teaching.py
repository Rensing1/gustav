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
import os
import re
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple
import asyncio
from uuid import uuid4, UUID

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from pydantic.functional_validators import field_validator

from teaching.services.materials import MaterialFileSettings, MaterialsService
from teaching.services.tasks import TasksService
from teaching.storage import NullStorageAdapter, StorageAdapterProtocol
from .security import _is_same_origin
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
    hints_md: Optional[str] | None
    due_at: Optional[str] | None
    max_attempts: Optional[int] | None
    position: int
    created_at: str
    updated_at: str
    kind: str = "native"


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
        if body_md is not _UNSET:
            if mat.kind != "markdown":
                raise ValueError("invalid_body_md")
            if body_md is None or not isinstance(body_md, str):
                raise ValueError("invalid_body_md")
            mat.body_md = body_md
        if alt_text is not _UNSET:
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
        hints_md: str | None = None,
        due_at=None,
        max_attempts: int | None = None,
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
            hints_md=hints_md.strip() if isinstance(hints_md, str) and hints_md.strip() else None,
            due_at=due_iso,
            max_attempts=max_attempts,
            position=pos,
            created_at=now,
            updated_at=now,
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
        hints_md=_UNSET,
        due_at=_UNSET,
        max_attempts=_UNSET,
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
        if hints_md is not _UNSET:
            if hints_md is None:
                task.hints_md = None
            elif isinstance(hints_md, str):
                stripped = hints_md.strip()
                task.hints_md = stripped or None
        if due_at is not _UNSET:
            if due_at is None:
                task.due_at = None
            elif isinstance(due_at, datetime):
                task.due_at = due_at.astimezone(timezone.utc).isoformat()
            elif isinstance(due_at, str):
                task.due_at = due_at
        if max_attempts is not _UNSET:
            task.max_attempts = max_attempts
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
    from teaching.repo_db import DBTeachingRepo  # type: ignore
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

def _get_repo():  # pragma: no cover - simple accessor
    global _REPO
    if _REPO is None:
        _REPO = _build_default_repo()
    return _REPO

# Back-compat symbol used in tests: expose the actual instance for isinstance checks
REPO = _get_repo()

# Allow overriding the storage bucket via environment for deployments
_bucket = os.getenv("SUPABASE_STORAGE_BUCKET") or MaterialFileSettings().storage_bucket
MATERIAL_FILE_SETTINGS = MaterialFileSettings(storage_bucket=_bucket)
STORAGE_ADAPTER: StorageAdapterProtocol = NullStorageAdapter()

def _get_materials_service() -> MaterialsService:
    return MaterialsService(_get_repo(), settings=MATERIAL_FILE_SETTINGS)

def _get_tasks_service() -> TasksService:
    return TasksService(_get_repo())


def set_repo(repo) -> None:
    """Allow tests to swap the teaching repository implementation."""
    global _REPO
    _REPO = repo


def set_storage_adapter(adapter: StorageAdapterProtocol) -> None:
    """Allow tests to provide a storage adapter (e.g., fake or stub)."""
    global STORAGE_ADAPTER
    STORAGE_ADAPTER = adapter


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
        return None, _private_error({"error": "forbidden"}, status_code=403)
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
        return _private_error({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        repo = _get_repo()
        if isinstance(repo, DBTeachingRepo):
            if repo.unit_exists_for_author(unit_id, author_sub):
                return None
            exists = repo.unit_exists(unit_id)
            if exists is False:
                return _private_error({"error": "not_found"}, status_code=404)
            return _private_error({"error": "forbidden"}, status_code=403)
    except Exception:
        return _private_error({"error": "forbidden"}, status_code=403)
    # Fallback for in-memory repo
    repo = _get_repo()
    if hasattr(repo, "unit_exists_for_author") and repo.unit_exists_for_author(unit_id, author_sub):
        return None
    if hasattr(repo, "unit_exists") and not repo.unit_exists(unit_id):
        return _private_error({"error": "not_found"}, status_code=404)
    return _private_error({"error": "forbidden"}, status_code=403)


def _json_private(payload, *, status_code: int = 200, vary_origin: bool = False) -> JSONResponse:
    """Return a JSONResponse with cache disabled for shared caches and browsers.

    Rationale: Teaching endpoints expose user- and role-scoped data. To avoid
    accidental caching in proxies or browsers, respond with "private, no-store".
    """
    headers = {"Cache-Control": "private, no-store"}
    if vary_origin:
        headers["Vary"] = "Origin"
    return JSONResponse(content=payload, status_code=status_code, headers=headers)


def _private_error(payload: dict, *, status_code: int, vary_origin: bool = False) -> JSONResponse:
    """Return error JSON with private, no-store cache headers.

    Keep error responses out of shared caches to avoid leaking owner-scoped
    metadata via intermediary proxies or browser history.
    """
    headers = {"Cache-Control": "private, no-store"}
    if vary_origin:
        headers["Vary"] = "Origin"
    return JSONResponse(content=payload, status_code=status_code, headers=headers)


def _csrf_guard(request: Request) -> JSONResponse | None:
    """Enforce same-origin for browser write requests.

    Behavior:
        - In production or when STRICT_CSRF_TEACHING=true, require that either
          Origin or Referer is present AND same-origin. Missing or foreign
          headers result in 403 with detail=csrf_violation.
        - In non-strict modes, fall back to best-effort `_is_same_origin`,
          which permits requests without these headers (server-to-server calls).
    """
    import os

    prod_env = (os.getenv("GUSTAV_ENV", "dev") or "").lower() == "prod"
    strict_toggle = (os.getenv("STRICT_CSRF_TEACHING", "false") or "").lower() == "true"
    strict = prod_env or strict_toggle

    if strict:
        origin_present = (request.headers.get("origin") or request.headers.get("referer"))
        if not origin_present or (not _is_same_origin(request)):
            return _private_error({"error": "forbidden", "detail": "csrf_violation"}, status_code=403)
        return None

    if not _is_same_origin(request):
        return _private_error({"error": "forbidden", "detail": "csrf_violation"}, status_code=403)
    return None


def _require_strict_same_origin(request: Request) -> bool:
    """Return True only when a same-origin indicator is present and matches.

    Why:
        Owner-scoped write APIs must not accept cross-site browser requests.
        Requiring Origin/Referer eliminates the "no-header" ambiguity that
        `_is_same_origin` deliberately allows for non-browser clients.
    """
    origin_present = (request.headers.get("origin") or request.headers.get("referer"))
    if not origin_present:
        return False
    return _is_same_origin(request)


"""CSRF helper imported from .security"""


def _guard_course_owner(course_id: str, owner_sub: str):
    """Ensure caller owns the course, mapping to 404/403 appropriately."""
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        repo = _get_repo()
        if isinstance(repo, DBTeachingRepo):
            if repo.course_exists_for_owner(course_id, owner_sub):
                return None
            return _resp_non_owner_or_unknown(course_id, owner_sub)
    except Exception:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    repo = _get_repo()
    course = repo.get_course(course_id)
    if not course:
        return JSONResponse({"error": "not_found"}, status_code=404)
    if _teacher_id_of(course) != owner_sub:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    return None


# --- User directory adapter (mockable) ------------------------------------------

def resolve_student_names(subs: list[str]) -> dict[str, str]:
    """Resolve user IDs to display names via Keycloak directory (humanized).

    - Always attempt the directory call; on failure, fall back to "Unbekannt".
    - Humanize returned identifiers (emails/usernames) to "Vorname Nachname".
    - Never expose SUBs in the names returned by this function.
    """
    out: dict[str, str] = {}
    try:
        from identity_access import directory  # type: ignore
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
    repo = _get_repo()
    if _role_in(user, "teacher"):
        items = repo.list_courses_for_teacher(teacher_id=sub, limit=limit, offset=offset)
    else:
        items = repo.list_courses_for_student(student_id=sub, limit=limit, offset=offset)
    return _json_private([_serialize_course(c) for c in items], status_code=200)


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
    csrf = _csrf_guard(request)
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
        return JSONResponse({"error": "bad_request", "detail": "invalid_input"}, status_code=400)
    # Security: return private, no-store to prevent caching of owner-scoped data
    return _json_private(_serialize_course(course), status_code=201)


@teaching_router.get("/api/teaching/courses/{course_id}")
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
        return JSONResponse({"error": "forbidden"}, status_code=403)
    csrf = _csrf_guard(request)
    if csrf:
        return csrf
    # Validate path parameter format early to avoid unintended 500s
    if not _is_uuid_like(course_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_course_id"}, status_code=400)
    guard = _guard_course_owner(course_id, sub)
    if guard:
        return guard
    # Owner confirmed; fetch course and return
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        if isinstance(repo, DBTeachingRepo):
            # Use owner-scoped helper under RLS
            c = repo.get_course_for_owner(course_id, sub)
        else:
            c = repo.get_course(course_id)
    except Exception:
        c = repo.get_course(course_id)
    if not c:
        return JSONResponse({"error": "not_found"}, status_code=404)
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
    # Accept loose typing to avoid FastAPI 422 and map contract errors to 400
    module_ids: object | None = None


class ModuleSectionVisibilityPayload(BaseModel):
    # Accept loose typing to avoid FastAPI 422 and surface contract error codes.
    visible: object | None = None


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
    hints_md: object | None = None
    due_at: object | None = None
    max_attempts: object | None = None


class TaskUpdatePayload(BaseModel):
    instruction_md: object | None = None
    criteria: object | None = None
    hints_md: object | None = None
    due_at: object | None = None
    max_attempts: object | None = None


class TaskReorderPayload(BaseModel):
    task_ids: object | None = None


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
    repo = _get_repo()
    user = getattr(request.state, "user", None)
    sub = _current_sub(user)
    if not _role_in(user, "teacher"):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    updates = payload.model_dump(mode="python", exclude_unset=True)
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        if isinstance(repo, DBTeachingRepo):
            # Contract-aligned semantics: disambiguate 404 vs 403 prior to mutation
            if not repo.course_exists_for_owner(course_id, sub):
                ex = repo.course_exists(course_id)
                if ex is False:
                    return JSONResponse({"error": "not_found"}, status_code=404)
                return JSONResponse({"error": "forbidden"}, status_code=403)
            updated = repo.update_course_owned(
                course_id,
                sub,
                **updates,
            )
        else:
            course = repo.get_course(course_id)
            if not course:
                return JSONResponse({"error": "not_found"}, status_code=404)
            owner_id = course["teacher_id"] if isinstance(course, dict) else getattr(course, "teacher_id", None)
            if sub != owner_id:
                return JSONResponse({"error": "forbidden"}, status_code=403)
            updated = repo.update_course(
                course_id,
                **updates,
            )
    except ValueError:
        return JSONResponse({"error": "bad_request", "detail": "invalid_field"}, status_code=400)
    if not updated:
        # Should not normally happen after existence/ownership checks; keep conservative 403
        return JSONResponse({"error": "forbidden"}, status_code=403)
    # Consistent API response shape: explicit JSONResponse with status 200
    return JSONResponse(content=_serialize_course(updated), status_code=200)


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
    repo = _get_repo()
    user = getattr(request.state, "user", None)
    sub = _current_sub(user)
    if not _role_in(user, "teacher"):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    # CSRF defense-in-depth for browser clients
    csrf = _csrf_guard(request)
    if csrf:
        return csrf
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
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
    csrf = _csrf_guard(request)
    if csrf:
        return csrf
    limit = max(1, min(50, int(limit or 20)))
    offset = max(0, int(offset or 0))
    sub = _current_sub(user)
    try:
        units = _get_repo().list_units_for_author(author_id=sub, limit=limit, offset=offset)
    except Exception as exc:
        logger.warning("list_units failed for sub=%s err=%s", sub[-6:], exc.__class__.__name__)
        return JSONResponse({"error": "forbidden"}, status_code=403)
    return _json_private([_serialize_unit(u) for u in units], status_code=200)


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
    csrf = _csrf_guard(request)
    if csrf:
        return csrf
    sub = _current_sub(user)
    try:
        title = payload.title or ""
        unit = _get_repo().create_unit(title=title, summary=payload.summary, author_id=sub)
    except ValueError as exc:
        detail = str(exc)
        if detail in {"invalid_title", "invalid_summary"}:
            return JSONResponse({"error": "bad_request", "detail": detail}, status_code=400)
        return JSONResponse({"error": "bad_request"}, status_code=400)
    except PermissionError:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    return _json_private(_serialize_unit(unit), status_code=201)


@teaching_router.get("/api/teaching/units/{unit_id}")
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
    csrf = _csrf_guard(request)
    if csrf:
        return csrf
    if not _is_uuid_like(unit_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    sub = _current_sub(user)
    guard = _guard_unit_author(unit_id, sub)
    if guard:
        return guard
    # Author confirmed; fetch the unit via repo (DB or in-memory)
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        if isinstance(repo, DBTeachingRepo):
            u = repo.get_unit_for_author(unit_id, sub)
        else:
            u = repo.get_unit_for_author(unit_id, sub)
    except Exception:
        u = repo.get_unit_for_author(unit_id, sub)
    if not u:
        return JSONResponse({"error": "not_found"}, status_code=404)
    return _json_private(_serialize_unit(u), status_code=200)


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
    repo = _get_repo()
    user, error = _require_teacher(request)
    if error:
        return error
    csrf = _csrf_guard(request)
    if csrf:
        return csrf
    sub = _current_sub(user)
    guard = _guard_unit_author(unit_id, sub)
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
    repo = _get_repo()
    user, error = _require_teacher(request)
    if error:
        return error
    csrf = _csrf_guard(request)
    if csrf:
        return csrf
    sub = _current_sub(user)
    guard = _guard_unit_author(unit_id, sub)
    if guard:
        return guard
    try:
        deleted = repo.delete_unit_owned(unit_id, sub)
    except Exception:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    if not deleted:
        return JSONResponse({"error": "not_found"}, status_code=404)
    # No content but still enforce private, no-store to be explicit in proxies
    return Response(status_code=204, headers={"Cache-Control": "private, no-store"})


@teaching_router.get("/api/teaching/units/{unit_id}/sections")
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
    guard = _guard_unit_author(unit_id, sub)
    if guard:
        return guard
    try:
        items = _get_repo().list_sections_for_author(unit_id, sub)
    except Exception:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    return _json_private([_serialize_section(s) for s in items], status_code=200)


@teaching_router.post("/api/teaching/units/{unit_id}/sections")
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
    csrf = _csrf_guard(request)
    if csrf:
        return csrf
    sub = _current_sub(user)
    guard = _guard_unit_author(unit_id, sub)
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


@teaching_router.patch("/api/teaching/units/{unit_id}/sections/{section_id}")
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
    csrf = _csrf_guard(request)
    if csrf:
        return csrf
    if not _is_uuid_like(unit_id) or not _is_uuid_like(section_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_path_params"}, status_code=400)
    sub = _current_sub(user)
    guard = _guard_unit_author(unit_id, sub)
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


@teaching_router.delete("/api/teaching/units/{unit_id}/sections/{section_id}")
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
    csrf = _csrf_guard(request)
    if csrf:
        return csrf
    if not _is_uuid_like(unit_id) or not _is_uuid_like(section_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_path_params"}, status_code=400)
    sub = _current_sub(user)
    guard = _guard_unit_author(unit_id, sub)
    if guard:
        return guard
    deleted = repo.delete_section(unit_id, section_id, sub)
    if not deleted:
        return JSONResponse({"error": "not_found"}, status_code=404)
    return Response(status_code=204, headers={"Cache-Control": "private, no-store"})


@teaching_router.post("/api/teaching/units/{unit_id}/sections/reorder")
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
    csrf = _csrf_guard(request)
    if csrf:
        return csrf
    if not _is_uuid_like(unit_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    sub = _current_sub(user)
    # Security-first: verify authorship before deep payload validation to avoid error oracle
    guard = _guard_unit_author(unit_id, sub)
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


@teaching_router.get("/api/teaching/units/{unit_id}/sections/{section_id}/tasks")
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
    guard = _guard_unit_author(unit_id, sub)
    if guard:
        return guard
    try:
        items = _get_tasks_service().list_tasks(unit_id, section_id, sub)
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404)
    return _json_private([_serialize_task(t) for t in items], status_code=200)


@teaching_router.post("/api/teaching/units/{unit_id}/sections/{section_id}/tasks")
async def create_section_task(request: Request, unit_id: str, section_id: str, payload: TaskCreatePayload):
    """Create a task within a section (author only)."""

    user, error = _require_teacher(request)
    if error:
        return error
    csrf = _csrf_guard(request)
    if csrf:
        return csrf
    if not _is_uuid_like(unit_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    if not _is_uuid_like(section_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_section_id"}, status_code=400)
    sub = _current_sub(user)
    guard = _guard_unit_author(unit_id, sub)
    if guard:
        return guard
    try:
        task = _get_tasks_service().create_task(
            unit_id,
            section_id,
            sub,
            instruction_md=payload.instruction_md,
            criteria=payload.criteria,
            hints_md=payload.hints_md,
            due_at=payload.due_at,
            max_attempts=payload.max_attempts,
        )
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404)
    except ValueError as exc:
        detail = str(exc) or "invalid_input"
        if detail not in {
            "invalid_instruction_md",
            "invalid_criteria",
            "invalid_due_at",
            "invalid_max_attempts",
            "invalid_hints_md",
        }:
            detail = "invalid_input"
        return JSONResponse({"error": "bad_request", "detail": detail}, status_code=400)
    except PermissionError:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    return JSONResponse(content=_serialize_task(task), status_code=201)


@teaching_router.patch("/api/teaching/units/{unit_id}/sections/{section_id}/tasks/{task_id}")
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
    csrf = _csrf_guard(request)
    if csrf:
        return csrf
    if not _is_uuid_like(unit_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    if not _is_uuid_like(section_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_section_id"}, status_code=400)
    if not _is_uuid_like(task_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_task_id"}, status_code=400)
    sub = _current_sub(user)
    guard = _guard_unit_author(unit_id, sub)
    if guard:
        return guard
    raw_updates = payload.model_dump(mode="python", exclude_unset=True)
    if not raw_updates:
        return JSONResponse({"error": "bad_request", "detail": "empty_payload"}, status_code=400)
    kwargs: Dict[str, object] = {}
    if "instruction_md" in raw_updates:
        kwargs["instruction_md"] = raw_updates["instruction_md"]
    if "criteria" in raw_updates:
        kwargs["criteria"] = raw_updates["criteria"]
    if "hints_md" in raw_updates:
        kwargs["hints_md"] = raw_updates["hints_md"]
    if "due_at" in raw_updates:
        kwargs["due_at"] = raw_updates["due_at"]
    if "max_attempts" in raw_updates:
        kwargs["max_attempts"] = raw_updates["max_attempts"]
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
            "invalid_hints_md",
        }:
            detail = "invalid_input"
        return JSONResponse({"error": "bad_request", "detail": detail}, status_code=400)
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404)
    except PermissionError:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    return JSONResponse(content=_serialize_task(updated), status_code=200)


@teaching_router.delete("/api/teaching/units/{unit_id}/sections/{section_id}/tasks/{task_id}")
async def delete_section_task(request: Request, unit_id: str, section_id: str, task_id: str):
    """Delete a task and resequence positions."""

    user, error = _require_teacher(request)
    if error:
        return error
    csrf = _csrf_guard(request)
    if csrf:
        return csrf
    if not _is_uuid_like(unit_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    if not _is_uuid_like(section_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_section_id"}, status_code=400)
    if not _is_uuid_like(task_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_task_id"}, status_code=400)
    sub = _current_sub(user)
    guard = _guard_unit_author(unit_id, sub)
    if guard:
        return guard
    try:
        _get_tasks_service().delete_task(unit_id, section_id, task_id, sub)
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404)
    except PermissionError:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    return Response(status_code=204, headers={"Cache-Control": "private, no-store"})


@teaching_router.post("/api/teaching/units/{unit_id}/sections/{section_id}/tasks/reorder")
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
    csrf = _csrf_guard(request)
    if csrf:
        return csrf
    if not _is_uuid_like(unit_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    if not _is_uuid_like(section_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_section_id"}, status_code=400)
    sub = _current_sub(user)
    guard = _guard_unit_author(unit_id, sub)
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


@teaching_router.get("/api/teaching/units/{unit_id}/sections/{section_id}/materials")
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
    guard = _guard_unit_author(unit_id, sub)
    if guard:
        return guard
    try:
        items = _get_materials_service().list_markdown_materials(unit_id, section_id, sub)
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404)
    return _json_private([_serialize_material(m) for m in items], status_code=200)


@teaching_router.post("/api/teaching/units/{unit_id}/sections/{section_id}/materials")
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
    if not _is_uuid_like(unit_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    if not _is_uuid_like(section_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_section_id"}, status_code=400)
    sub = _current_sub(user)
    guard = _guard_unit_author(unit_id, sub)
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
    return JSONResponse(content=_serialize_material(material), status_code=201)


@teaching_router.patch("/api/teaching/units/{unit_id}/sections/{section_id}/materials/{material_id}")
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
    csrf = _csrf_guard(request)
    if csrf:
        return csrf
    if not _is_uuid_like(unit_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    if not _is_uuid_like(section_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_section_id"}, status_code=400)
    if not _is_uuid_like(material_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_material_id"}, status_code=400)
    sub = _current_sub(user)
    guard = _guard_unit_author(unit_id, sub)
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


@teaching_router.delete("/api/teaching/units/{unit_id}/sections/{section_id}/materials/{material_id}")
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
    csrf = _csrf_guard(request)
    if csrf:
        return csrf
    if not _is_uuid_like(unit_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    if not _is_uuid_like(section_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_section_id"}, status_code=400)
    if not _is_uuid_like(material_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_material_id"}, status_code=400)
    sub = _current_sub(user)
    guard = _guard_unit_author(unit_id, sub)
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
        try:
            STORAGE_ADAPTER.delete_object(
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


@teaching_router.post("/api/teaching/units/{unit_id}/sections/{section_id}/materials/upload-intents")
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
    csrf = _csrf_guard(request)
    if csrf:
        return csrf
    if not _is_uuid_like(unit_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    if not _is_uuid_like(section_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_section_id"}, status_code=400)
    sub = _current_sub(user)
    guard = _guard_unit_author(unit_id, sub)
    if guard:
        return guard
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


@teaching_router.post("/api/teaching/units/{unit_id}/sections/{section_id}/materials/finalize")
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
    csrf = _csrf_guard(request)
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
    guard = _guard_unit_author(unit_id, sub)
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


@teaching_router.get(
    "/api/teaching/units/{unit_id}/sections/{section_id}/materials/{material_id}/download-url"
)
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
    guard = _guard_unit_author(unit_id, sub)
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


@teaching_router.post("/api/teaching/units/{unit_id}/sections/{section_id}/materials/reorder")
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
    if not _is_uuid_like(unit_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    if not _is_uuid_like(section_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_section_id"}, status_code=400)
    sub = _current_sub(user)
    guard = _guard_unit_author(unit_id, sub)
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
        modules = _get_repo().list_course_modules_for_owner(course_id, sub)
    except Exception as exc:
        logger.warning("list_course_modules failed cid=%s err=%s", course_id[-6:], exc.__class__.__name__)
        return JSONResponse({"error": "forbidden"}, status_code=403)
    return JSONResponse(content=[_serialize_module(m) for m in modules], status_code=200)


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
        return JSONResponse({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    try:
        guard_course = _guard_course_owner(course_id, sub)
        if guard_course:
            return guard_course
        guard_unit = _guard_unit_author(unit_id, sub)
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
    repo = _get_repo()
    user, error = _require_teacher(request)
    if error:
        return error
    if not _is_uuid_like(course_id):
        return JSONResponse({"error": "bad_request", "detail": "invalid_course_id"}, status_code=400)
    sub = _current_sub(user)
    # Security-first: check ownership before deep payload validation to avoid error oracle
    guard = _guard_course_owner(course_id, sub)
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


@teaching_router.delete("/api/teaching/courses/{course_id}/modules/{module_id}")
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
    guard = _guard_course_owner(course_id, sub)
    if guard:
        return guard
    try:
        # CSRF guard for DELETE
        csrf = _csrf_guard(request)
        if csrf:
            return csrf
        deleted = _get_repo().delete_course_module_owned(course_id, module_id, sub)
    except PermissionError:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    if not deleted:
        return JSONResponse({"error": "not_found"}, status_code=404)
    return Response(status_code=204, headers={"Cache-Control": "private, no-store"})

@teaching_router.patch("/api/teaching/courses/{course_id}/modules/{module_id}/sections/{section_id}/visibility")
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

    # CSRF: In production or STRICT_CSRF_TEACHING=true, require explicit Origin/Referer
    # and same-origin; otherwise fall back to best-effort check.
    import os as _os
    _prod = (_os.getenv("GUSTAV_ENV", "dev") or "").lower() == "prod"
    _strict = _prod or ((_os.getenv("STRICT_CSRF_TEACHING", "false") or "").lower() == "true")
    if _strict:
        if not _require_strict_same_origin(request):
            return _private_error(
                {"error": "forbidden", "detail": "csrf_violation"},
                status_code=403,
                vary_origin=True,
            )
    else:
        if not _is_same_origin(request):
            return _private_error(
                {"error": "forbidden", "detail": "csrf_violation"},
                status_code=403,
                vary_origin=True,
            )

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
    guard = _guard_course_owner(course_id, sub)
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
        body = {"error": "not_found"}
        if detail:
            body["detail"] = detail
        return _private_error(body, status_code=404, vary_origin=True)
    except PermissionError:
        return _private_error({"error": "forbidden"}, status_code=403, vary_origin=True)
    return _json_private(record, status_code=200, vary_origin=True)


@teaching_router.get("/api/teaching/courses/{course_id}/modules/{module_id}/sections/releases")
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
    guard = _guard_course_owner(course_id, sub)
    if guard:
        if isinstance(guard, JSONResponse):
            guard.headers.setdefault("Cache-Control", "private, no-store")
            guard.headers.setdefault("Vary", "Origin")
            return guard
        return _private_error({"error": "forbidden"}, status_code=403, vary_origin=True)
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
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


@teaching_router.get("/api/teaching/courses/{course_id}/modules/{module_id}/sections")
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
    guard = _guard_course_owner(course_id, sub)
    if guard:
        if isinstance(guard, JSONResponse):
            guard.headers.setdefault("Cache-Control", "private, no-store")
            guard.headers.setdefault("Vary", "Origin")
            return guard
        return _private_error({"error": "forbidden"}, status_code=403, vary_origin=True)

    unit_id: str | None = None
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
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
        from teaching.repo_db import DBTeachingRepo  # type: ignore
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


def _serialize_section(s) -> dict:
    if is_dataclass(s):
        return asdict(s)
    if isinstance(s, dict):
        return s
    return {
        "id": getattr(s, "id", None),
        "unit_id": getattr(s, "unit_id", None),
        "title": getattr(s, "title", None),
        "position": getattr(s, "position", None),
        "created_at": getattr(s, "created_at", None),
        "updated_at": getattr(s, "updated_at", None),
    }


def _serialize_material(m) -> dict:
    if is_dataclass(m):
        return asdict(m)
    if isinstance(m, dict):
        return m
    return {
        "id": getattr(m, "id", None),
        "unit_id": getattr(m, "unit_id", None),
        "section_id": getattr(m, "section_id", None),
        "title": getattr(m, "title", None),
        "body_md": getattr(m, "body_md", None),
        "position": getattr(m, "position", None),
        "created_at": getattr(m, "created_at", None),
        "updated_at": getattr(m, "updated_at", None),
    }


def _serialize_task(t) -> dict:
    if is_dataclass(t):
        data = asdict(t)
    elif isinstance(t, dict):
        data = dict(t)
    else:
        data = {
            "id": getattr(t, "id", None),
            "unit_id": getattr(t, "unit_id", None),
            "section_id": getattr(t, "section_id", None),
            "instruction_md": getattr(t, "instruction_md", None),
            "criteria": getattr(t, "criteria", []),
            "hints_md": getattr(t, "hints_md", None),
            "due_at": getattr(t, "due_at", None),
            "max_attempts": getattr(t, "max_attempts", None),
            "position": getattr(t, "position", None),
            "created_at": getattr(t, "created_at", None),
            "updated_at": getattr(t, "updated_at", None),
        }
    data.setdefault("kind", "native")
    if data.get("criteria") is None:
        data["criteria"] = []
    return data


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
        return JSONResponse({"error": "not_found"}, status_code=404)
    try:
        ex = repo.course_exists(course_id)
    except Exception:
        ex = None
    if ex is False:
        # Deterministic contract: non-existent course -> 404
        return JSONResponse({"error": "not_found"}, status_code=404)
    return JSONResponse({"error": "forbidden"}, status_code=403)


@teaching_router.get("/api/teaching/courses/{course_id}/members")
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
        return JSONResponse({"error": "forbidden"}, status_code=403)
    limit = max(1, min(50, int(limit or 20)))
    offset = max(0, int(offset or 0))
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        repo = _get_repo()
        if isinstance(repo, DBTeachingRepo):
            if not repo.course_exists_for_owner(course_id, sub):
                return _resp_non_owner_or_unknown(course_id, sub)
            pairs = repo.list_members_for_owner(course_id, sub, limit=limit, offset=offset)
        else:
            # Fallback in-memory owner check
            course = repo.get_course(course_id)
            if not course:
                return JSONResponse({"error": "not_found"}, status_code=404)
            if _teacher_id_of(course) != sub:
                return JSONResponse({"error": "forbidden"}, status_code=403)
            pairs = repo.list_members(course_id, limit=limit, offset=offset)
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
    return _json_private(result, status_code=200)


class AddMember(BaseModel):
    # Keep optional to return 400 (not FastAPI 422) when missing/empty
    # Accept both contract key `student_sub` (preferred) and legacy/test key `sub`.
    student_sub: str | None = None
    sub: str | None = None
    name: str | None = None  # ignored by API, accepted for compatibility


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
    # Prefer the contract key; fall back to legacy `sub` for compatibility with older callers/tests.
    student_sub = getattr(payload, "student_sub", None) or getattr(payload, "sub", None)
    if not isinstance(student_sub, str) or not student_sub.strip():
        return JSONResponse({"error": "bad_request", "detail": "student_sub_required"}, status_code=400)
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
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
                return JSONResponse({"error": "not_found"}, status_code=404)
            if _teacher_id_of(course) != sub:
                return JSONResponse({"error": "forbidden"}, status_code=403)
            created = repo.add_member(course_id, student_sub.strip())
    except Exception:
        # Fail closed: do not attempt mutation without clear ownership/existence semantics
        return _resp_non_owner_or_unknown(course_id, sub)
    if created:
        return JSONResponse({}, status_code=201, headers={"Cache-Control": "private, no-store"})
    return Response(status_code=204, headers={"Cache-Control": "private, no-store"})


@teaching_router.delete("/api/teaching/courses/{course_id}/members/{student_sub}")
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
    csrf = _csrf_guard(request)
    if csrf:
        return csrf
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
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


@teaching_router.get("/api/teaching/courses/{course_id}/units/{unit_id}/submissions/summary")
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
    guard = _guard_course_owner(course_id, sub)
    if guard:
        if isinstance(guard, JSONResponse):
            guard.headers.setdefault("Cache-Control", "private, no-store")
            guard.headers.setdefault("Vary", "Origin")
            return guard
        return _private_error({"error": "forbidden"}, status_code=403, vary_origin=True)

    # Verify unit is attached to course for the owner
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        repo = _get_repo()
        if isinstance(repo, DBTeachingRepo):
            modules = repo.list_course_modules_for_owner(course_id, sub)
        else:
            modules = [asdict(m) if is_dataclass(m) else m for m in repo.list_course_modules_for_owner(course_id, sub)]
    except Exception:
        modules = []
    if str(unit_id) not in {str(m.get("unit_id")) for m in modules}:
        return _private_error({"error": "not_found"}, status_code=404, vary_origin=True)

    # Build task list across the unit in position order
    tasks: list[dict] = []
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
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
                    })
    except Exception:
        tasks = []

    rows_out: list[dict] = []
    if include_students:
        roster: list[tuple[str, str]] = []
        try:
            from teaching.repo_db import DBTeachingRepo  # type: ignore
            if isinstance(repo, DBTeachingRepo):
                roster = repo.list_members_for_owner(course_id, sub, limit=limit, offset=offset)
            else:
                members = repo.members.get(course_id, {})
                roster = sorted([(k, v) for k, v in members.items()], key=lambda kv: kv[1])
                roster = roster[offset: offset + limit]
        except Exception:
            roster = []
        member_subs = [sid for sid, _ in roster]
        names = resolve_student_names(member_subs)

        has_map: set[tuple[str, str]] = set()
        try:
            from teaching.repo_db import DBTeachingRepo  # type: ignore
            if isinstance(repo, DBTeachingRepo):
                import psycopg  # type: ignore
                dsn = getattr(repo, "_dsn", None)
                if dsn:
                    with psycopg.connect(dsn) as conn:
                        with conn.cursor() as cur:
                            cur.execute("select set_config('app.current_sub', %s, true)", (sub,))
                            try:
                                cur.execute(
                                    "select student_sub::text, task_id::text from public.get_unit_latest_submissions_for_owner(%s, %s, %s, %s, %s, %s)",
                                    (sub, course_id, unit_id, updated_since_dt, int(limit), int(offset)),
                                )
                                rows = cur.fetchall() or []
                                has_map = {(r[0], r[1]) for r in rows}
                            except Exception as exc:
                                logger.warning(
                                    "Unit summary fallback: helper get_unit_latest_submissions_for_owner unavailable — %s",
                                    exc,
                                    extra={"course_id": course_id, "unit_id": unit_id},
                                )
                                rows = []
                            if tasks and member_subs:
                                task_ids = [t["id"] for t in tasks]
                                if not rows:
                                    cur.execute(
                                        """
                                        select distinct student_sub::text, task_id::text
                                        from public.learning_submissions
                                        where course_id = %s
                                          and task_id = any(%s)
                                          and student_sub = any(%s)
                                        """,
                                        (course_id, task_ids, member_subs),
                                    )
                                    rows = cur.fetchall() or []
                                    has_map = {(r[0], r[1]) for r in rows}
                                if not has_map:
                                    for sid in member_subs:
                                        cur.execute("select set_config('app.current_sub', %s, true)", (sid,))
                                        cur.execute(
                                            """
                                            select distinct task_id::text
                                            from public.learning_submissions
                                            where course_id = %s
                                              and student_sub = %s
                                              and task_id = any(%s)
                                            """,
                                            (course_id, sid, task_ids),
                                        )
                                        for (tid,) in cur.fetchall() or []:
                                            has_map.add((sid, tid))
                                    cur.execute("select set_config('app.current_sub', %s, true)", (sub,))
        except Exception:
            has_map = set()

        for sid in member_subs:
            row = {
                "student": {"sub": sid, "name": names.get(sid, sid)},
                "tasks": [
                    {"task_id": t["id"], "has_submission": ((sid, t["id"]) in has_map)} for t in tasks
                ],
            }
            rows_out.append(row)

    payload = {"tasks": tasks, "rows": rows_out}
    # private + Vary: Origin per contract
    return _json_private(payload, status_code=200, vary_origin=True)


@teaching_router.get("/api/teaching/courses/{course_id}/units/{unit_id}/submissions/delta")
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
    guard = _guard_course_owner(course_id, sub)
    if guard:
        if isinstance(guard, JSONResponse):
            guard.headers.setdefault("Cache-Control", "private, no-store")
            guard.headers.setdefault("Vary", "Origin")
            return guard
        return _private_error({"error": "forbidden"}, status_code=403, vary_origin=True)

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
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
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        if isinstance(repo, DBTeachingRepo):
            import psycopg  # type: ignore

            dsn = getattr(repo, "_dsn", None)
            if dsn:
                with psycopg.connect(dsn) as conn:
                    with conn.cursor() as cur:
                        cur.execute("select set_config('app.current_sub', %s, true)", (sub,))
                        helper_ok = True
                        try:
                            cur.execute(
                                """
                                select student_sub::text, task_id::text, submission_id::text, created_at_iso, completed_at_iso
                                  from public.get_unit_latest_submissions_for_owner(%s, %s, %s, %s, %s, %s)
                                """,
                                (sub, course_id, unit_id, db_lower_bound, int(limit), int(offset)),
                            )
                            rows = cur.fetchall() or []
                        except Exception as exc:
                            logger.warning(
                                "Unit delta fallback: helper unavailable — %s",
                                exc,
                                extra={"course_id": course_id, "unit_id": unit_id},
                            )
                            rows = []
                            helper_ok = False
                        for student_sub, task_id, submission_id, created_iso, completed_iso in rows:
                            cur.execute(
                                """
                                select greatest(created_at, coalesce(completed_at, created_at))
                                  from public.learning_submissions
                                 where course_id = %s
                                   and task_id = %s::uuid
                                   and student_sub = %s
                                 order by created_at desc
                                 limit 1
                                """,
                                (course_id, task_id, student_sub),
                            )
                            ts_row = cur.fetchone()
                            if ts_row and ts_row[0] is not None:
                                changed_dt = ts_row[0].astimezone(timezone.utc)
                            else:
                                # fall back to helper-provided timestamps or now
                                fallback_iso = completed_iso or created_iso
                                if fallback_iso:
                                    try:
                                        changed_dt = datetime.fromisoformat(fallback_iso.replace("Z", "+00:00")).astimezone(timezone.utc)
                                    except Exception:
                                        changed_dt = datetime.now(timezone.utc)
                                else:
                                    changed_dt = datetime.now(timezone.utc)
                            changed_iso = changed_dt.isoformat(timespec="microseconds")
                            if logger.isEnabledFor(logging.DEBUG) or debug:
                                logger.debug(
                                    "delta-cell",
                                    extra={
                                        "student_sub": student_sub,
                                        "task_id": task_id,
                                        "changed_dt": changed_dt.isoformat(timespec="microseconds"),
                                        "original_updated": original_updated_dt.isoformat(timespec="microseconds"),
                                    },
                                )
                                if debug:
                                    print(
                                        "[DELTA] changed=",
                                        changed_dt.isoformat(timespec="microseconds"),
                                        " cursor=",
                                        original_updated_dt.isoformat(timespec="microseconds"),
                                        " db_lb=",
                                        db_lower_bound.isoformat(timespec="microseconds"),
                                    )
                            # Include changes after (cursor - EPS) to account for clock skew
                            include = changed_dt > (original_updated_dt - EPS)
                            if not include:
                                continue
                            # Emit a cursor strictly beyond the client's cursor when
                            # we include due to clock skew, otherwise use the DB time.
                            # Move the emitted cursor forward to avoid duplicates on the next poll.
                            emit_dt = (
                                (changed_dt + EPS) if changed_dt > original_updated_dt else (original_updated_dt + EPS)
                            )
                            cells.append(
                                {
                                    "student_sub": student_sub,
                                    "task_id": task_id,
                                    "has_submission": bool(submission_id),
                                    "changed_at": emit_dt.isoformat(timespec="microseconds"),
                                }
                            )

                        if not helper_ok:
                            # Fallback to bulk query when helper missing. Return a real timestamptz
                            # and format in Python to preserve microseconds precision consistently.
                            try:
                                cur.execute(
                                    """
                                    select distinct student_sub::text,
                                                   task_id::text,
                                                   greatest(created_at, coalesce(completed_at, created_at)) as changed_ts
                                      from public.learning_submissions
                                     where course_id = %s
                                       and greatest(created_at, coalesce(completed_at, created_at)) > %s
                                     order by changed_ts desc
                                     limit %s offset %s
                                    """,
                                    (course_id, db_lower_bound, int(limit), int(offset)),
                                )
                                fallback_rows = cur.fetchall() or []
                            except Exception:
                                fallback_rows = []
                            for student_sub, task_id, changed_ts in fallback_rows:
                                try:
                                    # Ensure UTC and microsecond precision
                                    changed_dt = changed_ts.astimezone(timezone.utc)
                                except Exception:
                                    changed_dt = datetime.now(timezone.utc)
                                include = changed_dt > (original_updated_dt - EPS)
                                if not include:
                                    continue
                                emit_dt = (
                                    (changed_dt + EPS) if changed_dt > original_updated_dt else (original_updated_dt + EPS)
                                )
                                changed_iso = emit_dt.isoformat(timespec="microseconds")
                                cells.append(
                                    {
                                        "student_sub": student_sub,
                                        "task_id": task_id,
                                        "has_submission": True,
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


@teaching_router.get(
    "/api/teaching/courses/{course_id}/units/{unit_id}/tasks/{task_id}/students/{student_sub}/submissions/latest"
)
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
    guard = _guard_course_owner(course_id, sub)
    if guard:
        if isinstance(guard, JSONResponse):
            guard.headers.setdefault("Cache-Control", "private, no-store")
            guard.headers.setdefault("Vary", "Origin")
            return guard
        return _private_error({"error": "forbidden"}, status_code=403, vary_origin=True)

    # Strict verification that task belongs to unit and unit is attached to course
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
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
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        if isinstance(repo, DBTeachingRepo):
            import psycopg  # type: ignore

            dsn = getattr(repo, "_dsn", None)
            if dsn:
                with psycopg.connect(dsn) as conn:
                    with conn.cursor() as cur:
                        cur.execute("select set_config('app.current_sub', %s, true)", (sub,))
                        # Enforce task ∈ unit via explicit relation check (DB)
                        cur.execute(
                            """
                            select 1
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
                        if cur.fetchone() is None:
                            return _private_error({"error": "not_found"}, status_code=404, vary_origin=True)
                        helper_ok = True
                        try:
                            cur.execute(
                                """
                                select id::text, task_id::text, student_sub::text, created_at, completed_at, kind, text_body, mime_type, size_bytes, storage_key
                                  from public.get_latest_submission_for_owner(%s, %s, %s, %s, %s)
                                """,
                                (sub, course_id, unit_id, task_id, student_sub),
                            )
                        except Exception as exc:
                            logger.warning("latest submission helper unavailable — %s", exc)
                            helper_ok = False
                            # Safe fallback under RLS with strict relation + owner scope
                            cur.execute(
                                """
                                select id::text, task_id::text, student_sub::text, created_at, completed_at, kind, text_body, mime_type, size_bytes, storage_key
                                  from public.learning_submissions
                                 where course_id = %s
                                   and task_id = %s::uuid
                                   and student_sub = %s
                                 order by created_at desc
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
                            text_body,
                            mime_type,
                            size_bytes,
                            storage_key,
                        ) = row
                        def_kind = str(kind or "text")
                        # Derive a more specific kind for PDFs if possible
                        if def_kind == "file" and isinstance(mime_type, str) and "pdf" in mime_type.lower():
                            def_kind = "pdf"
                        payload: dict[str, Any] = {
                            "id": str(sid),
                            "task_id": str(tid),
                            "student_sub": str(ssub),
                            "created_at": created_at.astimezone(timezone.utc).isoformat(),
                            "completed_at": (completed_at.astimezone(timezone.utc).isoformat() if completed_at else None),
                            "kind": def_kind,
                        }
                        if def_kind == "text" and isinstance(text_body, str) and text_body:
                            # Keep it simple; truncation for safety
                            payload["text_body"] = text_body[:1000]
                        return _json_private(payload, status_code=200, vary_origin=True)
    except Exception as exc:
        logger.warning("latest submission query failed — %s", exc, extra={"course_id": course_id, "task_id": task_id})

    # Fallback when DB path not available
    return Response(status_code=204, headers={"Cache-Control": "private, no-store", "Vary": "Origin"})
