"""Row mapping helpers for the Teaching Postgres repository.

Why:
    DBTeachingRepo should orchestrate queries and RLS-aware access. Converting
    selected database rows into plain dictionaries is pure mapping logic and can
    live in a small, DB-free module that is easy to test directly.
"""

from __future__ import annotations

from typing import Any


MATERIAL_COLUMNS_SQL = """
    id::text,
    unit_id::text,
    section_id::text,
    title,
    body_md,
    position,
    kind,
    storage_key,
    filename_original,
    mime_type,
    size_bytes,
    sha256,
    alt_text,
    to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
    to_char(updated_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
"""


def material_row_to_dict(row: tuple) -> dict[str, Any]:
    """Map a unit material SQL row to the API-facing material dictionary."""

    return {
        "id": row[0],
        "unit_id": row[1],
        "section_id": row[2],
        "title": row[3],
        "body_md": row[4],
        "position": int(row[5]) if row[5] is not None else None,
        "kind": row[6],
        "storage_key": row[7],
        "filename_original": row[8],
        "mime_type": row[9],
        "size_bytes": int(row[10]) if row[10] is not None else None,
        "sha256": row[11],
        "alt_text": row[12],
        "created_at": row[13],
        "updated_at": row[14],
    }


TASK_COLUMNS_SQL = """
    id::text,
    unit_id::text,
    section_id::text,
    instruction_md,
    criteria,
    teacher_context_md,
    case
      when due_at is null then null
      else to_char(due_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
    end as due_at_iso,
    max_attempts,
    position,
    to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
    to_char(updated_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
    kind,
    h5p_content_id,
    h5p_display_options,
    model_solution_md
"""


def task_row_to_dict(row: tuple) -> dict[str, Any]:
    """Map a unit task SQL row to the API-facing task dictionary."""

    kind = str(row[11] or "native")
    h5p_content_id = row[12]
    h5p_display_options = row[13] or {}
    h5p = None
    visual = None
    scratch = None
    calliope = None
    filius = None
    if kind == "h5p":
        h5p = {"content_id": h5p_content_id, "display_options": dict(h5p_display_options)}
    elif kind == "visual":
        visual = {}
    elif kind == "scratch":
        scratch = {}
    elif kind == "calliope":
        calliope = {}
    elif kind == "filius":
        filius = {}
    return {
        "id": row[0],
        "unit_id": row[1],
        "section_id": row[2],
        "instruction_md": row[3],
        "criteria": list(row[4] or []),
        "teacher_context_md": row[5],
        "model_solution_md": row[14] if len(row) > 14 else None,
        "due_at": row[6],
        "max_attempts": int(row[7]) if row[7] is not None else None,
        "position": int(row[8]) if row[8] is not None else None,
        "created_at": row[9],
        "updated_at": row[10],
        "kind": kind,
        "h5p": h5p,
        "visual": visual,
        "scratch": scratch,
        "calliope": calliope,
        "filius": filius,
        "dialog": None,
    }


def compute_average_score_from_analysis(analysis: object) -> float | None:
    """Compute a 0..10 criteria average from a submission analysis payload."""

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
        normalized.append(max(0.0, min(10.0, scaled)))

    if not normalized:
        return None
    return sum(normalized) / len(normalized)
