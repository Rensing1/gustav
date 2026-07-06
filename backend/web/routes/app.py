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
from backend.web.routes.app_diagnostics_routes import (
    app_diagnostics_router,
    get_diagnostics_course_matrix as get_diagnostics_course_matrix,  # noqa: F401
    get_diagnostics_learner_profile as get_diagnostics_learner_profile,  # noqa: F401
    _build_diagnostics_course_matrix_rows as _build_diagnostics_course_matrix_rows,  # noqa: F401
    _build_diagnostics_learner_profile_courses as _build_diagnostics_learner_profile_courses,  # noqa: F401
    _teacher_course_has_member as _teacher_course_has_member,  # noqa: F401
)
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
from backend.web.routes.app_teacher_node_editor_routes import (
    app_teacher_node_editor_router,
    get_teacher_unit_node_editor as get_teacher_unit_node_editor,  # noqa: F401
)
from backend.web.routes.app_teacher_unit_routes import (
    app_teacher_unit_router,
    get_teacher_units_catalog as get_teacher_units_catalog,  # noqa: F401
    get_teacher_unit_workspace as get_teacher_unit_workspace,  # noqa: F401
    _build_teacher_unit_course_refs as _build_teacher_unit_course_refs,  # noqa: F401
    _field_value as _field_value,  # noqa: F401
    _find_course_unit as _find_course_unit,  # noqa: F401
    _list_teacher_course_units as _list_teacher_course_units,  # noqa: F401
    _list_teacher_courses as _list_teacher_courses,  # noqa: F401
    _list_teacher_section_materials as _list_teacher_section_materials,  # noqa: F401
    _list_teacher_section_tasks as _list_teacher_section_tasks,  # noqa: F401
    _list_teacher_unit_edges as _list_teacher_unit_edges,  # noqa: F401
    _list_teacher_unit_modules as _list_teacher_unit_modules,  # noqa: F401
    _list_teacher_unit_phases as _list_teacher_unit_phases,  # noqa: F401
    _list_teacher_unit_sections as _list_teacher_unit_sections,  # noqa: F401
    _list_teacher_units as _list_teacher_units,  # noqa: F401
    _list_submission_pairs_for_students as _list_submission_pairs_for_students,  # noqa: F401
    _list_unit_task_ids as _list_unit_task_ids,  # noqa: F401
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
app_router.include_router(app_diagnostics_router)
app_router.include_router(app_profile_router)
app_router.include_router(app_teacher_concern_router)
app_router.include_router(app_teacher_course_router)
app_router.include_router(app_teacher_unit_router)
app_router.include_router(app_teacher_node_editor_router)


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
