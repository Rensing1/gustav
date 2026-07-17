"""Explicit in-memory test repository for Teaching routes.

Why:
    The production Teaching API uses the database-backed repository. Tests
    need a deterministic test double that mirrors the same public repository
    methods without importing FastAPI route handlers.

Responsibility:
    Keep in-memory Teaching state and simple validation rules only. HTTP
    authentication, authorization guards, storage adapters and response shaping
    stay in dedicated route or service modules.
"""

from __future__ import annotations

import sys as _sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple
from uuid import uuid4


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


class InMemoryTeachingRepo:
    def check_readiness(self) -> None:
        """Treat an explicitly injected in-memory test double as ready."""

        return None

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


_Repo = InMemoryTeachingRepo
