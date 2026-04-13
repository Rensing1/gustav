"""
Shared student material file visibility helpers for Learning API and SSR.

Why:
    Student-facing material lists, SSR previews, and the stable material file
    routes must all answer the same question: "May this student read this file
    material in this course?" This module centralises the DB lookup so those
    code paths do not drift apart.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import psycopg


class MaterialVisibilityLookupUnavailable(RuntimeError):
    """Raised when student material visibility cannot be resolved safely."""


@dataclass(frozen=True)
class StudentMaterialFileMetadata:
    """Visible file-material metadata returned under student scope."""

    material_id: str
    section_id: str
    unit_id: str
    mime_type: str
    size_bytes: int
    storage_key: str
    filename_original: str | None


def _set_student_scope(cur, *, repo: object, student_sub: str, course_id: str) -> None:
    set_current_sub = getattr(repo, "_set_current_sub", None)
    if callable(set_current_sub):
        set_current_sub(cur, student_sub)
    else:
        cur.execute("select set_config('app.current_sub', %s, true)", (student_sub,))

    set_current_course_id = getattr(repo, "_set_current_course_id", None)
    if callable(set_current_course_id):
        set_current_course_id(cur, course_id)
    else:
        cur.execute("select set_config('app.current_course_id', %s, true)", (course_id,))


def _coerce_row(row: tuple[object, ...] | None) -> StudentMaterialFileMetadata | None:
    if not row:
        return None
    try:
        material_id = str(row[0] or "").strip()
        section_id = str(row[1] or "").strip()
        unit_id = str(row[2] or "").strip()
        mime_type = str(row[3] or "").strip().lower()
        size_bytes = max(0, int(row[4] or 0))
        storage_key = str(row[5] or "").strip()
        filename_original = str(row[6]).strip() if row[6] is not None else None
    except Exception:
        return None
    if not (material_id and section_id and unit_id and mime_type and storage_key):
        return None
    return StudentMaterialFileMetadata(
        material_id=material_id,
        section_id=section_id,
        unit_id=unit_id,
        mime_type=mime_type,
        size_bytes=size_bytes,
        storage_key=storage_key,
        filename_original=filename_original,
    )


def _repo_dsn(repo: object) -> str:
    """Return the repo DSN or fail loudly when the learning DB is unavailable."""

    dsn = str(getattr(repo, "_dsn", "") or "").strip()
    if not dsn:
        raise MaterialVisibilityLookupUnavailable("repo_dsn_missing")
    return dsn


def load_student_material_file_metadata(
    *,
    repo: object,
    student_sub: str,
    course_id: str,
    material_id: str,
) -> StudentMaterialFileMetadata | None:
    """Return visible file-material metadata for one material under student scope."""

    rows = load_student_material_file_metadata_batch(
        repo=repo,
        student_sub=student_sub,
        course_id=course_id,
        material_ids=[material_id],
    )
    return rows.get(str(material_id))


def load_student_material_file_metadata_batch(
    *,
    repo: object,
    student_sub: str,
    course_id: str,
    material_ids: Iterable[str],
) -> dict[str, StudentMaterialFileMetadata]:
    """Return visible file-material metadata keyed by material id."""

    requested_ids = [str(material_id) for material_id in material_ids if str(material_id or "").strip()]
    if not (student_sub and course_id and requested_ids):
        return {}
    dsn = _repo_dsn(repo)

    out: dict[str, StudentMaterialFileMetadata] = {}
    try:
        with psycopg.connect(dsn) as conn:
            with conn.cursor() as cur:
                _set_student_scope(cur, repo=repo, student_sub=student_sub, course_id=course_id)
                cur.execute(
                    """
                    select visible.material_id::text,
                           visible.section_id::text,
                           visible.unit_id::text,
                           visible.mime_type,
                           visible.size_bytes,
                           visible.storage_key,
                           visible.filename_original
                      from public.get_material_file_metadata_batch_for_student(
                            %s,
                            %s::uuid,
                            %s::uuid[]
                      ) visible
                    """,
                    (student_sub, course_id, requested_ids),
                )
                for row in cur.fetchall() or []:
                    metadata = _coerce_row(row)
                    if metadata is not None:
                        out[metadata.material_id] = metadata
    except MaterialVisibilityLookupUnavailable:
        raise
    except Exception as exc:
        raise MaterialVisibilityLookupUnavailable("visibility_lookup_failed") from exc
    return out
