"""Application-level read-model routes for the new web platform.

Why:
    SvelteKit needs a small shell bootstrap payload that is independent from
    legacy SSR concerns. This router is the first explicit room read-model
    endpoint in the FastAPI adapter.
"""

from __future__ import annotations

import json
import inspect
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.identity_access.admin_client import AdminClient
from backend.identity_access.cli_tokens import CLITokenRecord
from backend.identity_access.tokens import verify_bearer_token
from backend.web.auth_session import SESSION_COOKIE_NAME, app_session_ttl_seconds, set_session_cookie
from backend.web.security.guards import has_any_role

from backend.web.routes import teaching as teaching_routes
from backend.web.routes import teaching_guards
from backend.web.routes.app_learner_view_routes import (
    app_learner_view_router,
    create_learner_concern_box_entry as create_learner_concern_box_entry,  # noqa: F401
    get_learner_concern_box as get_learner_concern_box,  # noqa: F401
    get_learner_home as get_learner_home,  # noqa: F401
    _list_concern_box_courses_for_student as _list_concern_box_courses_for_student,  # noqa: F401
    _list_learner_courses as _list_learner_courses,  # noqa: F401
)
from backend.web.routes.app_profile_helpers import (
    claims_email as _claims_email,  # noqa: F401
    normalized_attributes as _normalized_attributes,
    parse_lock_timestamp as _parse_lock_timestamp,
    profile_identity_defaults as _profile_identity_defaults,
    split_name_suggestion as _split_name_suggestion,  # noqa: F401
)
from backend.web.routes.app_profile_routes import (
    ProfileNameLockedError,
    app_profile_router,
    create_profile_cli_token as create_profile_cli_token,  # noqa: F401 - kept for route module compatibility
    get_app_profile as get_app_profile,  # noqa: F401
    list_profile_cli_tokens as list_profile_cli_tokens,  # noqa: F401
    patch_profile_display_name as patch_profile_display_name,  # noqa: F401
    patch_profile_name as patch_profile_name,  # noqa: F401
    revoke_profile_cli_token as revoke_profile_cli_token,  # noqa: F401
)
from backend.web.routes.app_session_helpers import (
    bff_session_payload as _bff_session_payload,
    bff_session_store as _bff_session_store,
    current_user as _current_user,
    internal_bff_secret_configured as _internal_bff_secret_configured,  # noqa: F401
    oidc_config as _oidc_config,
    private_headers as _private_headers,
    require_internal_bff_secret as _require_internal_bff_secret,
    runtime_from_request as _runtime_from_request,
    runtime_settings as _runtime_settings,
    session_store as _session_store,
    spaces_for_role as _spaces_for_role,
    start_target_for_role as _start_target_for_role,
    user_payload as _user_payload,
)
from backend.web.routes.app_teacher_concern_routes import (
    app_teacher_concern_router,
    archive_teacher_concern_box_entry as archive_teacher_concern_box_entry,  # noqa: F401
    get_teacher_concern_box as get_teacher_concern_box,  # noqa: F401
    get_teacher_home as get_teacher_home,  # noqa: F401
    restore_teacher_concern_box_entry as restore_teacher_concern_box_entry,  # noqa: F401
    _teacher_concern_box_scopes as _teacher_concern_box_scopes,  # noqa: F401
    _teacher_home_entries as _teacher_home_entries,  # noqa: F401
)
from backend.web.routes.app_teacher_course_routes import (
    app_teacher_course_router,
    get_teacher_course_ai_usage as get_teacher_course_ai_usage,  # noqa: F401
    get_teacher_course_context as get_teacher_course_context,  # noqa: F401
    get_teacher_course_list as get_teacher_course_list,  # noqa: F401
    _build_usage_totals as _build_usage_totals,  # noqa: F401
    _count_teacher_course_members as _count_teacher_course_members,  # noqa: F401
    _empty_usage_totals as _empty_usage_totals,  # noqa: F401
    _get_teacher_course as _get_teacher_course,  # noqa: F401
    _list_teacher_course_ai_usage_events as _list_teacher_course_ai_usage_events,  # noqa: F401
    _list_teacher_course_cards as _list_teacher_course_cards,  # noqa: F401
    _list_teacher_course_members as _list_teacher_course_members,  # noqa: F401
    _list_teacher_course_members_window as _list_teacher_course_members_window,  # noqa: F401
    _parse_usage_filter_timestamp as _parse_usage_filter_timestamp,  # noqa: F401
)


app_router = APIRouter(tags=["App"])
app_router.include_router(app_learner_view_router)
app_router.include_router(app_profile_router)
app_router.include_router(app_teacher_concern_router)
app_router.include_router(app_teacher_course_router)


class BFFSessionSyncPayload(BaseModel):
    access_token: str = Field(min_length=1)
    refresh_token: str | None = None
    id_token: str = Field(min_length=1)
    expires_at: int = Field(gt=0)


class AppSessionSyncPayload(BaseModel):
    id_token: str | None = Field(default=None, min_length=1)


def _cli_token_store(request: Request | None = None):
    if request is not None:
        runtime = _runtime_from_request(request)
        if runtime is not None and hasattr(runtime, "cli_token_store"):
            return runtime.cli_token_store
    raise RuntimeError("app runtime cli_token_store is not configured")


def _epoch_to_iso(value: int | None) -> str | None:
    if value is None:
        return None
    return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()


def _serialize_cli_token(record: CLITokenRecord) -> dict[str, object]:
    return {
        "id": record.id,
        "label": record.label,
        "scopes": record.scopes,
        "created_at": _epoch_to_iso(record.created_at),
        "expires_at": _epoch_to_iso(record.expires_at),
        "last_used_at": _epoch_to_iso(record.last_used_at),
        "revoked_at": _epoch_to_iso(record.revoked_at),
    }


def _current_claims(request: Request) -> dict[str, object]:
    """Re-resolve bearer claims for BFF-owned routes that need raw identity data."""
    auth_header = str(request.headers.get("authorization") or "")
    if not auth_header.lower().startswith("bearer "):
        return {}
    token = auth_header.split(" ", 1)[1].strip()
    if not token:
        return {}
    try:
        claims = verify_bearer_token(token=token, cfg=_oidc_config(request))
    except Exception:
        return {}
    return claims if isinstance(claims, dict) else {}


def _load_profile_identity(sub: str, claims: dict[str, object], request: Request | None = None) -> dict[str, object]:
    defaults = _profile_identity_defaults(claims)
    client = AdminClient(_oidc_config(request))
    try:
        user = client.get_user(user_id=sub)
    except Exception:
        return defaults

    attributes = _normalized_attributes(user.get("attributes"))
    display_name = str((attributes.get("display_name") or [defaults["display_name"]])[0] or "").strip()
    email = str(user.get("email") or defaults["email"] or "").strip()
    first_name = str(user.get("firstName") or "").strip()
    last_name = str(user.get("lastName") or "").strip()
    if not first_name and not last_name:
        first_name = str(defaults["first_name"] or "")
        last_name = str(defaults["last_name"] or "")

    locked_until = _parse_lock_timestamp((attributes.get("name_locked_until") or [None])[0])
    now = datetime.now(timezone.utc)
    can_edit = locked_until is None or locked_until <= now
    lock_value = locked_until.astimezone(timezone.utc).isoformat() if locked_until else None

    return {
        "display_name": display_name or str(defaults["display_name"]),
        "email": email,
        "first_name": first_name,
        "last_name": last_name,
        "name_locked_until": lock_value,
        "name_can_edit": can_edit,
    }


def _update_profile_display_name(sub: str, display_name: str, request: Request | None = None) -> None:
    """Persist only the mutable display-name attribute for one profile.

    Why:
        Some identity providers treat fields like `username` or `email` as
        read-only. This update therefore sends only the attribute delta that is
        actually needed and keeps the existing attribute bag intact.
    """
    client = AdminClient(_oidc_config(request))
    user = client.get_user(user_id=sub)
    attributes = _normalized_attributes(user.get("attributes"))
    attributes["display_name"] = [str(display_name).strip()]
    client.update_user(
        user_id=sub,
        payload={
            "email": str(user.get("email") or "").strip(),
            "attributes": attributes,
        },
    )


def _update_profile_name(sub: str, first_name: str, last_name: str, request: Request | None = None) -> None:
    """Persist only Vorname, Nachname and the lock attribute for one profile.

    Why:
        Login-related fields can be externally managed and therefore immutable.
        We update only the profile fields that belong to this use case so the
        request also works for brokered or restricted accounts.
    """
    client = AdminClient(_oidc_config(request))
    user = client.get_user(user_id=sub)
    attributes = _normalized_attributes(user.get("attributes"))
    locked_until = _parse_lock_timestamp((attributes.get("name_locked_until") or [None])[0])
    now = datetime.now(timezone.utc)
    if locked_until is not None and locked_until > now:
        raise ProfileNameLockedError(locked_until.astimezone(timezone.utc).isoformat())

    next_lock = (now + timedelta(days=180)).astimezone(timezone.utc).isoformat()
    attributes["name_locked_until"] = [next_lock]
    payload = {
        "firstName": str(first_name).strip(),
        "lastName": str(last_name).strip(),
        "email": str(user.get("email") or "").strip(),
        "attributes": attributes,
    }
    client.update_user(user_id=sub, payload=payload)


def _list_teacher_course_units(course_id: str, owner_sub: str) -> list[dict]:
    repo = teaching_routes._get_repo()  # type: ignore[attr-defined]
    return repo.list_course_units_for_owner(course_id, owner_sub)


def _list_teacher_units(owner_sub: str, limit: int, offset: int) -> list[dict]:
    repo = teaching_routes._get_repo()  # type: ignore[attr-defined]
    return [
        teaching_routes._serialize_unit(item)  # type: ignore[attr-defined]
        for item in (repo.list_units_for_author(author_id=owner_sub, limit=limit, offset=offset) or [])
    ]


def _list_teacher_courses(owner_sub: str, limit: int, offset: int) -> list[dict[str, str]]:
    repo = teaching_routes._get_repo()  # type: ignore[attr-defined]
    items = repo.list_courses_for_teacher(teacher_id=owner_sub, limit=limit, offset=offset)
    return [
        {
            "id": str(_field_value(item, "id") or ""),
            "title": str(_field_value(item, "title") or ""),
        }
        for item in (items or [])
        if str(_field_value(item, "id") or "")
    ]


def _list_teacher_unit_sections(unit_id: str, owner_sub: str) -> list[dict]:
    repo = teaching_routes._get_repo()  # type: ignore[attr-defined]
    return [
        teaching_routes._serialize_section(item)  # type: ignore[attr-defined]
        for item in (repo.list_sections_for_author(unit_id, owner_sub) or [])
    ]


def _list_teacher_section_materials(unit_id: str, section_id: str, owner_sub: str) -> list[dict]:
    repo = teaching_routes._get_repo()  # type: ignore[attr-defined]
    return [
        teaching_routes._serialize_material(item)  # type: ignore[attr-defined]
        for item in (repo.list_materials_for_section_owned(unit_id, section_id, owner_sub) or [])
    ]


def _list_teacher_section_tasks(unit_id: str, section_id: str, owner_sub: str) -> list[dict]:
    repo = teaching_routes._get_repo()  # type: ignore[attr-defined]
    return [
        teaching_routes._serialize_task(item)  # type: ignore[attr-defined]
        for item in (repo.list_tasks_for_section_owned(unit_id, section_id, owner_sub) or [])
    ]


def _list_teacher_unit_phases(unit_id: str, owner_sub: str) -> list[dict]:
    repo = teaching_routes._get_repo()  # type: ignore[attr-defined]
    return [
        teaching_routes._serialize_unit_phase_public(item)  # type: ignore[attr-defined]
        for item in (repo.list_unit_phases_for_author(unit_id, owner_sub) or [])
    ]


def _list_teacher_unit_modules(unit_id: str, owner_sub: str) -> list[dict]:
    repo = teaching_routes._get_repo()  # type: ignore[attr-defined]
    return [
        dict(item) if isinstance(item, dict) else teaching_routes._serialize_unit_module(item)  # type: ignore[attr-defined]
        for item in (repo.list_unit_modules_for_author(unit_id=unit_id, author_id=owner_sub) or [])
    ]


def _list_teacher_unit_edges(unit_id: str, owner_sub: str) -> list[dict]:
    repo = teaching_routes._get_repo()  # type: ignore[attr-defined]
    return [
        teaching_routes._serialize_unit_graph_edge(item)  # type: ignore[attr-defined]
        for item in (repo.list_unit_module_edges_for_author(unit_id=unit_id, author_id=owner_sub) or [])
    ]


def _field_value(item: object, key: str) -> object:
    if isinstance(item, dict):
        return item.get(key)
    return getattr(item, key, None)


def _build_teacher_unit_course_refs(owner_sub: str) -> tuple[dict[str, list[dict[str, str]]], list[dict[str, str | None]]]:
    course_refs_by_unit: dict[str, list[dict[str, str]]] = {}
    courses = _list_teacher_courses(owner_sub, limit=200, offset=0)

    for course in courses:
        course_id = str(course.get("id") or "")
        if not course_id:
            continue

        for unit in _list_teacher_course_units(course_id, owner_sub):
            unit_id = str(_field_value(unit, "id") or "")
            if not unit_id:
                continue
            course_refs_by_unit.setdefault(unit_id, []).append(
                {
                    "id": course_id,
                    "title": str(course.get("title") or ""),
                    "href": f"/teaching/courses/{course_id}",
                }
            )

    return course_refs_by_unit, courses


def _list_unit_task_ids(unit_id: str, owner_sub: str) -> list[str]:
    repo = teaching_routes._get_repo()  # type: ignore[attr-defined]
    task_ids: list[str] = []
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore

        if isinstance(repo, DBTeachingRepo):
            sections = repo.list_sections_for_author(unit_id, owner_sub)
            for section in sections:
                section_tasks = repo.list_tasks_for_section_owned(unit_id, str(section.get("id") or ""), owner_sub)
                for task in section_tasks:
                    task_id = str(task.get("id") or "")
                    if task_id:
                        task_ids.append(task_id)
            return task_ids
    except Exception:
        pass

    try:
        section_ids = [sid for sid, data in repo.sections.items() if str(getattr(data, "unit_id", "")) == unit_id]
        section_ids.sort(key=lambda sid: int(getattr(repo.sections[sid], "position", 0)))
        for section_id in section_ids:
            for task_id in repo.task_ids_by_section.get(section_id, []):
                if task_id:
                    task_ids.append(str(task_id))
    except Exception:
        return []
    return task_ids


def _list_submission_pairs_for_students(
    course_id: str,
    owner_sub: str,
    student_subs: list[str],
    task_ids: list[str],
) -> set[tuple[str, str]]:
    if not student_subs or not task_ids:
        return set()

    repo = teaching_routes._get_repo()  # type: ignore[attr-defined]
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore
        if isinstance(repo, DBTeachingRepo):
            return repo.list_submission_pairs_for_students(
                owner_sub=owner_sub,
                course_id=course_id,
                student_subs=student_subs,
                task_ids=task_ids,
            )
    except Exception:
        return set()
    return set()


def _build_diagnostics_course_matrix_rows(
    course_id: str,
    owner_sub: str,
    limit: int,
    offset: int,
    units: list[dict[str, object]],
) -> list[dict[str, object]]:
    members = _list_teacher_course_members(course_id, owner_sub, limit=limit, offset=offset)
    task_ids_by_unit = {
        str(unit.get("id") or ""): _list_unit_task_ids(str(unit.get("id") or ""), owner_sub)
        for unit in units
        if str(unit.get("id") or "")
    }
    all_task_ids = sorted({task_id for unit_task_ids in task_ids_by_unit.values() for task_id in unit_task_ids})
    member_subs = [str(member.get("sub") or "") for member in members if str(member.get("sub") or "")]
    submission_pairs = _list_submission_pairs_for_students(course_id, owner_sub, member_subs, all_task_ids)

    rows: list[dict[str, object]] = []
    for member in members:
        student_sub = str(member.get("sub") or "")
        if not student_sub:
            continue
        cells: list[dict[str, object]] = []
        for unit in units:
            unit_id = str(unit.get("id") or "")
            unit_task_ids = task_ids_by_unit.get(unit_id, [])
            submitted_tasks = sum(1 for task_id in unit_task_ids if (student_sub, task_id) in submission_pairs)
            cells.append(
                {
                    "unit_id": unit_id,
                    "submitted_tasks": submitted_tasks,
                    "total_tasks": len(unit_task_ids),
                    "href": f"/live/courses/{course_id}/units/{unit_id}",
                }
            )
        rows.append(
            {
                "student": {
                    "sub": student_sub,
                    "name": str(member.get("name") or student_sub),
                    "href": f"/diagnostics/learners/{student_sub}",
                },
                "cells": cells,
            }
        )
    return rows


def _teacher_course_has_member(course_id: str, owner_sub: str, student_sub: str) -> bool:
    repo = teaching_routes._get_repo()  # type: ignore[attr-defined]
    try:
        return bool(repo.course_has_member(course_id, owner_sub, student_sub))
    except Exception:
        members = _list_teacher_course_members(course_id, owner_sub, limit=200, offset=0)
        return any(str(member.get("sub") or "") == student_sub for member in members)


def _build_diagnostics_learner_profile_courses(
    student_sub: str,
    owner_sub: str,
    limit: int,
    offset: int,
) -> list[dict[str, object]]:
    courses: list[dict[str, object]] = []
    for course in _list_teacher_courses(owner_sub, limit=limit, offset=offset):
        course_id = str(course.get("id") or "")
        if not course_id or not _teacher_course_has_member(course_id, owner_sub, student_sub):
            continue

        units = [
            {
                "id": str(item.get("id") or ""),
                "title": str(item.get("title") or ""),
                "position": int(item.get("position") or 0),
                "href": f"/diagnostics/courses/{course_id}/units/{item.get('id')}",
            }
            for item in _list_teacher_course_units(course_id, owner_sub)
            if isinstance(item, dict)
        ]
        task_ids_by_unit = {
            str(unit.get("id") or ""): _list_unit_task_ids(str(unit.get("id") or ""), owner_sub)
            for unit in units
            if str(unit.get("id") or "")
        }
        all_task_ids = sorted({task_id for unit_task_ids in task_ids_by_unit.values() for task_id in unit_task_ids})
        submission_pairs = _list_submission_pairs_for_students(course_id, owner_sub, [student_sub], all_task_ids)

        unit_summaries: list[dict[str, object]] = []
        course_submitted_tasks = 0
        course_total_tasks = 0
        for unit in units:
            unit_id = str(unit.get("id") or "")
            unit_task_ids = task_ids_by_unit.get(unit_id, [])
            submitted_tasks = sum(1 for task_id in unit_task_ids if (student_sub, task_id) in submission_pairs)
            total_tasks = len(unit_task_ids)
            course_submitted_tasks += submitted_tasks
            course_total_tasks += total_tasks
            unit_summaries.append(
                {
                    "id": unit_id,
                    "title": str(unit.get("title") or ""),
                    "position": int(unit.get("position") or 0),
                    "href": str(unit.get("href") or ""),
                    "submitted_tasks": submitted_tasks,
                    "total_tasks": total_tasks,
                }
            )

        courses.append(
            {
                "id": course_id,
                "title": str(course.get("title") or ""),
                "href": f"/diagnostics/courses/{course_id}",
                "submitted_tasks": course_submitted_tasks,
                "total_tasks": course_total_tasks,
                "units": unit_summaries,
            }
        )
    return courses


def _decode_json_response_body(response: object) -> object:
    body = getattr(response, "body", b"")
    if not body:
        return None
    if isinstance(body, bytes):
        raw = body.decode("utf-8")
    else:
        raw = str(body)
    if not raw:
        return None
    return json.loads(raw)


def _find_course_unit(course_id: str, owner_sub: str, unit_id: str) -> dict[str, object] | None:
    for item in _list_teacher_course_units(course_id, owner_sub):
        if not isinstance(item, dict):
            continue
        if str(item.get("id") or "") == unit_id:
            return item
    return None


@app_router.get("/api/app/session-bootstrap")
async def get_session_bootstrap(request: Request):
    """Return shell bootstrap data for the current authenticated session."""
    user = _current_user(request)
    if user is None:
        return JSONResponse({"error": "unauthenticated"}, status_code=401, headers=_private_headers())

    primary_role = str(user.get("role") or "student")
    body = {
        "user": _user_payload(user),
        "start_target": _start_target_for_role(primary_role),
        "spaces": _spaces_for_role(primary_role),
    }
    return JSONResponse(body, headers=_private_headers())


@app_router.post("/api/app/session-sync")
async def post_session_sync(request: Request, payload: AppSessionSyncPayload | None = None):
    """Mint a stable app session from a bearer-authenticated Svelte BFF request."""
    user = _current_user(request)
    if user is None:
        return JSONResponse({"error": "unauthenticated"}, status_code=401, headers=_private_headers())

    store = _session_store(request)

    stale_session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if stale_session_id:
        try:
            store.delete(stale_session_id)
        except Exception:
            pass

    session = store.create(
        sub=str(user.get("sub") or ""),
        roles=[str(role) for role in (user.get("roles") or []) if isinstance(role, str)] or ["student"],
        name=str(user.get("name") or ""),
        ttl_seconds=app_session_ttl_seconds(),
        id_token=(payload.id_token if payload is not None else None) or getattr(request.state, "id_token", None),
    )
    response = Response(status_code=204, headers=_private_headers())
    set_session_cookie(response, session.session_id, environment=_runtime_settings(request).environment)
    return response


@app_router.put("/backend-internal/app/bff-session")
async def put_bff_session(request: Request, payload: BFFSessionSyncPayload):
    """Persist or update the opaque Browser-BFF token session."""
    if not _require_internal_bff_secret(request):
        return JSONResponse({"error": "unauthenticated"}, status_code=401, headers=_private_headers())
    store = _bff_session_store(request)
    session = store.create(
        access_token=payload.access_token,
        refresh_token=payload.refresh_token,
        id_token=payload.id_token,
        expires_at=int(payload.expires_at),
    )
    return JSONResponse(_bff_session_payload(session), headers=_private_headers())


@app_router.get("/backend-internal/app/bff-session")
async def get_bff_session(request: Request):
    """Return the stored Browser-BFF token session for an opaque session id."""
    if not _require_internal_bff_secret(request):
        return JSONResponse({"error": "unauthenticated"}, status_code=401, headers=_private_headers())
    session_id = str(request.headers.get("x-gustav-bff-session") or "").strip()
    if not session_id:
        return Response(status_code=204, headers=_private_headers())
    store = _bff_session_store(request)
    session = store.get(session_id)
    if session is None:
        return Response(status_code=204, headers=_private_headers())
    return JSONResponse(_bff_session_payload(session), headers=_private_headers())


@app_router.patch("/backend-internal/app/bff-session")
async def patch_bff_session(request: Request, payload: BFFSessionSyncPayload):
    """Update an existing Browser-BFF token session."""
    if not _require_internal_bff_secret(request):
        return JSONResponse({"error": "unauthenticated"}, status_code=401, headers=_private_headers())
    session_id = str(request.headers.get("x-gustav-bff-session") or "").strip()
    if not session_id:
        return JSONResponse({"error": "unauthenticated"}, status_code=401, headers=_private_headers())
    store = _bff_session_store(request)
    session = store.update(
        session_id,
        access_token=payload.access_token,
        refresh_token=payload.refresh_token,
        id_token=payload.id_token,
        expires_at=int(payload.expires_at),
    )
    if session is None:
        return JSONResponse({"error": "unauthenticated"}, status_code=401, headers=_private_headers())
    return JSONResponse(_bff_session_payload(session), headers=_private_headers())


@app_router.delete("/backend-internal/app/bff-session")
async def delete_bff_session(request: Request):
    """Delete one Browser-BFF token session."""
    if not _require_internal_bff_secret(request):
        return JSONResponse({"error": "unauthenticated"}, status_code=401, headers=_private_headers())
    session_id = str(request.headers.get("x-gustav-bff-session") or "").strip()
    if session_id:
        _bff_session_store(request).delete(session_id)
    return Response(status_code=204, headers=_private_headers())


@app_router.get("/api/teaching/views/units/catalog")
async def get_teacher_units_catalog(
    request: Request,
    query: str = "",
    sort: str | None = None,
):
    """Return the teacher units catalog as a structured bestandsliste.

    The payload stays intentionally small and UI-ready. It avoids mixed meta
    strings so the frontend can render a flat table-like inventory with a
    separate course cell and a dedicated title link.
    """
    user = _current_user(request)
    if user is None:
        return JSONResponse({"error": "unauthenticated"}, status_code=401, headers=_private_headers())
    if not has_any_role(user, {"teacher", "admin"}):
        return JSONResponse({"error": "forbidden"}, status_code=403, headers=_private_headers())

    owner_sub = str(user.get("sub") or "")
    course_refs_by_unit, _ = _build_teacher_unit_course_refs(owner_sub)
    units = _list_teacher_units(owner_sub, limit=200, offset=0)

    items: list[dict[str, object]] = []

    for unit in units:
        unit_id = str(unit.get("id") or "")
        refs = course_refs_by_unit.get(unit_id, [])
        sections = _list_teacher_unit_sections(unit_id, owner_sub)
        sections_count = len(sections)
        courses_count = len(refs)
        last_activity = max(
            [str(unit.get("updated_at") or "")]
            + [str(section.get("updated_at") or "") for section in sections]
        )
        haystack = " ".join(
            part.strip().lower()
            for part in (
                str(unit.get("title") or ""),
                str(unit.get("summary") or ""),
            )
            if part
        )

        if courses_count > 0:
            status_label = "Aktiv im Unterricht"
            status_tone = "success"
        elif sections_count == 0:
            status_label = "Entwurf"
            status_tone = "muted"
        else:
            status_label = "In Bearbeitung"
            status_tone = "accent"

        item = {
            "id": unit_id,
            "title": str(unit.get("title") or ""),
            "topic": str(unit.get("summary") or "").strip() or None,
            "updated_at": last_activity,
            "href": f"/teaching/units/{unit_id}",
            "courses_count": courses_count,
            "courses": [
                {
                    "id": str(ref.get("id") or ""),
                    "title": str(ref.get("title") or ""),
                    "href": str(ref.get("href") or ""),
                }
                for ref in refs
                if str(ref.get("id") or "")
            ],
            "status_label": status_label,
            "status_tone": status_tone,
            "searchable": haystack,
        }
        items.append(item)

    query_value = query.strip()
    if query_value:
        needle = query_value.lower()
        items = [item for item in items if needle in str(item["searchable"])]

    active_sort = sort or "updated_desc"
    if active_sort == "title_asc":
        items.sort(key=lambda item: str(item["title"]).lower())
    else:
        items.sort(key=lambda item: str(item["updated_at"]), reverse=True)

    list_items = [
        {
            "id": str(item["id"]),
            "title": str(item["title"]),
            "topic": item["topic"],
            "status_label": str(item["status_label"]),
            "status_tone": str(item["status_tone"]),
            "courses_count": int(item["courses_count"]),
            "courses": item["courses"],
            "updated_at": str(item["updated_at"]),
            "href": str(item["href"]),
        }
        for item in items
    ]

    body = {
        "user": _user_payload(user),
        "query": query_value,
        "sort": active_sort,
        "result_count": len(list_items),
        "items": list_items,
        "create_href": "/teaching/units?create=1",
    }
    return JSONResponse(body, headers=_private_headers())


@app_router.get("/api/teaching/views/units/{unit_id}/workspace")
async def get_teacher_unit_workspace(
    request: Request,
    unit_id: str,
    section_id: str | None = None,
    phase_id: str | None = None,
    module_id: str | None = None,
    edge_from_module_id: str | None = None,
    edge_to_module_id: str | None = None,
):
    """Return the graph-first teacher unit workspace read-model."""
    user = _current_user(request)
    if user is None:
        return JSONResponse({"error": "unauthenticated"}, status_code=401, headers=_private_headers())
    if not has_any_role(user, {"teacher", "admin"}):
        return JSONResponse({"error": "forbidden"}, status_code=403, headers=_private_headers())
    if not teaching_routes._is_uuid_like(unit_id):  # type: ignore[attr-defined]
        return JSONResponse(
            {"error": "bad_request", "detail": "invalid_unit_id"},
            status_code=400,
            headers=_private_headers(),
        )

    owner_sub = str(user.get("sub") or "")
    guard = teaching_guards._guard_unit_author(
        unit_id,
        owner_sub,
        repo_provider=teaching_routes._get_repo,  # type: ignore[attr-defined]
    )
    if guard:
        return guard

    repo = teaching_routes._get_repo()  # type: ignore[attr-defined]
    unit = repo.get_unit_for_author(unit_id, owner_sub)
    if not unit:
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_private_headers())

    serialized_unit = teaching_routes._serialize_unit(unit)  # type: ignore[attr-defined]
    unit_type = str(serialized_unit.get("unit_type") or "linear").strip().lower() or "linear"
    course_refs_by_unit, _courses = _build_teacher_unit_course_refs(owner_sub)
    courses_count = len(course_refs_by_unit.get(unit_id, []))

    counts = {"sections_count": 0, "phases_count": 0, "modules_count": 0, "courses_count": courses_count}
    graph: dict[str, object] = {"kind": unit_type}
    selection: dict[str, object] = {"kind": "none"}

    def _validate_optional_uuid(raw_value: str | None, detail: str) -> str:
        value = str(raw_value or "").strip()
        if value and not teaching_routes._is_uuid_like(value):  # type: ignore[attr-defined]
            raise ValueError(detail)
        return value

    if unit_type == "modular":
        required_methods = (
            "list_unit_phases_for_author",
            "list_unit_modules_for_author",
            "list_unit_module_edges_for_author",
        )
        repo_error = teaching_routes._require_modular_repo_methods(repo, *required_methods)  # type: ignore[attr-defined]
        if repo_error:
            return repo_error

        try:
            selected_phase_id = _validate_optional_uuid(phase_id, "invalid_phase_id")
            selected_module_id = _validate_optional_uuid(module_id, "invalid_module_id")
            edge_source_id = _validate_optional_uuid(edge_from_module_id, "invalid_edge_from_module_id")
            edge_target_id = _validate_optional_uuid(edge_to_module_id, "invalid_edge_to_module_id")
        except ValueError as exc:
            return JSONResponse(
                {"error": "bad_request", "detail": str(exc)},
                status_code=400,
                headers=_private_headers(),
            )

        phases = _list_teacher_unit_phases(unit_id, owner_sub)
        modules = _list_teacher_unit_modules(unit_id, owner_sub)
        edges = _list_teacher_unit_edges(unit_id, owner_sub)

        module_items: list[dict[str, object]] = []
        modules_by_id: dict[str, dict[str, object]] = {}
        phase_items: list[dict[str, object]] = []
        for module in modules:
            section_id = str(module.get("section_id") or "")
            materials_count = 0
            tasks_count = 0
            if section_id:
                materials_count = len(_list_teacher_section_materials(unit_id, section_id, owner_sub))
                tasks_count = len(_list_teacher_section_tasks(unit_id, section_id, owner_sub))
            item = {
                "id": str(module.get("id") or ""),
                "title": str(module.get("title") or ""),
                "phase_id": str(module.get("phase_id") or ""),
                "position_in_phase": int(module.get("position_in_phase") or 0),
                "required_prereq_count": int(module.get("required_prereq_count") or 0),
                "materials_count": materials_count,
                "tasks_count": tasks_count,
                "editor_href": f"/teaching/units/{unit_id}/nodes/{str(module.get('id') or '')}",
                "section_id": section_id or None,
            }
            module_items.append(item)
            if item["id"]:
                modules_by_id[str(item["id"])] = item

        for phase in phases:
            phase_items.append(
                {
                    "id": str(phase.get("id") or ""),
                    "title": str(phase.get("title") or ""),
                    "position": int(phase.get("position") or 0),
                    "modules": [
                        item
                        for item in module_items
                        if str(item.get("phase_id") or "") == str(phase.get("id") or "")
                    ],
                }
            )

        counts = {
            "sections_count": 0,
            "phases_count": len(phases),
            "modules_count": len(module_items),
            "courses_count": courses_count,
        }

        if not selected_module_id and module_items:
            selected_module_id = str(module_items[0].get("id") or "")
        selected_module = modules_by_id.get(selected_module_id or "")
        selected_phase = next(
            (phase for phase in phases if str(phase.get("id") or "") == (selected_phase_id or "")),
            None,
        )
        selected_edge = None
        if edge_source_id and edge_target_id:
            source_title = str((modules_by_id.get(edge_source_id or "") or {}).get("title") or "")
            target_title = str((modules_by_id.get(edge_target_id or "") or {}).get("title") or "")
            selected_edge = {
                "from_id": edge_source_id,
                "to_id": edge_target_id,
                "from_title": source_title,
                "to_title": target_title,
                "exists": any(
                    str(edge.get("from") or "") == edge_source_id and str(edge.get("to") or "") == edge_target_id
                    for edge in edges
                ),
            }

        graph = {
            "kind": "modular",
            "create_phase_href": f"/teaching/units/{unit_id}?create-phase=1",
            "create_module_href": f"/teaching/units/{unit_id}?create-module=1",
            "phases": phase_items,
            "edges": edges,
        }
        if selected_edge:
            selection = {"kind": "edge", "edge": selected_edge}
        elif selected_module:
            selection = {"kind": "module", "module": selected_module}
        elif selected_phase:
            selection = {
                "kind": "phase",
                "phase": {
                    "id": str((selected_phase or {}).get("id") or ""),
                    "title": str((selected_phase or {}).get("title") or ""),
                    "position": int((selected_phase or {}).get("position") or 0),
                },
            }
    else:
        try:
            selected_section_id = _validate_optional_uuid(section_id, "invalid_section_id")
        except ValueError as exc:
            return JSONResponse(
                {"error": "bad_request", "detail": str(exc)},
                status_code=400,
                headers=_private_headers(),
            )

        sections = _list_teacher_unit_sections(unit_id, owner_sub)
        section_items: list[dict[str, object]] = []
        for section in sections:
            current_section_id = str(section.get("id") or "")
            section_items.append(
                {
                    "id": current_section_id,
                    "title": str(section.get("title") or ""),
                    "position": int(section.get("position") or 0),
                    "materials_count": len(_list_teacher_section_materials(unit_id, current_section_id, owner_sub)),
                    "tasks_count": len(_list_teacher_section_tasks(unit_id, current_section_id, owner_sub)),
                    "editor_href": f"/teaching/units/{unit_id}/nodes/{current_section_id}",
                }
            )

        counts = {
            "sections_count": len(section_items),
            "phases_count": 0,
            "modules_count": 0,
            "courses_count": courses_count,
        }

        if not selected_section_id and section_items:
            selected_section_id = str(section_items[0].get("id") or "")

        selected_structure_section = next(
            (section for section in section_items if str(section.get("id") or "") == (selected_section_id or "")),
            None,
        )
        graph = {
            "kind": "linear",
            "create_section_href": f"/teaching/units/{unit_id}?create-section=1",
            "nodes": section_items,
        }
        if selected_structure_section:
            selection = {
                "kind": "section",
                "section": {
                    "id": str(selected_structure_section.get("id") or ""),
                    "title": str(selected_structure_section.get("title") or ""),
                    "position": int(selected_structure_section.get("position") or 0),
                    "editor_href": str(selected_structure_section.get("editor_href") or ""),
                },
            }

    body = {
        "user": _user_payload(user),
        "unit": {
            "id": str(serialized_unit.get("id") or ""),
            "title": str(serialized_unit.get("title") or ""),
            "summary": serialized_unit.get("summary"),
            "unit_type": unit_type,
            "edit_href": f"/teaching/units/{unit_id}?edit=1",
        },
        "counts": counts,
        "graph": graph,
        "selection": selection,
    }
    return JSONResponse(body, headers=_private_headers())


@app_router.get("/api/teaching/views/units/{unit_id}/nodes/{node_id}/editor")
async def get_teacher_unit_node_editor(request: Request, unit_id: str, node_id: str):
    """Return the shared teacher content editor read-model for a unit node."""
    user = _current_user(request)
    if user is None:
        return JSONResponse({"error": "unauthenticated"}, status_code=401, headers=_private_headers())
    if not has_any_role(user, {"teacher", "admin"}):
        return JSONResponse({"error": "forbidden"}, status_code=403, headers=_private_headers())
    if not teaching_routes._is_uuid_like(unit_id):  # type: ignore[attr-defined]
        return JSONResponse({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400, headers=_private_headers())
    if not teaching_routes._is_uuid_like(node_id):  # type: ignore[attr-defined]
        return JSONResponse({"error": "bad_request", "detail": "invalid_node_id"}, status_code=400, headers=_private_headers())

    owner_sub = str(user.get("sub") or "")
    guard = teaching_guards._guard_unit_author(
        unit_id,
        owner_sub,
        repo_provider=teaching_routes._get_repo,  # type: ignore[attr-defined]
    )
    if guard:
        return guard

    repo = teaching_routes._get_repo()  # type: ignore[attr-defined]
    unit = repo.get_unit_for_author(unit_id, owner_sub)
    if not unit:
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_private_headers())

    serialized_unit = teaching_routes._serialize_unit(unit)  # type: ignore[attr-defined]
    unit_type = str(serialized_unit.get("unit_type") or "linear").strip().lower() or "linear"

    node_kind = "section"
    node_title = ""
    backing_section_id = node_id
    settings: dict[str, object] = {"kind": "section"}

    if unit_type == "modular":
        repo_error = teaching_routes._require_modular_repo_methods(repo, "get_unit_module_for_author")  # type: ignore[attr-defined]
        if repo_error:
            return repo_error
        module = repo.get_unit_module_for_author(unit_id=unit_id, module_id=node_id, author_id=owner_sub)
        if not module:
            return JSONResponse({"error": "not_found"}, status_code=404, headers=_private_headers())
        node_kind = "module"
        node_title = str(module.get("title") or "")
        backing_section_id = str(module.get("section_id") or "")
        settings = {
            "kind": "module",
            "required_prereq_count": int(module.get("required_prereq_count") or 0),
        }
    else:
        section = next(
            (item for item in _list_teacher_unit_sections(unit_id, owner_sub) if str(item.get("id") or "") == node_id),
            None,
        )
        if not section:
            return JSONResponse({"error": "not_found"}, status_code=404, headers=_private_headers())
        node_title = str(section.get("title") or "")

    materials = _list_teacher_section_materials(unit_id, backing_section_id, owner_sub)
    tasks = _list_teacher_section_tasks(unit_id, backing_section_id, owner_sub)

    body = {
        "user": _user_payload(user),
        "unit": {
            "id": str(serialized_unit.get("id") or ""),
            "title": str(serialized_unit.get("title") or ""),
            "summary": serialized_unit.get("summary"),
            "unit_type": unit_type,
            "edit_href": f"/teaching/units/{unit_id}?edit=1",
        },
        "node": {
            "id": node_id,
            "kind": node_kind,
            "title": node_title,
            "editor_title": node_title,
        },
        "materials": [
            {
                "id": str(item.get("id") or ""),
                "title": str(item.get("title") or ""),
                "kind": str(item.get("kind") or "markdown"),
                "body_md": item.get("body_md"),
                "position": int(item.get("position") or 0),
                "mime_type": item.get("mime_type"),
                "size_bytes": item.get("size_bytes"),
                "filename_original": item.get("filename_original"),
                "alt_text": item.get("alt_text"),
            }
            for item in materials
            if str(item.get("id") or "")
        ],
        "tasks": [
            {
                "id": str(item.get("id") or ""),
                "instruction_md": str(item.get("instruction_md") or ""),
                "criteria": list(item.get("criteria") or []),
                "teacher_context_md": item.get("teacher_context_md"),
                "due_at": item.get("due_at"),
                "max_attempts": item.get("max_attempts"),
                "position": int(item.get("position") or 0),
                "kind": str(item.get("kind") or "native"),
                "h5p": item.get("h5p"),
                "visual": item.get("visual"),
                "scratch": item.get("scratch"),
                "calliope": item.get("calliope"),
            }
            for item in tasks
            if str(item.get("id") or "")
        ],
        "settings": settings,
    }
    if node_kind == "module":
        body["node"]["backing_section_id"] = backing_section_id
    return JSONResponse(body, headers=_private_headers())


@app_router.get("/api/diagnostics/views/courses/{course_id}/matrix")
async def get_diagnostics_course_matrix(request: Request, course_id: str, limit: int = 25, offset: int = 0):
    """Return the first course-scoped diagnostics matrix for SvelteKit."""
    user = _current_user(request)
    if user is None:
        return JSONResponse({"error": "unauthenticated"}, status_code=401, headers=_private_headers())
    if not has_any_role(user, {"teacher", "admin"}):
        return JSONResponse({"error": "forbidden"}, status_code=403, headers=_private_headers())

    owner_sub = str(user.get("sub") or "")
    guard = teaching_guards._guard_course_owner(
        course_id,
        owner_sub,
        repo_provider=teaching_routes._get_current_teaching_repo_for_provider,
    )
    if guard:
        return guard

    course = _get_teacher_course(course_id, owner_sub)
    if course is None:
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_private_headers())

    units = [
        {
            "id": str(item.get("id") or ""),
            "title": str(item.get("title") or ""),
            "position": int(item.get("position") or 0),
            "href": f"/live/courses/{course_id}/units/{item.get('id')}",
        }
        for item in _list_teacher_course_units(course_id, owner_sub)
        if isinstance(item, dict)
    ]
    body = {
        "user": _user_payload(user),
        "course": {
            "id": str(_field_value(course, "id") or ""),
            "title": str(_field_value(course, "title") or ""),
            "href": f"/diagnostics/courses/{course_id}",
        },
        "units": units,
        "rows": _build_diagnostics_course_matrix_rows(
            course_id,
            owner_sub,
            limit=int(limit or 25),
            offset=int(offset or 0),
            units=units,
        ),
    }
    return JSONResponse(body, headers=_private_headers())


@app_router.get("/api/live/views/courses/{course_id}/units/{unit_id}/matrix")
async def get_live_unit_matrix(request: Request, course_id: str, unit_id: str, limit: int = 100, offset: int = 0):
    """Return the live room matrix read-model for one course-unit pair."""
    user = _current_user(request)
    if user is None:
        return JSONResponse({"error": "unauthenticated"}, status_code=401, headers=_private_headers())
    if not has_any_role(user, {"teacher", "admin"}):
        return JSONResponse({"error": "forbidden"}, status_code=403, headers=_private_headers())

    owner_sub = str(user.get("sub") or "")
    guard = teaching_guards._guard_course_owner(
        course_id,
        owner_sub,
        repo_provider=teaching_routes._get_current_teaching_repo_for_provider,
    )
    if guard:
        return guard

    course = _get_teacher_course(course_id, owner_sub)
    if course is None:
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_private_headers())

    unit = _find_course_unit(course_id, owner_sub, unit_id)
    if unit is None:
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_private_headers())

    summary_result = teaching_routes.get_unit_live_summary(
        request,
        course_id=course_id,
        unit_id=unit_id,
        limit=int(limit or 100),
        offset=int(offset or 0),
    )
    summary_response = await summary_result if inspect.isawaitable(summary_result) else summary_result
    if getattr(summary_response, "status_code", 500) != 200:
        return summary_response

    payload = _decode_json_response_body(summary_response)
    data = payload if isinstance(payload, dict) else {}
    tasks = data.get("tasks") if isinstance(data.get("tasks"), list) else []
    rows_in = data.get("rows") if isinstance(data.get("rows"), list) else []

    rows: list[dict[str, object]] = []
    for row in rows_in:
        if not isinstance(row, dict):
            continue
        student = row.get("student") if isinstance(row.get("student"), dict) else {}
        student_sub = str(student.get("sub") or "")
        student_name = str(student.get("name") or student_sub)
        task_cells: list[dict[str, object]] = []
        for cell in row.get("tasks") or []:
            if not isinstance(cell, dict):
                continue
            task_id = str(cell.get("task_id") or "")
            task_cell = {
                "task_id": task_id,
                "has_submission": bool(cell.get("has_submission")),
                "average_score": cell.get("average_score"),
                "href": (
                    f"/live/courses/{course_id}/units/{unit_id}"
                    f"?student_sub={student_sub}&task_id={task_id}"
                ),
            }
            if cell.get("score_raw") is not None:
                task_cell["score_raw"] = cell.get("score_raw")
            if cell.get("score_max") is not None:
                task_cell["score_max"] = cell.get("score_max")
            if cell.get("h5p_completed") is not None:
                task_cell["h5p_completed"] = cell.get("h5p_completed")
            task_cells.append(task_cell)
        rows.append(
            {
                "student": {
                    "sub": student_sub,
                    "name": student_name,
                    "href": f"/live/courses/{course_id}/units/{unit_id}?student_sub={student_sub}",
                },
                "tasks": task_cells,
            }
        )

    body = {
        "user": _user_payload(user),
        "course": {
            "id": str(_field_value(course, "id") or ""),
            "title": str(_field_value(course, "title") or ""),
            "href": f"/live/courses/{course_id}",
        },
        "unit": {
            "id": str(unit.get("id") or ""),
            "title": str(unit.get("title") or ""),
            "position": int(unit.get("position") or 0),
            "href": f"/live/courses/{course_id}/units/{unit_id}",
        },
        "tasks": tasks,
        "rows": rows,
    }
    return JSONResponse(body, headers=_private_headers())


@app_router.get("/api/live/views/courses/{course_id}/units")
async def get_live_course_units(request: Request, course_id: str):
    """Return a lightweight unit list for the `/live` course selection UI."""
    user = _current_user(request)
    if user is None:
        return JSONResponse({"error": "unauthenticated"}, status_code=401, headers=_private_headers())
    if not has_any_role(user, {"teacher", "admin"}):
        return JSONResponse({"error": "forbidden"}, status_code=403, headers=_private_headers())

    owner_sub = str(user.get("sub") or "")
    guard = teaching_guards._guard_course_owner(
        course_id,
        owner_sub,
        repo_provider=teaching_routes._get_current_teaching_repo_for_provider,
    )
    if guard:
        return guard

    course = _get_teacher_course(course_id, owner_sub)
    if course is None:
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_private_headers())

    units = [
        {
            "id": str(item.get("id") or ""),
            "title": str(item.get("title") or ""),
            "position": int(item.get("position") or 0),
            "href": f"/live?course_id={course_id}&unit_id={item.get('id')}",
        }
        for item in _list_teacher_course_units(course_id, owner_sub)
        if isinstance(item, dict)
    ]

    body = {
        "user": _user_payload(user),
        "course": {
            "id": str(_field_value(course, "id") or ""),
            "title": str(_field_value(course, "title") or ""),
            "href": f"/live?course_id={course_id}",
        },
        "units": units,
    }
    return JSONResponse(body, headers=_private_headers())


def _live_selection_href(course_id: str, unit_id: str, student_sub: str | None = None, task_id: str | None = None) -> str:
    """Build canonical `/live` dashboard links for course/unit/student selections."""
    parts = [f"course_id={course_id}", f"unit_id={unit_id}"]
    if student_sub:
        parts.append(f"student_sub={student_sub}")
    if task_id:
        parts.append(f"task_id={task_id}")
    return "/live?" + "&".join(parts)


def _round_live_average(values: list[float | None]) -> float | None:
    """Return a stable arithmetic mean for compact dashboard KPIs."""
    numbers = [float(value) for value in values if isinstance(value, (int, float))]
    if not numbers:
        return None
    return round(sum(numbers) / len(numbers), 1)


def _live_task_meta_by_id(tasks: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    """Map task ids to lightweight label metadata for dashboard rendering."""
    out: dict[str, dict[str, object]] = {}
    for task in tasks:
        task_id = str(task.get("id") or "")
        position = int(task.get("position") or 0)
        out[task_id] = {
            "task_position": position,
            "task_label": f"{position}. Aufgabe",
        }
    return out


def _live_dashboard_localpart_identifier(*values: object) -> str:
    """Return a stable localpart-style fallback for live dashboard labels."""
    for candidate in values:
        raw = str(candidate or "").strip()
        if not raw:
            continue
        try:
            from backend.identity_access import directory  # type: ignore

            extractor = getattr(directory, "localpart_identifier", None)
            if callable(extractor):
                localpart = str(extractor(raw) or "").strip()
                if localpart:
                    return localpart
        except Exception:
            pass
        normalized = raw.split(":", 1)[1].strip() if raw.startswith("legacy-email:") else raw
        if "@" in normalized:
            localpart = normalized.split("@", 1)[0].strip()
            if localpart:
                return localpart
    return ""


@app_router.get("/api/live/views/courses/{course_id}/units/{unit_id}/dashboard")
async def get_live_unit_dashboard(
    request: Request,
    course_id: str,
    unit_id: str,
    student_sub: str | None = None,
    task_id: str | None = None,
):
    """Return a compact dashboard read-model for one live course-unit pair."""
    user = _current_user(request)
    if user is None:
        return JSONResponse({"error": "unauthenticated"}, status_code=401, headers=_private_headers())
    if not has_any_role(user, {"teacher", "admin"}):
        return JSONResponse({"error": "forbidden"}, status_code=403, headers=_private_headers())

    owner_sub = str(user.get("sub") or "")
    guard = teaching_guards._guard_course_owner(
        course_id,
        owner_sub,
        repo_provider=teaching_routes._get_current_teaching_repo_for_provider,
    )
    if guard:
        return guard

    course = _get_teacher_course(course_id, owner_sub)
    if course is None:
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_private_headers())

    unit = _find_course_unit(course_id, owner_sub, unit_id)
    if unit is None:
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_private_headers())

    summary_result = teaching_routes.get_unit_live_summary(
        request,
        course_id=course_id,
        unit_id=unit_id,
        limit=100,
        offset=0,
    )
    summary_response = await summary_result if inspect.isawaitable(summary_result) else summary_result
    if getattr(summary_response, "status_code", 500) != 200:
        return summary_response

    payload = _decode_json_response_body(summary_response)
    data = payload if isinstance(payload, dict) else {}
    tasks = data.get("tasks") if isinstance(data.get("tasks"), list) else []
    rows_in = data.get("rows") if isinstance(data.get("rows"), list) else []
    task_meta = _live_task_meta_by_id([task for task in tasks if isinstance(task, dict)])
    rows: list[dict[str, object]] = []
    selected_student_panel: dict[str, object] | None = None
    row_average_values: list[float | None] = []
    submitted_cells = 0
    total_cells = 0

    for row in rows_in:
        if not isinstance(row, dict):
            continue
        student = row.get("student") if isinstance(row.get("student"), dict) else {}
        current_student_sub = str(student.get("sub") or "")
        student_name = str(
            student.get("name")
            or _live_dashboard_localpart_identifier(current_student_sub)
            or "Unbekannt"
        )
        row_cells = [cell for cell in (row.get("tasks") or []) if isinstance(cell, dict)]
        total_cells += len(row_cells)
        submitted_count = sum(1 for cell in row_cells if bool(cell.get("has_submission")))
        submitted_cells += submitted_count
        progress_percent = int(round((submitted_count / len(row_cells)) * 100)) if row_cells else 0
        average_score = _round_live_average([cell.get("average_score") for cell in row_cells])
        row_average_values.append(average_score)

        latest_submission: dict[str, object] | None = None
        latest_cell: dict[str, object] | None = None
        latest_created_at = ""
        for cell in row_cells:
            if not bool(cell.get("has_submission")):
                continue
            created_at = str(cell.get("created_at") or "")
            if created_at >= latest_created_at:
                latest_created_at = created_at
                latest_cell = cell

        if latest_cell is not None:
            latest_task_id = str(latest_cell.get("task_id") or "")
            meta = task_meta.get(latest_task_id, {"task_position": 0, "task_label": "Aufgabe"})
            latest_submission = {
                "task_id": latest_task_id,
                "task_position": int(meta["task_position"]),
                "task_label": str(meta["task_label"]),
                "created_at": latest_created_at,
                "average_score": latest_cell.get("average_score"),
            }

        row_href = _live_selection_href(course_id, unit_id, current_student_sub)
        row_payload = {
            "student": {
                "sub": current_student_sub,
                "name": student_name,
                "href": row_href,
            },
            "progress_percent": progress_percent,
            "average_score": average_score,
            "latest_submission": latest_submission,
            "href": row_href,
        }
        rows.append(row_payload)

        if student_sub and current_student_sub == student_sub:
            panel_tasks: list[dict[str, object]] = []
            latest_task_id = str(latest_submission.get("task_id") or "") if isinstance(latest_submission, dict) else ""
            for task in [task for task in tasks if isinstance(task, dict)]:
                current_task_id = str(task.get("id") or "")
                meta = task_meta.get(current_task_id, {"task_position": int(task.get("position") or 0), "task_label": "Aufgabe"})
                matching_cell = next((cell for cell in row_cells if str(cell.get("task_id") or "") == current_task_id), {})
                panel_tasks.append(
                    {
                        "task_id": current_task_id,
                        "task_position": int(meta["task_position"]),
                        "task_label": str(meta["task_label"]),
                        "has_submission": bool(matching_cell.get("has_submission")),
                        "average_score": matching_cell.get("average_score"),
                        "is_latest_submission": current_task_id == latest_task_id,
                        "href": _live_selection_href(course_id, unit_id, current_student_sub, current_task_id),
                    }
                )

            selected_task_id = str(task_id or "").strip() or latest_task_id or None

            selected_task_detail = None
            if selected_task_id:
                detail_result = teaching_routes.get_latest_submission_detail(
                    request,
                    course_id=course_id,
                    unit_id=unit_id,
                    task_id=selected_task_id,
                    student_sub=current_student_sub,
                )
                detail_response = await detail_result if inspect.isawaitable(detail_result) else detail_result
                if getattr(detail_response, "status_code", 500) == 200:
                    selected_task_detail = _decode_json_response_body(detail_response)

            selected_student_panel = {
                "student": {
                    "sub": current_student_sub,
                    "name": student_name,
                    "href": row_href,
                },
                "tasks": panel_tasks,
                "selected_task_id": selected_task_id,
                "selected_task_detail": selected_task_detail,
            }

    summary = {
        "learners_count": len(rows),
        "tasks_count": len(tasks),
        "completion_rate_percent": int(round((submitted_cells / total_cells) * 100)) if total_cells else 0,
        "average_score": _round_live_average(row_average_values),
    }

    body = {
        "user": _user_payload(user),
        "course": {
            "id": str(_field_value(course, "id") or ""),
            "title": str(_field_value(course, "title") or ""),
            "href": f"/live?course_id={course_id}",
        },
        "unit": {
            "id": str(unit.get("id") or ""),
            "title": str(unit.get("title") or ""),
            "position": int(unit.get("position") or 0),
            "href": f"/live?course_id={course_id}&unit_id={unit_id}",
        },
        "summary": summary,
        "rows": rows,
        "selected_student_panel": selected_student_panel,
    }
    return JSONResponse(body, headers=_private_headers())


@app_router.get("/api/live/views/courses/{course_id}/units/{unit_id}/detail-sheet")
async def get_live_detail_sheet(request: Request, course_id: str, unit_id: str, student_sub: str, task_id: str):
    """Return the live room detail sheet for one student-task selection."""
    user = _current_user(request)
    if user is None:
        return JSONResponse({"error": "unauthenticated"}, status_code=401, headers=_private_headers())
    if not has_any_role(user, {"teacher", "admin"}):
        return JSONResponse({"error": "forbidden"}, status_code=403, headers=_private_headers())

    owner_sub = str(user.get("sub") or "")
    guard = teaching_guards._guard_course_owner(
        course_id,
        owner_sub,
        repo_provider=teaching_routes._get_current_teaching_repo_for_provider,
    )
    if guard:
        return guard

    course = _get_teacher_course(course_id, owner_sub)
    if course is None:
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_private_headers())

    unit = _find_course_unit(course_id, owner_sub, unit_id)
    if unit is None:
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_private_headers())

    detail_result = teaching_routes.get_latest_submission_detail(
        request,
        course_id=course_id,
        unit_id=unit_id,
        task_id=task_id,
        student_sub=student_sub,
    )
    detail_response = await detail_result if inspect.isawaitable(detail_result) else detail_result
    status_code = getattr(detail_response, "status_code", 500)
    if status_code not in (200, 204):
        return detail_response

    submission = _decode_json_response_body(detail_response) if status_code == 200 else None
    names_result = teaching_routes.resolve_live_student_names_by_sub([student_sub])
    learner_names = await names_result if inspect.isawaitable(names_result) else names_result
    learner_name = str(learner_names.get(student_sub, student_sub))

    body = {
        "user": _user_payload(user),
        "course": {
            "id": str(_field_value(course, "id") or ""),
            "title": str(_field_value(course, "title") or ""),
            "href": f"/live/courses/{course_id}",
        },
        "unit": {
            "id": str(unit.get("id") or ""),
            "title": str(unit.get("title") or ""),
            "position": int(unit.get("position") or 0),
            "href": f"/live/courses/{course_id}/units/{unit_id}",
        },
        "student": {
            "sub": student_sub,
            "name": learner_name,
            "href": f"/live/courses/{course_id}/units/{unit_id}?student_sub={student_sub}",
        },
        "task": {
            "id": task_id,
            "href": f"/live/courses/{course_id}/units/{unit_id}?student_sub={student_sub}&task_id={task_id}",
        },
        "submission": submission,
    }
    return JSONResponse(body, headers=_private_headers())


@app_router.get("/api/diagnostics/views/learners/{student_sub:path}/profile")
async def get_diagnostics_learner_profile(request: Request, student_sub: str, limit: int = 50, offset: int = 0):
    """Return the first learner-scoped diagnostics profile for SvelteKit."""
    user = _current_user(request)
    if user is None:
        return JSONResponse({"error": "unauthenticated"}, status_code=401, headers=_private_headers())
    if not has_any_role(user, {"teacher", "admin"}):
        return JSONResponse({"error": "forbidden"}, status_code=403, headers=_private_headers())

    owner_sub = str(user.get("sub") or "")
    courses = _build_diagnostics_learner_profile_courses(
        student_sub,
        owner_sub,
        limit=int(limit or 50),
        offset=int(offset or 0),
    )
    if not courses:
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_private_headers())

    learner_names = teaching_routes.resolve_student_names([student_sub])
    learner_name = str(learner_names.get(student_sub, student_sub))
    body = {
        "user": _user_payload(user),
        "learner": {
            "sub": student_sub,
            "name": learner_name,
            "href": f"/diagnostics/learners/{student_sub}",
        },
        "summary": {
            "courses_count": len(courses),
            "submitted_tasks": sum(int(course.get("submitted_tasks") or 0) for course in courses),
            "total_tasks": sum(int(course.get("total_tasks") or 0) for course in courses),
        },
        "courses": courses,
    }
    return JSONResponse(body, headers=_private_headers())
