"""Application-level read-model routes for the new web platform.

Why:
    SvelteKit needs a small shell bootstrap payload that is independent from
    legacy SSR concerns. This router is the first explicit room read-model
    endpoint in the FastAPI adapter.
"""

from __future__ import annotations

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.identity_access.admin_client import AdminClient  # noqa: F401 - remaining live facade
from backend.web.auth_session import (
    SESSION_COOKIE_NAME,
    app_session_ttl_seconds,
    set_session_cookie,
)
from backend.web.routes import teaching as teaching_routes  # noqa: F401
from backend.web.routes import teaching_guards as teaching_guards  # noqa: F401
from backend.web.routes.app_concern_box_routes import app_concern_box_router
from backend.web.routes.app_diagnostics_routes import (
    _build_diagnostics_course_matrix_rows as _build_diagnostics_course_matrix_rows,  # noqa: F401
)
from backend.web.routes.app_diagnostics_routes import (
    _build_diagnostics_learner_profile_courses as _build_diagnostics_learner_profile_courses,  # noqa: F401
)
from backend.web.routes.app_diagnostics_routes import (
    _teacher_course_has_member as _teacher_course_has_member,  # noqa: F401
)
from backend.web.routes.app_diagnostics_routes import (
    app_diagnostics_router,
)
from backend.web.routes.app_diagnostics_routes import (
    get_diagnostics_course_matrix as get_diagnostics_course_matrix,  # noqa: F401
)
from backend.web.routes.app_diagnostics_routes import (
    get_diagnostics_learner_profile as get_diagnostics_learner_profile,  # noqa: F401
)
from backend.web.routes.app_learner_view_routes import (
    app_learner_view_router,
)
from backend.web.routes.app_live_routes import (
    _decode_json_response_body as _decode_json_response_body,  # noqa: F401
)
from backend.web.routes.app_live_routes import (
    _live_dashboard_localpart_identifier as _live_dashboard_localpart_identifier,  # noqa: F401
)
from backend.web.routes.app_live_routes import (
    _live_selection_href as _live_selection_href,  # noqa: F401
)
from backend.web.routes.app_live_routes import (
    _live_task_meta_by_id as _live_task_meta_by_id,  # noqa: F401
)
from backend.web.routes.app_live_routes import (
    _round_live_average as _round_live_average,  # noqa: F401
)
from backend.web.routes.app_live_routes import (
    app_live_router,
)
from backend.web.routes.app_live_routes import (
    get_live_course_units as get_live_course_units,  # noqa: F401
)
from backend.web.routes.app_live_routes import (
    get_live_detail_sheet as get_live_detail_sheet,  # noqa: F401
)
from backend.web.routes.app_live_routes import (
    get_live_unit_dashboard as get_live_unit_dashboard,  # noqa: F401
)
from backend.web.routes.app_live_routes import (
    get_live_unit_matrix as get_live_unit_matrix,  # noqa: F401
)
from backend.web.routes.app_profile_routes import app_profile_router
from backend.web.routes.app_session_helpers import (
    bff_session_payload as _bff_session_payload,
)
from backend.web.routes.app_session_helpers import (
    bff_session_store as _bff_session_store,
)
from backend.web.routes.app_session_helpers import (
    current_user as _current_user,
)
from backend.web.routes.app_session_helpers import (
    internal_bff_secret_configured as _internal_bff_secret_configured,  # noqa: F401
)
from backend.web.routes.app_session_helpers import (
    oidc_config as _oidc_config,  # noqa: F401 - remaining session facade
)
from backend.web.routes.app_session_helpers import (
    private_headers as _private_headers,
)
from backend.web.routes.app_session_helpers import (
    require_internal_bff_secret as _require_internal_bff_secret,
)
from backend.web.routes.app_session_helpers import (
    runtime_from_request as _runtime_from_request,  # noqa: F401 - remaining session facade
)
from backend.web.routes.app_session_helpers import (
    runtime_settings as _runtime_settings,
)
from backend.web.routes.app_session_helpers import (
    session_store as _session_store,
)
from backend.web.routes.app_session_helpers import (
    spaces_for_role as _spaces_for_role,
)
from backend.web.routes.app_session_helpers import (
    start_target_for_role as _start_target_for_role,
)
from backend.web.routes.app_session_helpers import (
    user_payload as _user_payload,
)
from backend.web.routes.app_teacher_catalog_routes import app_teacher_catalog_router
from backend.web.routes.app_teacher_concern_routes import (
    app_teacher_concern_router,
)
from backend.web.routes.app_teacher_course_routes import (
    _build_usage_totals as _build_usage_totals,  # noqa: F401
)
from backend.web.routes.app_teacher_course_routes import (
    _count_teacher_course_members as _count_teacher_course_members,  # noqa: F401
)
from backend.web.routes.app_teacher_course_routes import (
    _empty_usage_totals as _empty_usage_totals,  # noqa: F401
)
from backend.web.routes.app_teacher_course_routes import (
    _get_teacher_course as _get_teacher_course,  # noqa: F401
)
from backend.web.routes.app_teacher_course_routes import (
    _list_teacher_course_ai_usage_events as _list_teacher_course_ai_usage_events,  # noqa: F401
)
from backend.web.routes.app_teacher_course_routes import (
    _list_teacher_course_cards as _list_teacher_course_cards,  # noqa: F401
)
from backend.web.routes.app_teacher_course_routes import (
    _list_teacher_course_members as _list_teacher_course_members,  # noqa: F401
)
from backend.web.routes.app_teacher_course_routes import (
    _list_teacher_course_members_window as _list_teacher_course_members_window,  # noqa: F401
)
from backend.web.routes.app_teacher_course_routes import (
    _parse_usage_filter_timestamp as _parse_usage_filter_timestamp,  # noqa: F401
)
from backend.web.routes.app_teacher_course_routes import (
    app_teacher_course_router,
)
from backend.web.routes.app_teacher_course_routes import (
    get_teacher_course_ai_usage as get_teacher_course_ai_usage,  # noqa: F401
)
from backend.web.routes.app_teacher_course_routes import (
    get_teacher_course_context as get_teacher_course_context,  # noqa: F401
)
from backend.web.routes.app_teacher_course_routes import (
    get_teacher_course_list as get_teacher_course_list,  # noqa: F401
)
from backend.web.routes.app_teacher_node_editor_routes import (
    app_teacher_node_editor_router,
)
from backend.web.routes.app_teacher_node_editor_routes import (
    get_teacher_unit_node_editor as get_teacher_unit_node_editor,  # noqa: F401
)
from backend.web.routes.app_teacher_unit_routes import (
    _build_teacher_unit_course_refs as _build_teacher_unit_course_refs,  # noqa: F401
)
from backend.web.routes.app_teacher_unit_routes import (
    _field_value as _field_value,  # noqa: F401
)
from backend.web.routes.app_teacher_unit_routes import (
    _find_course_unit as _find_course_unit,  # noqa: F401
)
from backend.web.routes.app_teacher_unit_routes import (
    _list_submission_pairs_for_students as _list_submission_pairs_for_students,  # noqa: F401
)
from backend.web.routes.app_teacher_unit_routes import (
    _list_teacher_course_units as _list_teacher_course_units,  # noqa: F401
)
from backend.web.routes.app_teacher_unit_routes import (
    _list_teacher_courses as _list_teacher_courses,  # noqa: F401
)
from backend.web.routes.app_teacher_unit_routes import (
    _list_teacher_section_materials as _list_teacher_section_materials,  # noqa: F401
)
from backend.web.routes.app_teacher_unit_routes import (
    _list_teacher_section_tasks as _list_teacher_section_tasks,  # noqa: F401
)
from backend.web.routes.app_teacher_unit_routes import (
    _list_teacher_unit_edges as _list_teacher_unit_edges,  # noqa: F401
)
from backend.web.routes.app_teacher_unit_routes import (
    _list_teacher_unit_modules as _list_teacher_unit_modules,  # noqa: F401
)
from backend.web.routes.app_teacher_unit_routes import (
    _list_teacher_unit_phases as _list_teacher_unit_phases,  # noqa: F401
)
from backend.web.routes.app_teacher_unit_routes import (
    _list_teacher_unit_sections as _list_teacher_unit_sections,  # noqa: F401
)
from backend.web.routes.app_teacher_unit_routes import (
    _list_unit_task_ids as _list_unit_task_ids,  # noqa: F401
)
from backend.web.routes.app_teacher_unit_routes import (
    app_teacher_unit_router,
)
from backend.web.routes.app_teacher_unit_routes import (
    get_teacher_unit_workspace as get_teacher_unit_workspace,  # noqa: F401
)
from backend.web.security.guards import has_any_role as has_any_role  # noqa: F401

app_router = APIRouter(tags=["App"])
app_router.include_router(app_learner_view_router)
app_router.include_router(app_live_router)
app_router.include_router(app_diagnostics_router)
app_router.include_router(app_profile_router)
app_router.include_router(app_teacher_concern_router)
app_router.include_router(app_teacher_catalog_router)
app_router.include_router(app_concern_box_router)
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
