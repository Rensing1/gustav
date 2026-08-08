"""Application-level read-model routes for the new web platform.

Why:
    SvelteKit needs a small shell bootstrap payload that is independent from
    legacy SSR concerns. This router is the first explicit room read-model
    endpoint in the FastAPI adapter.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.identity_access.admin_client import AdminClient
from backend.identity_access.cli_tokens import CLITokenRecord
from backend.identity_access.tokens import verify_bearer_token
from backend.web.auth_session import SESSION_COOKIE_NAME, app_session_ttl_seconds, set_session_cookie
from backend.web.security.guards import has_any_role as has_any_role  # noqa: F401
from backend.web.routes import teaching as teaching_routes  # noqa: F401
from backend.web.routes import teaching_guards as teaching_guards  # noqa: F401
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
from backend.web.routes.app_live_routes import (
    app_live_router,
    get_live_course_units as get_live_course_units,  # noqa: F401
    get_live_detail_sheet as get_live_detail_sheet,  # noqa: F401
    get_live_unit_dashboard as get_live_unit_dashboard,  # noqa: F401
    get_live_unit_matrix as get_live_unit_matrix,  # noqa: F401
    _decode_json_response_body as _decode_json_response_body,  # noqa: F401
    _live_dashboard_localpart_identifier as _live_dashboard_localpart_identifier,  # noqa: F401
    _live_selection_href as _live_selection_href,  # noqa: F401
    _live_task_meta_by_id as _live_task_meta_by_id,  # noqa: F401
    _round_live_average as _round_live_average,  # noqa: F401
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
from backend.learning.practice.config import practice_sessions_enabled
from backend.web.routes.app_teacher_concern_routes import (
    app_teacher_concern_router,
    archive_teacher_concern_box_entry as archive_teacher_concern_box_entry,  # noqa: F401
    get_teacher_concern_box as get_teacher_concern_box,  # noqa: F401
    get_teacher_home as get_teacher_home,  # noqa: F401
    restore_teacher_concern_box_entry as restore_teacher_concern_box_entry,  # noqa: F401
    _teacher_concern_box_scopes as _teacher_concern_box_scopes,  # noqa: F401
    _teacher_home_workstarter as _teacher_home_workstarter,  # noqa: F401
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
    _teacher_units_catalog as _teacher_units_catalog,  # noqa: F401
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
app_router.include_router(app_live_router)
app_router.include_router(app_diagnostics_router)
app_router.include_router(app_profile_router)
app_router.include_router(app_teacher_concern_router)
app_router.include_router(app_teacher_course_router)
app_router.include_router(app_teacher_unit_router)
app_router.include_router(app_teacher_node_editor_router)

# Active Live API H5P matrix fields (`score_raw`, `score_max`, `h5p_completed`)
# live in `backend.web.routes.app_live_routes`; this source-level note keeps
# the legacy contract pointing at the App facade honest during the split.


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
        "practice_enabled": practice_sessions_enabled(),
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
