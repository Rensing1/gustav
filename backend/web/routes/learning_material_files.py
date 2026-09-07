"""Learner material-file enrichment helpers.

Why:
    Learning routes and SSR payloads both need to expose stable same-origin
    URLs only for material files that are visible to the current student. This
    module keeps that visibility enrichment out of the Learning route hotspot
    while preserving the existing route contracts.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote as _quote
from uuid import UUID

from backend.web.material_file_access import (
    StudentMaterialAssetMetadata,
    load_student_material_asset_metadata_batch,
)


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


def material_simulation_href(*, course_id: str, material_id: str) -> str:
    """Return the stable same-origin sandboxed simulation URL."""
    return (
        f"/api/learning/courses/{_quote(str(course_id), safe='')}/materials/"
        f"{_quote(str(material_id), safe='')}/simulation"
    )


def load_visible_material_asset_metadata(
    *,
    student_sub: str,
    course_id: str,
    material_ids: list[str],
    repo: object,
) -> dict[str, StudentMaterialAssetMetadata]:
    """Load visible stored-material metadata with one fail-closed DB lookup."""

    valid_material_ids = [
        str(material_id) for material_id in material_ids if _is_uuid_like(material_id)
    ]
    if not (student_sub and _is_uuid_like(course_id) and valid_material_ids):
        return {}
    try:
        return load_student_material_asset_metadata_batch(
            repo=repo,
            student_sub=student_sub,
            course_id=str(course_id),
            material_ids=valid_material_ids,
        )
    except Exception:
        return {}


def _attach_material_urls(
    *, course_id: str, materials: list[dict], material_rows: dict[str, StudentMaterialAssetMetadata]
) -> list[dict]:
    """Copy material rows and expose same-origin URLs only for confirmed asset kinds."""
    enriched = []
    for material in materials or []:
        material_payload = dict(material)
        if material_payload.get("kind") == "file":
            material_id = str(material_payload.get("id") or "")
            row = material_rows.get(material_id)
            material_payload["file_url"] = (
                material_file_href(
                    course_id=course_id, material_id=material_id, disposition="inline"
                )
                if row is not None and row.kind == "file"
                else None
            )
        else:
            material_payload["file_url"] = None
        if material_payload.get("kind") == "simulation":
            material_id = str(material_payload.get("id") or "")
            row = material_rows.get(material_id)
            material_payload["simulation_url"] = (
                material_simulation_href(course_id=course_id, material_id=material_id)
                if row is not None and row.kind == "simulation"
                else None
            )
        else:
            material_payload["simulation_url"] = None
        enriched.append(material_payload)
    return enriched


def attach_section_material_files(
    *, repo: object, student_sub: str, course_id: str, sections: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Enrich authorized section lists using the same explicitly supplied DB adapter."""
    material_rows = load_visible_material_asset_metadata(
        repo=repo,
        student_sub=student_sub,
        course_id=course_id,
        material_ids=[
            str(material.get("id") or "")
            for section in sections
            for material in (section.get("materials") or [])
            if isinstance(section, dict)
            and isinstance(material, dict)
            and material.get("kind") in {"file", "simulation"}
        ],
    )
    enriched = []
    for section in sections:
        payload = dict(section)
        payload["materials"] = _attach_material_urls(
            course_id=course_id,
            materials=payload.get("materials") or [],
            material_rows=material_rows,
        )
        enriched.append(payload)
    return enriched


def attach_modular_material_files(
    *, repo: object, student_sub: str, course_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    """Enrich authorized module contents using the same explicitly supplied repository.

    The additional visibility query is fail-closed: unavailable or mismatched
    metadata produces no URL. Neither the module payload nor its rows are mutated.
    Streaming endpoints must still recheck access when a URL is requested.
    """
    out = dict(payload)
    material_rows = load_visible_material_asset_metadata(
        repo=repo,
        student_sub=student_sub,
        course_id=course_id,
        material_ids=[
            str(material.get("id") or "")
            for material in (out.get("materials") or [])
            if isinstance(material, dict) and material.get("kind") in {"file", "simulation"}
        ],
    )
    out["materials"] = _attach_material_urls(
        course_id=course_id, materials=out.get("materials") or [], material_rows=material_rows
    )
    return out
