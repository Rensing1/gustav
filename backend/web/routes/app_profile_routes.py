"""Profile and CLI-token routes for the browser app."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import cast

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.identity_access.cli_tokens import CLITokenRecord, ProfileCLITokenStore
from backend.identity_access.profile import ProfileNameLockedError, ProfileService
from backend.identity_access.unified_sessions import SessionUnavailable
from backend.web.profile_providers import profile_providers
from backend.web.routes.app_session_helpers import current_user as _current_user
from backend.web.routes.app_session_helpers import private_headers as _private_headers
from backend.web.routes.app_session_helpers import user_payload as _user_payload

# These handlers perform synchronous identity/DB I/O. FastAPI runs ordinary
# def handlers in its bounded threadpool, keeping the event loop responsive.
app_profile_router = APIRouter(tags=["App"])


class ProfileDisplayNameUpdatePayload(BaseModel):
    display_name: str = Field(min_length=1, max_length=80)


class ProfileNameUpdatePayload(BaseModel):
    first_name: str = Field(default="", max_length=80)
    last_name: str = Field(default="", max_length=80)


class CLITokenCreatePayload(BaseModel):
    # Keep validation handler-side so the API returns the documented 400 shape
    # instead of FastAPI's framework-level 422 payload.
    label: object | None = None
    scopes: object | None = None
    ttl_days: object | None = 30


def _profile_service(request: Request) -> ProfileService:
    return ProfileService(profile_providers(request).identity())


def _cli_token_store(request: Request) -> ProfileCLITokenStore:
    # Management and bearer authentication must use the same app-owned store.
    return cast(ProfileCLITokenStore, request.app.state.runtime.cli_token_store)


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
        claims = profile_providers(request).verify_claims(token)
    except Exception:
        return {}
    return claims if isinstance(claims, dict) else {}


def _require_cli_token_teacher(request: Request) -> tuple[dict | None, JSONResponse | None]:
    """Authorize CLI-token management for an authenticated teacher.

    The check runs before any token-store access so students cannot enumerate,
    create, or revoke CLI credentials even when they call the API directly.
    """

    user = _current_user(request)
    if user is None:
        return None, JSONResponse({"error": "unauthenticated"}, status_code=401, headers=_private_headers())
    roles = user.get("roles") or []
    if not isinstance(roles, list) or "teacher" not in roles:
        return None, JSONResponse({"error": "forbidden"}, status_code=403, headers=_private_headers())
    return user, None


@app_profile_router.get("/api/app/profile")
def get_app_profile(request: Request):
    """Return the authenticated user's profile read-model."""

    user = _current_user(request)
    if user is None:
        return JSONResponse({"error": "unauthenticated"}, status_code=401, headers=_private_headers())

    claims = _current_claims(request)
    profile = _profile_service(request).load(str(user.get("sub") or ""), claims)
    body = {
        "user": _user_payload(user),
        "display_name": str(profile.get("display_name") or ""),
        "email": str(profile.get("email") or ""),
        "first_name": str(profile.get("first_name") or ""),
        "last_name": str(profile.get("last_name") or ""),
        "name_locked_until": profile.get("name_locked_until"),
        "name_can_edit": bool(profile.get("name_can_edit")),
        "password_change_href": "/auth/password",
    }
    return JSONResponse(body, headers=_private_headers())


@app_profile_router.patch("/api/app/profile/display-name")
def patch_profile_display_name(request: Request, payload: ProfileDisplayNameUpdatePayload):
    """Update only the display name for the current user."""

    user = _current_user(request)
    if user is None:
        return JSONResponse({"error": "unauthenticated"}, status_code=401, headers=_private_headers())

    display_name = str(payload.display_name or "").strip()
    if not display_name:
        return JSONResponse({"error": "bad_request", "detail": "invalid_display_name"}, status_code=400, headers=_private_headers())

    _profile_service(request).update_display_name(str(user.get("sub") or ""), display_name)
    try:
        request.app.state.runtime.session_store.update_display_name(str(user["sub"]), display_name)
    except SessionUnavailable:
        return JSONResponse({"error": "auth_unavailable"}, status_code=503, headers=_private_headers())
    return Response(status_code=204, headers=_private_headers())


@app_profile_router.patch("/api/app/profile/name")
def patch_profile_name(request: Request, payload: ProfileNameUpdatePayload):
    """Update Vorname/Nachname for the current user."""

    user = _current_user(request)
    if user is None:
        return JSONResponse({"error": "unauthenticated"}, status_code=401, headers=_private_headers())

    first_name = str(payload.first_name or "").strip()
    last_name = str(payload.last_name or "").strip()
    if not first_name and not last_name:
        return JSONResponse({"error": "bad_request", "detail": "invalid_name"}, status_code=400, headers=_private_headers())

    try:
        _profile_service(request).update_name(str(user.get("sub") or ""), first_name, last_name)
    except ProfileNameLockedError as exc:
        return JSONResponse(
            {"error": "name_locked", "detail": str(exc)},
            status_code=409,
            headers=_private_headers(),
        )
    return Response(status_code=204, headers=_private_headers())


@app_profile_router.get("/api/app/profile/cli-tokens")
def list_profile_cli_tokens(request: Request):
    """Return the current teacher's CLI-token metadata without raw values."""

    user, error = _require_cli_token_teacher(request)
    if error is not None:
        return error
    assert user is not None
    records = _cli_token_store(request).list_tokens(str(user.get("sub") or ""))
    return JSONResponse([_serialize_cli_token(record) for record in records], headers=_private_headers())


@app_profile_router.post("/api/app/profile/cli-tokens")
def create_profile_cli_token(request: Request, payload: CLITokenCreatePayload):
    """Create a CLI token for the current teacher and return it exactly once."""

    user, error = _require_cli_token_teacher(request)
    if error is not None:
        return error
    assert user is not None
    label_value = payload.label
    label = label_value.strip() if isinstance(label_value, str) else ""
    if not label or len(label) > 80:
        return JSONResponse({"error": "bad_request", "detail": "invalid_label"}, status_code=400, headers=_private_headers())
    scopes_value = payload.scopes
    if not isinstance(scopes_value, list) or not scopes_value:
        return JSONResponse(
            {"error": "bad_request", "detail": "invalid_cli_token_scopes"},
            status_code=400,
            headers=_private_headers(),
        )
    ttl_days = payload.ttl_days
    if isinstance(ttl_days, bool) or not isinstance(ttl_days, int) or ttl_days < 1 or ttl_days > 90:
        return JSONResponse(
            {"error": "bad_request", "detail": "invalid_ttl_days"},
            status_code=400,
            headers=_private_headers(),
        )
    try:
        created = _cli_token_store(request).create_token(
            user_sub=str(user.get("sub") or ""),
            label=label,
            scopes=[str(scope) for scope in scopes_value],
            ttl_seconds=ttl_days * 24 * 60 * 60,
        )
    except ValueError as exc:
        return JSONResponse({"error": "bad_request", "detail": str(exc)}, status_code=400, headers=_private_headers())
    return JSONResponse(
        {"token": created.raw_token, "record": _serialize_cli_token(created.record)},
        status_code=201,
        headers=_private_headers(),
    )


@app_profile_router.delete("/api/app/profile/cli-tokens/{token_id}")
def revoke_profile_cli_token(request: Request, token_id: str):
    """Revoke one CLI token owned by the current teacher."""

    user, error = _require_cli_token_teacher(request)
    if error is not None:
        return error
    assert user is not None
    ok = _cli_token_store(request).revoke_token(user_sub=str(user.get("sub") or ""), token_id=token_id)
    if not ok:
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_private_headers())
    return Response(status_code=204, headers=_private_headers())
