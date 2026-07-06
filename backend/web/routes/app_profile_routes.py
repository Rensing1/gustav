"""Profile and CLI-token routes for the browser app."""

from __future__ import annotations

import importlib
import sys as _sys
from typing import Any

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


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


class ProfileNameLockedError(RuntimeError):
    """Raised when Vorname/Nachname are currently locked."""


def _app_module():
    module = _sys.modules.get("backend.web.routes.app")
    if module is None:  # pragma: no cover - defensive import fallback
        module = importlib.import_module("backend.web.routes.app")
    return module


def _current_user(request: Request) -> dict | None:
    return _app_module()._current_user(request)


def _private_headers() -> dict[str, str]:
    return _app_module()._private_headers()


def _current_claims(request: Request) -> dict[str, object]:
    return _app_module()._current_claims(request)


def _load_profile_identity(sub: str, claims: dict[str, object], request: Request | None = None) -> dict[str, object]:
    return _app_module()._load_profile_identity(sub, claims, request)


def _user_payload(user: dict) -> dict[str, object]:
    return _app_module()._user_payload(user)


def _update_profile_display_name(sub: str, display_name: str, request: Request | None = None) -> None:
    _app_module()._update_profile_display_name(sub, display_name, request)


def _update_profile_name(sub: str, first_name: str, last_name: str, request: Request | None = None) -> None:
    _app_module()._update_profile_name(sub, first_name, last_name, request)


def _cli_token_store(request: Request | None = None):
    return _app_module()._cli_token_store(request)


def _serialize_cli_token(record: Any) -> dict[str, object]:
    return _app_module()._serialize_cli_token(record)


@app_profile_router.get("/api/app/profile")
async def get_app_profile(request: Request):
    """Return the authenticated user's profile read-model."""

    user = _current_user(request)
    if user is None:
        return JSONResponse({"error": "unauthenticated"}, status_code=401, headers=_private_headers())

    claims = _current_claims(request)
    profile = _load_profile_identity(str(user.get("sub") or ""), claims, request)
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
async def patch_profile_display_name(request: Request, payload: ProfileDisplayNameUpdatePayload):
    """Update only the display name for the current user."""

    user = _current_user(request)
    if user is None:
        return JSONResponse({"error": "unauthenticated"}, status_code=401, headers=_private_headers())

    display_name = str(payload.display_name or "").strip()
    if not display_name:
        return JSONResponse({"error": "bad_request", "detail": "invalid_display_name"}, status_code=400, headers=_private_headers())

    _update_profile_display_name(str(user.get("sub") or ""), display_name, request)
    return Response(status_code=204, headers=_private_headers())


@app_profile_router.patch("/api/app/profile/name")
async def patch_profile_name(request: Request, payload: ProfileNameUpdatePayload):
    """Update Vorname/Nachname for the current user."""

    user = _current_user(request)
    if user is None:
        return JSONResponse({"error": "unauthenticated"}, status_code=401, headers=_private_headers())

    first_name = str(payload.first_name or "").strip()
    last_name = str(payload.last_name or "").strip()
    if not first_name and not last_name:
        return JSONResponse({"error": "bad_request", "detail": "invalid_name"}, status_code=400, headers=_private_headers())

    try:
        _update_profile_name(str(user.get("sub") or ""), first_name, last_name, request)
    except ProfileNameLockedError as exc:
        return JSONResponse(
            {"error": "name_locked", "detail": str(exc)},
            status_code=409,
            headers=_private_headers(),
        )
    return Response(status_code=204, headers=_private_headers())


@app_profile_router.get("/api/app/profile/cli-tokens")
async def list_profile_cli_tokens(request: Request):
    """Return CLI token metadata for the current user without raw token values."""

    user = _current_user(request)
    if user is None:
        return JSONResponse({"error": "unauthenticated"}, status_code=401, headers=_private_headers())
    records = _cli_token_store(request).list_tokens(str(user.get("sub") or ""))
    return JSONResponse([_serialize_cli_token(record) for record in records], headers=_private_headers())


@app_profile_router.post("/api/app/profile/cli-tokens")
async def create_profile_cli_token(request: Request, payload: CLITokenCreatePayload):
    """Create a CLI token and return the raw token exactly once."""

    user = _current_user(request)
    if user is None:
        return JSONResponse({"error": "unauthenticated"}, status_code=401, headers=_private_headers())
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
async def revoke_profile_cli_token(request: Request, token_id: str):
    """Revoke one CLI token owned by the current user."""

    user = _current_user(request)
    if user is None:
        return JSONResponse({"error": "unauthenticated"}, status_code=401, headers=_private_headers())
    ok = _cli_token_store(request).revoke_token(user_sub=str(user.get("sub") or ""), token_id=token_id)
    if not ok:
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_private_headers())
    return Response(status_code=204, headers=_private_headers())
