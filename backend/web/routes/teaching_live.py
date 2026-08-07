"""Teaching live routes.

Why:
    The live dashboard endpoints are read-heavy teacher views with dedicated
    cache, authorization, and fallback behavior. Keeping them outside the main
    Teaching adapter makes the route surface easier to navigate while the shared
    repo/read-model helpers are extracted in later C2 work.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import asdict, is_dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
import importlib
import sys as _sys

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from backend.storage.config import get_submissions_bucket
from backend.teaching.errors import TeachingRepositoryUnavailable
from backend.teaching.storage import NullStorageAdapter
from backend.web.routes import teaching_guards
from backend.web.routes.teaching import (
    _current_download_bytes_with_limit,
    _current_max_unit_ids,
    _load_average_scores_by_submission_id,
    _load_latest_submission_state_by_task,
    _load_unit_live_helper_rows,
    _safe_download_filename,
    _safe_int,
    _summary_snapshot_cursor_runtime,
    _teaching_submission_file_href,
)
from backend.web.routes.teaching_serialization import (
    _build_latest_submission_payload,
    _build_live_delta_cells,
    _build_live_summary_rows,
)
from backend.teaching.live_h5p_review import issue_h5p_review_token
from backend.web.routes.teaching_shared import (
    _current_sub,
    _is_uuid_like,
    _json_private,
    _private_error,
    _require_teacher,
)
from backend.web.routes.teaching_validation import canonical_uuid as _canonical_uuid


teaching_live_router = APIRouter(tags=["Teaching"])
logger = logging.getLogger("gustav.web.teaching.live")

STORAGE_ADAPTER = None
_BOUND_TEACHING_MODULE = _sys.modules.get("backend.web.routes.teaching")


def _teaching_module():
    module = _BOUND_TEACHING_MODULE or _sys.modules.get("backend.web.routes.teaching")
    if module is None:  # pragma: no cover - defensive import fallback
        module = importlib.import_module("backend.web.routes.teaching")
    return module


def _get_repo():
    """Resolve the active Teaching repo provider after tests reload or monkeypatch it."""

    return _teaching_module()._get_repo()


def _get_student_live_overview_service():
    """Resolve the active live-overview service provider from the Teaching facade."""

    return _teaching_module()._get_student_live_overview_service()


def _storage_adapter():
    """Return the current Teaching storage adapter, preferring route-global sync updates."""

    return STORAGE_ADAPTER if STORAGE_ADAPTER is not None else _teaching_module().STORAGE_ADAPTER


@teaching_live_router.get("/api/teaching/courses/{course_id}/units/{unit_id}/submissions/summary")
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
    except TeachingRepositoryUnavailable:
        raise
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
    except TeachingRepositoryUnavailable:
        raise
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
        except TeachingRepositoryUnavailable:
            raise
        except Exception:
            roster = []
        member_subs = [sid for sid, _ in roster]
        names = await asyncio.to_thread(
            _teaching_module().resolve_live_student_names_by_sub,
            member_subs,
        )

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
                except TeachingRepositoryUnavailable:
                    raise
                except Exception as exc:
                    logger.warning(
                        "unit_summary_bulk_aggregate_fallback reason=unexpected_error error_type=%s",
                        exc.__class__.__name__,
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
                    except TeachingRepositoryUnavailable:
                        raise
                    except Exception as legacy_exc:
                        logger.warning(
                            "unit_summary_fallback reason=unexpected_error error_type=%s",
                            legacy_exc.__class__.__name__,
                            extra={"course_id": course_id, "unit_id": unit_id},
                        )
                        helper_rows = []
        except TeachingRepositoryUnavailable:
            raise
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


@teaching_live_router.get("/api/teaching/courses/{course_id}/units/{unit_id}/submissions/delta")
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
    except TeachingRepositoryUnavailable:
        raise
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
            except TeachingRepositoryUnavailable:
                raise
            except Exception as exc:
                logger.warning(
                    "unit_delta_helper_fallback reason=unexpected_error error_type=%s",
                    exc.__class__.__name__,
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
                except TeachingRepositoryUnavailable:
                    raise
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

    except TeachingRepositoryUnavailable:
        raise
    except Exception as exc:
        logger.warning(
            "unit_delta_query_failed reason=unexpected_error error_type=%s",
            exc.__class__.__name__,
            extra={"course_id": course_id, "unit_id": unit_id},
        )

    if not cells:
        return Response(status_code=204, headers={"Cache-Control": "private, no-store", "Vary": "Origin"})

    payload = {"cells": cells}
    return _json_private(payload, status_code=200, vary_origin=True)


@teaching_live_router.get("/api/teaching/courses/{course_id}/students/{student_sub:path}/submissions/overview")
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

    names = _teaching_module().resolve_live_student_names_by_sub([str(student_sub)])
    display_name = names.get(str(student_sub), "Unbekannt")
    return _json_private(overview.to_dict(student_name=display_name), status_code=200, vary_origin=True)


@teaching_live_router.get(
    "/api/teaching/courses/{course_id}/units/{unit_id}/tasks/{task_id}/students/{student_sub:path}/submissions/latest"
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
    except TeachingRepositoryUnavailable:
        raise
    except Exception:
        # Fail closed on relation check errors
        return _private_error({"error": "not_found"}, status_code=404, vary_origin=True)

    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore

        if isinstance(repo, DBTeachingRepo):
            projection = repo.get_latest_submission_for_owner(
                owner_sub=sub,
                course_id=course_id,
                unit_id=unit_id,
                task_id=task_id,
                student_sub=student_sub,
            )
            if projection is None:
                return _private_error({"error": "not_found"}, status_code=404, vary_origin=True)

            row = projection["submission"]
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
            task_kind = projection["task_kind"]
            task_instruction_md = projection["instruction_md"]
            task_h5p_content_id = projection["h5p_content_id"]
            review_token = None
            if str(kind or "") == "h5p" and isinstance(task_h5p_content_id, str) and task_h5p_content_id:
                review_token = issue_h5p_review_token(
                    owner_sub=str(sub),
                    task_id=str(task_id),
                    student_sub=str(student_sub),
                    content_id=str(task_h5p_content_id),
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
    except TeachingRepositoryUnavailable:
        raise
    except Exception as exc:
        logger.warning(
            "latest_submission_query_failed reason=unexpected_error error_type=%s",
            exc.__class__.__name__,
            extra={"course_id": course_id, "task_id": task_id},
        )
        return _private_error({"error": "internal_error"}, status_code=500, vary_origin=True)

    # In-memory repositories do not expose the database projection yet.
    return Response(status_code=204, headers={"Cache-Control": "private, no-store", "Vary": "Origin"})


@teaching_live_router.get(
    "/api/teaching/courses/{course_id}/units/{unit_id}/tasks/{task_id}/students/{student_sub:path}/submissions/latest/file"
)
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

        row = repo.get_latest_submission_file_for_owner(
            owner_sub=sub,
            course_id=course_id,
            unit_id=unit_id,
            task_id=task_id,
            student_sub=student_sub,
        )
    except TeachingRepositoryUnavailable:
        raise
    except Exception as exc:
        logger.warning(
            "latest_submission_file_query_failed reason=unexpected_error error_type=%s",
            exc.__class__.__name__,
            extra={"course_id": course_id, "task_id": task_id},
        )
        return _private_error({"error": "internal_error"}, status_code=500, vary_origin=True)

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

        adapter = getattr(learning_routes, "STORAGE_ADAPTER", _storage_adapter())
    except Exception:
        adapter = _storage_adapter()

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
