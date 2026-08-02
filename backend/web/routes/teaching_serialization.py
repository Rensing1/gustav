"""Response serialization helpers for Teaching route adapters."""

from __future__ import annotations

import logging
import hashlib
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone, timedelta
from typing import Any, Callable


logger = logging.getLogger("gustav.web.teaching.serialization")


def _serialize_task(t) -> dict:
    """Serialize a task object into the API response shape.

    The persistence layer still exposes some legacy flat columns such as
    `h5p_content_id`. The API contract uses nested task-kind objects, so this
    adapter normalizes both DB rows and in-memory task objects.
    """

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
            "teacher_context_md": getattr(t, "teacher_context_md", None),
            "due_at": getattr(t, "due_at", None),
            "max_attempts": getattr(t, "max_attempts", None),
            "position": getattr(t, "position", None),
            "created_at": getattr(t, "created_at", None),
            "updated_at": getattr(t, "updated_at", None),
        }
    kind = str(data.get("kind") or "native")
    data["kind"] = kind
    if data.get("criteria") is None:
        data["criteria"] = []
    # Normalize optional task kind configs to match the OpenAPI contract.
    if kind == "h5p":
        h5p_cfg = data.get("h5p")
        if not isinstance(h5p_cfg, dict):
            content_id = data.get("h5p_content_id")
            display_options = data.get("h5p_display_options") or {}
            if not isinstance(display_options, dict):
                display_options = {}
            h5p_cfg = {"content_id": content_id, "display_options": display_options}
        data["h5p"] = h5p_cfg
        data["visual"] = None
        data["scratch"] = None
        data["calliope"] = None
        data["filius"] = None
        data["dialog"] = None
    elif kind == "visual":
        visual_cfg = data.get("visual")
        data["visual"] = visual_cfg if isinstance(visual_cfg, dict) else {}
        data["h5p"] = None
        data["scratch"] = None
        data["calliope"] = None
        data["filius"] = None
        data["dialog"] = None
    elif kind == "scratch":
        scratch_cfg = data.get("scratch")
        data["scratch"] = scratch_cfg if isinstance(scratch_cfg, dict) else {}
        data["h5p"] = None
        data["visual"] = None
        data["calliope"] = None
        data["filius"] = None
        data["dialog"] = None
    elif kind == "calliope":
        calliope_cfg = data.get("calliope")
        data["calliope"] = calliope_cfg if isinstance(calliope_cfg, dict) else {}
        data["h5p"] = None
        data["visual"] = None
        data["scratch"] = None
        data["filius"] = None
        data["dialog"] = None
    elif kind == "filius":
        filius_cfg = data.get("filius")
        data["filius"] = filius_cfg if isinstance(filius_cfg, dict) else {}
        data["h5p"] = None
        data["visual"] = None
        data["scratch"] = None
        data["calliope"] = None
        data["dialog"] = None
    elif kind == "dialog":
        dialog_cfg = data.get("dialog")
        data["dialog"] = dialog_cfg if isinstance(dialog_cfg, dict) else None
        data["h5p"] = None
        data["visual"] = None
        data["scratch"] = None
        data["calliope"] = None
        data["filius"] = None
    else:
        data.setdefault("h5p", None)
        data.setdefault("visual", None)
        data.setdefault("scratch", None)
        data.setdefault("calliope", None)
        data.setdefault("filius", None)
        data.setdefault("dialog", None)
    # Do not expose internal storage columns; the API uses nested objects.
    data.pop("h5p_content_id", None)
    data.pop("h5p_display_options", None)
    return data


def _serialize_course(c) -> dict:
    if is_dataclass(c):
        return asdict(c)
    if isinstance(c, dict):
        return c
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
        "unit_type": getattr(u, "unit_type", None),
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


def _normalise_analysis_json(raw: Any) -> dict[str, Any] | None:
    """Normalise persisted analysis payloads into criteria.v1/v2 response shapes."""

    if not isinstance(raw, dict):
        return None

    schema = raw.get("schema")
    if schema in ("criteria.v1", "criteria.v2"):
        if "criteria_results" in raw and not isinstance(raw.get("criteria_results"), list):
            return {**raw, "criteria_results": []}
        return raw

    if "criteria_results" in raw and schema is None:
        results = raw.get("criteria_results") or []
        return {"schema": "criteria.v2", "criteria_results": results}

    summary = raw.get("summary")
    criteria_items = raw.get("criteria")
    if isinstance(criteria_items, list) and criteria_items:
        results: list[dict[str, Any]] = []
        for item in criteria_items:
            if not isinstance(item, dict):
                continue
            title = item.get("title") or item.get("criterion") or summary or "Kriterium"
            comment = item.get("comment") or item.get("explanation_md") or summary or ""
            result: dict[str, Any] = {"criterion": str(title)}
            if comment:
                result["explanation_md"] = str(comment)
            raw_score = item.get("score")
            try:
                if raw_score is not None:
                    score_int = int(raw_score)
                    result["score"] = max(0, min(score_int, 10))
            except (TypeError, ValueError):
                pass
            results.append(result)
        if results:
            return {"schema": "criteria.v2", "criteria_results": results}

    try:
        logger.info(
            "analysis_json_unhandled_shape",
            extra={
                "schema": str(schema or ""),
                "keys": sorted([str(k) for k in raw.keys()])[:10],
            },
        )
    except Exception:
        pass
    return None


def _build_latest_submission_payload(
    *,
    course_id: str,
    unit_id: str,
    file_href_builder: Callable[..., str],
    sid: Any,
    tid: Any,
    ssub: Any,
    instruction_md: Any,
    created_at: Any,
    completed_at: Any,
    kind: Any,
    score_raw: Any = None,
    score_max: Any = None,
    h5p_content_id: Any = None,
    h5p_review_token: Any = None,
    text_body: Any,
    mime_type: Any,
    size_bytes: Any,
    storage_key: Any,
    feedback_md: Any = None,
    analysis_json: Any = None,
    include_files: bool = True,
) -> dict[str, Any]:
    """Build a TeachingLatestSubmission response payload from authorised row data."""

    def_kind = str(kind or "text")
    if def_kind == "file" and isinstance(mime_type, str) and "pdf" in mime_type.lower():
        def_kind = "pdf"

    def _safe_int(v: Any) -> int | None:
        if v is None:
            return None
        try:
            n = int(v)
            return max(0, n)
        except (TypeError, ValueError):
            return None

    payload: dict[str, Any] = {
        "id": str(sid),
        "task_id": str(tid),
        "student_sub": str(ssub),
        "instruction_md": str(instruction_md or ""),
        "created_at": created_at.astimezone(timezone.utc).isoformat(),
        "completed_at": (completed_at.astimezone(timezone.utc).isoformat() if completed_at else None),
        "kind": def_kind,
    }
    if def_kind == "h5p":
        payload["score_raw"] = _safe_int(score_raw)
        payload["score_max"] = _safe_int(score_max)
        payload["h5p"] = {
            "content_id": (str(h5p_content_id) if h5p_content_id is not None else None),
            "review_token": (str(h5p_review_token) if h5p_review_token is not None else None),
        }
    if isinstance(text_body, str) and text_body:
        payload["text_body"] = text_body
    if isinstance(feedback_md, str) and feedback_md:
        payload["feedback_md"] = feedback_md

    normalised = _normalise_analysis_json(analysis_json)
    if normalised is not None:
        payload["analysis_json"] = normalised

    files: list[dict[str, Any]] = []
    if include_files and def_kind in ("file", "pdf", "image") and isinstance(storage_key, str):
        try:
            if size_bytes is not None:
                try:
                    size_int = int(size_bytes)
                    if size_int < 0:
                        size_int = 0
                    files.append(
                        {
                            "mime": str(mime_type or ""),
                            "size": size_int,
                            "url": file_href_builder(
                                course_id=str(course_id),
                                unit_id=str(unit_id),
                                task_id=str(tid),
                                student_sub=str(ssub),
                                disposition="inline",
                            ),
                        }
                    )
                except (TypeError, ValueError):
                    files = []
        except Exception:
            files = []
    if include_files:
        payload["files"] = files
    return payload


def _serialize_unit_phase(p) -> dict:
    if is_dataclass(p):
        return asdict(p)
    if isinstance(p, dict):
        return p
    return {
        "id": getattr(p, "id", None),
        "unit_id": getattr(p, "unit_id", None),
        "title": getattr(p, "title", None),
        "position": getattr(p, "position", None),
        "created_at": getattr(p, "created_at", None),
        "updated_at": getattr(p, "updated_at", None),
    }


def _serialize_unit_phase_public(p) -> dict:
    """Serialize a unit phase for public Teaching API schemas."""

    return {
        "id": p.get("id") if isinstance(p, dict) else getattr(p, "id", None),
        "unit_id": p.get("unit_id") if isinstance(p, dict) else getattr(p, "unit_id", None),
        "title": p.get("title") if isinstance(p, dict) else getattr(p, "title", None),
        "position": p.get("position") if isinstance(p, dict) else getattr(p, "position", None),
    }


def _serialize_unit_module(m) -> dict:
    """Serialize a unit module for the teacher visual editor APIs."""

    return {
        "id": m.get("id") if isinstance(m, dict) else getattr(m, "id", None),
        "unit_id": m.get("unit_id") if isinstance(m, dict) else getattr(m, "unit_id", None),
        "phase_id": m.get("phase_id") if isinstance(m, dict) else getattr(m, "phase_id", None),
        "title": m.get("title") if isinstance(m, dict) else getattr(m, "title", None),
        "position_in_phase": (
            m.get("position_in_phase") if isinstance(m, dict) else getattr(m, "position_in_phase", None)
        ),
        "required_prereq_count": (
            m.get("required_prereq_count", 0) if isinstance(m, dict) else getattr(m, "required_prereq_count", 0)
        ),
    }


def _serialize_unit_graph_edge(e) -> dict:
    """Serialize a module edge as {from, to}."""

    if isinstance(e, dict):
        if "from" in e and "to" in e:
            return {"from": e.get("from"), "to": e.get("to")}
        return {"from": e.get("from_module_id"), "to": e.get("to_module_id")}
    return {"from": getattr(e, "from", None), "to": getattr(e, "to", None)}


def _build_live_summary_rows(
    *,
    members: list[str],
    names: dict[str, str],
    tasks: list[dict[str, Any]],
    has_map: set[tuple[str, str]],
    avg_map: dict[tuple[str, str], Any],
    created_at_map: dict[tuple[str, str], str | None],
    score_map: dict[tuple[str, str], tuple[int | None, int | None]] | None = None,
    h5p_map: dict[tuple[str, str], bool] | None = None,
) -> list[dict[str, Any]]:
    """Build one live-summary row per student with per-task status cells.

    Why:
        Keep route handlers focused on guards and data access, while response
        shaping is centralized and testable in one place.
    """

    resolved_h5p_map = h5p_map or {}
    resolved_score_map = score_map or {}

    rows: list[dict[str, Any]] = []
    for sid in members:
        task_cells: list[dict[str, Any]] = []
        for task in tasks:
            tid = task.get("id")
            if tid is None:
                continue
            key = (sid, str(tid))
            has_submission = key in has_map
            cell: dict[str, Any] = {
                "task_id": str(tid),
                "has_submission": has_submission,
                "average_score": avg_map.get(key),
                "created_at": created_at_map.get(key),
            }
            if task.get("kind") == "h5p" and has_submission:
                latest_scores = resolved_score_map.get(key, (None, None))
                cell["score_raw"] = latest_scores[0]
                cell["score_max"] = latest_scores[1]
                cell["h5p_completed"] = resolved_h5p_map.get(key, False)
            task_cells.append(cell)

        rows.append(
            {
                "student": {
                    "sub": sid,
                    "name": names.get(sid, "Unbekannt"),
                },
                "tasks": task_cells,
            }
        )
    return rows


def _build_live_delta_cells(
    *,
    helper_rows: list[dict[str, Any]],
    latest_state_by_task: dict[tuple[str, str], dict[str, Any]],
    avg_by_id: dict[str, Any] | None,
    latest_changed_by_pair: dict[tuple[str, str], Any],
    original_updated_dt: datetime,
    logger_obj: Any = None,
    debug: bool = False,
    timestamp_provider: Callable[[], datetime] | None = None,
    epsilon_seconds: int = 1,
) -> list[dict[str, Any]]:
    """Build live-delta change-cells from helper rows and timing maps.

    Why:
        Delta payload assembly is data-shaping work; keeping it here makes the
        route function easier to reason about and test in isolation.
    """

    eps = timedelta(seconds=max(1, int(epsilon_seconds)))
    now_fn = timestamp_provider or (lambda: datetime.now(timezone.utc))
    cells: list[dict[str, Any]] = []
    resolved_avg = avg_by_id or {}

    for row in helper_rows:
        student_sub = str(row.get("student_sub") or "")
        task_id = str(row.get("task_id") or "")
        latest_state = latest_state_by_task.get((student_sub, task_id), {})
        submission_id = latest_state.get("submission_id") or row.get("submission_id")
        score_raw = row.get("score_raw")
        score_max = row.get("score_max")
        if score_raw is None or score_max is None:
            score_raw = latest_state.get("score_raw", score_raw)
            score_max = latest_state.get("score_max", score_max)

        created_iso = row.get("created_at_iso")
        completed_iso = row.get("completed_at_iso")
        h5p_completed = row.get("h5p_completed")

        changed_dt = None
        latest_changed_at = latest_changed_by_pair.get((student_sub, task_id))
        if latest_changed_at is not None:
            try:
                changed_dt = latest_changed_at.astimezone(timezone.utc)
            except Exception:
                changed_dt = None

        if changed_dt is None:
            fallback_iso = completed_iso or created_iso
            if fallback_iso:
                try:
                    changed_dt = datetime.fromisoformat(str(fallback_iso).replace("Z", "+00:00")).astimezone(timezone.utc)
                except Exception:
                    changed_dt = None

        if changed_dt is None:
            changed_dt = now_fn()

        if debug and logger_obj is not None:
            try:
                student_sub_hash = hashlib.sha256(student_sub.encode("utf-8")).hexdigest()[:12]
                logger_obj.debug(
                    "delta-cell",
                    extra={
                        "student_sub_hash": student_sub_hash,
                        "task_id": task_id,
                        "changed_dt": changed_dt.isoformat(timespec="microseconds"),
                        "original_updated": original_updated_dt.isoformat(timespec="microseconds"),
                    },
                )
            except Exception:
                pass

        include = changed_dt > (original_updated_dt - eps)
        if not include:
            continue

        emit_dt = (changed_dt + eps) if changed_dt > original_updated_dt else (original_updated_dt + eps)
        average_score = resolved_avg.get(submission_id) if submission_id else None
        cell: dict[str, Any] = {
            "student_sub": student_sub,
            "task_id": task_id,
            "has_submission": bool(submission_id),
            "average_score": average_score,
            "changed_at": emit_dt.isoformat(timespec="microseconds"),
        }
        if h5p_completed is not None:
            cell["h5p_completed"] = bool(h5p_completed)
            if score_raw is not None:
                cell["score_raw"] = _safe_int(score_raw)
            if score_max is not None:
                cell["score_max"] = _safe_int(score_max)
        cells.append(cell)

    return cells


def _safe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
