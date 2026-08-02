"""Pydantic request payload models for Teaching route adapters.

Why:
    The Teaching route hotspot should own HTTP orchestration, not every payload
    model. Keeping these models here lets split routers reuse the same request
    contracts without importing more implementation detail from `teaching.py`.
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from pydantic.functional_validators import field_validator


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


class CourseUpdate(BaseModel):
    # Accept raw strings (including empty) and validate in handler to return 400.
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
    # Accept loose typing to avoid FastAPI 422 and map contract errors to 400.
    module_ids: object | None = None


class ModuleSectionVisibilityPayload(BaseModel):
    # Accept loose typing to avoid FastAPI 422 and surface contract error codes.
    visible: object | None = None


class UnitPhaseCreatePayload(BaseModel):
    # Accept any length; enforce 1..200 in handler to return 400 (not 422).
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
    # Accept any length; enforce 1..200 in handler to return 400 (not 422).
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
    # Use loose typing to avoid FastAPI 422, then validate type manually.
    phase_ids: object | None = None


class UnitModuleCreatePayload(BaseModel):
    # Accept raw strings (including empty) and validate in handler to return 400.
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
    # Accept any length; enforce 1..200 in handler to return 400 (not 422).
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
    # Use loose typing to avoid FastAPI 422, then validate type manually.
    module_ids: object | None = None


class UnitModuleEdgePayload(BaseModel):
    # Accept raw strings (including empty) and validate in handler to return 400.
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


class SectionCreatePayload(BaseModel):
    # Accept any length; enforce 1..200 in handler to return 400 (not 422).
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
    # Accept any length; enforce 1..200 in handler to return 400 (not 422).
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
    # Use loose typing to avoid FastAPI 422, then validate type manually.
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
    # Do not enforce max_length here to avoid FastAPI 422; service maps to 400 invalid_alt_text.
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
    dialog: object | None = None


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
    dialog: object | None = None


class TaskReorderPayload(BaseModel):
    task_ids: object | None = None


class AddMember(BaseModel):
    # Keep optional to return 400 (not FastAPI 422) when missing/empty.
    # Accept both contract key `student_sub` (preferred) and legacy/test key `sub`.
    student_sub: str | None = None
    sub: str | None = None
    name: str | None = None  # ignored by API, accepted for compatibility


__all__ = [
    "AddMember",
    "CourseCreate",
    "CourseModuleCreatePayload",
    "CourseModuleReorderPayload",
    "CourseUpdate",
    "MaterialCreatePayload",
    "MaterialFinalizePayload",
    "MaterialReorderPayload",
    "MaterialUpdatePayload",
    "MaterialUploadIntentPayload",
    "ModuleSectionVisibilityPayload",
    "SectionCreatePayload",
    "SectionReorderPayload",
    "SectionUpdatePayload",
    "TaskCreatePayload",
    "TaskReorderPayload",
    "TaskUpdatePayload",
    "UnitCreatePayload",
    "UnitModuleCreatePayload",
    "UnitModuleEdgePayload",
    "UnitModuleReorderPayload",
    "UnitModuleUpdatePayload",
    "UnitPhaseCreatePayload",
    "UnitPhaseReorderPayload",
    "UnitPhaseUpdatePayload",
    "UnitUpdatePayload",
]
