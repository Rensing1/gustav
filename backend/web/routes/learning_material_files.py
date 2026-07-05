"""Learner material-file enrichment helpers.

Why:
    Learning routes and SSR payloads both need to expose stable same-origin
    URLs only for material files that are visible to the current student. This
    module keeps that visibility enrichment out of the Learning route hotspot
    while preserving the existing route contracts.
"""

from __future__ import annotations

import importlib
import sys as _sys
from typing import Any
from urllib.parse import quote as _quote
from uuid import UUID

from backend.web.material_file_access import (
    StudentMaterialFileMetadata,
    load_student_material_file_metadata,
    load_student_material_file_metadata_batch,
)


def _learning_module():
    module = _sys.modules.get("backend.web.routes.learning")
    if module is None:  # pragma: no cover - defensive import fallback
        module = importlib.import_module("backend.web.routes.learning")
    return module


def _get_repo():
    """Resolve the active Learning repo provider after reloads or monkeypatches."""

    return _learning_module()._get_repo()


def _is_uuid_like(value: object) -> bool:
    try:
        UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        return False
    return True


def material_file_href(*, course_id: str, material_id: str, disposition: str) -> str:
    """Return a stable same-origin file URL for a learner-visible material."""

    return (
        f"/api/learning/courses/{_quote(str(course_id), safe='')}/materials/"
        f"{_quote(str(material_id), safe='')}/file?disposition={_quote(str(disposition), safe='')}"
    )


def resolve_student_material_file_url(
    *,
    student_sub: str,
    course_id: str,
    material_id: str,
) -> str | None:
    if not (student_sub and _is_uuid_like(course_id) and _is_uuid_like(material_id)):
        return None
    repo = _get_repo()
    try:
        metadata = load_student_material_file_metadata(
            repo=repo,
            student_sub=student_sub,
            course_id=str(course_id),
            material_id=str(material_id),
        )
    except Exception:
        return None
    if metadata is None:
        return None
    return material_file_href(course_id=course_id, material_id=material_id, disposition="inline")


def load_visible_material_file_metadata(
    *,
    student_sub: str,
    course_id: str,
    material_ids: list[str],
) -> dict[str, StudentMaterialFileMetadata]:
    """Load visible file-material metadata for a student with one DB connection."""

    valid_material_ids = [str(material_id) for material_id in material_ids if _is_uuid_like(material_id)]
    if not (student_sub and _is_uuid_like(course_id) and valid_material_ids):
        return {}

    repo = _get_repo()
    try:
        return load_student_material_file_metadata_batch(
            repo=repo,
            student_sub=student_sub,
            course_id=str(course_id),
            material_ids=valid_material_ids,
        )
    except Exception:
        return {}


def resolve_student_modular_material_file_url(
    *,
    student_sub: str,
    course_id: str,
    material_id: str,
) -> str | None:
    return resolve_student_material_file_url(
        student_sub=student_sub,
        course_id=course_id,
        material_id=material_id,
    )


def attach_section_material_files(
    *,
    student_sub: str,
    course_id: str,
    sections: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    material_ids = [
        str(material.get("id") or "")
        for section in sections
        for material in (section.get("materials") or [])
        if isinstance(section, dict) and isinstance(material, dict) and material.get("kind") == "file"
    ]
    material_rows = load_visible_material_file_metadata(
        student_sub=student_sub,
        course_id=course_id,
        material_ids=material_ids,
    )
    enriched: list[dict[str, Any]] = []
    for section in sections:
        payload = dict(section)
        materials = []
        for material in payload.get("materials") or []:
            material_payload = dict(material)
            if material_payload.get("kind") == "file":
                material_id = str(material_payload.get("id") or "")
                material_payload["file_url"] = (
                    material_file_href(course_id=course_id, material_id=material_id, disposition="inline")
                    if material_id in material_rows
                    else None
                )
            else:
                material_payload["file_url"] = None
            materials.append(material_payload)
        payload["materials"] = materials
        enriched.append(payload)
    return enriched


def attach_modular_material_files(
    *,
    student_sub: str,
    course_id: str,
    unit_id: str,
    module_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    # Unit and module ids are part of the legacy helper signature. Visibility is
    # resolved by material id and course membership inside the DB helper.
    _ = (unit_id, module_id)

    out = dict(payload)
    material_rows = load_visible_material_file_metadata(
        student_sub=student_sub,
        course_id=course_id,
        material_ids=[
            str(material.get("id") or "")
            for material in (out.get("materials") or [])
            if isinstance(material, dict) and material.get("kind") == "file"
        ],
    )
    materials = []
    for material in out.get("materials") or []:
        material_payload = dict(material)
        if material_payload.get("kind") == "file":
            material_id = str(material_payload.get("id") or "")
            material_payload["file_url"] = (
                material_file_href(course_id=course_id, material_id=material_id, disposition="inline")
                if material_id in material_rows
                else None
            )
        else:
            material_payload["file_url"] = None
        materials.append(material_payload)
    out["materials"] = materials
    return out
