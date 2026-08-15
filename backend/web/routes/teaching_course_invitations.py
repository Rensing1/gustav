"""HTTP adapter for secure, time-limited course invitations.

Why:
    Teachers need one owner-scoped management surface while learners need a
    deliberately small capability surface. Token verification happens before
    any database lookup so malformed or forged capabilities fail closed.
"""

from __future__ import annotations

import os
import secrets
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from backend.teaching.course_invitations import (
    InvitationTokenError,
    build_invitation_token,
    normalize_invitation_recipients,
    parse_invitation_token,
    recipient_digest,
)
from backend.teaching.errors import TeachingRepositoryUnavailable
from backend.web.routes import teaching_guards
from backend.web.routes.teaching import _get_repo
from backend.web.routes.teaching_payloads import (
    CourseInvitationEmailPayload,
    CourseInvitationTokenPayload,
)
from backend.web.routes.teaching_shared import _current_sub, _json_private, _private_error, _role_in


teaching_course_invitations_router = APIRouter(tags=["Teaching"])


def _secret() -> str:
    """Return the dedicated invite secret or fail before exposing capability data."""

    return os.getenv("COURSE_INVITE_SIGNING_SECRET", "")


def _public_response(payload: dict[str, Any], *, status_code: int) -> JSONResponse:
    """Return a non-cacheable response that never forwards capability fragments."""

    return JSONResponse(
        payload,
        status_code=status_code,
        headers={"Cache-Control": "private, no-store", "Referrer-Policy": "no-referrer"},
    )


def _parse_token(payload: CourseInvitationTokenPayload) -> tuple[str, str] | None:
    """Validate the signed token and return string values suitable for psycopg."""

    if not isinstance(payload.token, str):
        return None
    try:
        invitation_id, nonce = parse_invitation_token(payload.token, _secret())
    except InvitationTokenError:
        return None
    return str(invitation_id), nonce


def _invite_url(request: Request, invitation: dict[str, Any]) -> str:
    """Build the browser link with the capability in the URL fragment."""

    base = (os.getenv("WEB_BASE") or str(request.base_url)).rstrip("/")
    token = build_invitation_token(invitation["id"], invitation["token_nonce"], _secret())
    return f"{base}/invite#{token}"


def _serialize_invitation(request: Request, invitation: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": invitation["id"],
        "course_id": invitation["course_id"],
        "invite_url": _invite_url(request, invitation),
        "expires_at": invitation["expires_at"],
        "created_at": invitation["created_at"],
        "redemption_count": invitation.get("redemption_count", 0),
        "email_status": invitation.get(
            "email_status", {"pending": 0, "sent": 0, "failed": 0}
        ),
    }


def _owner_context(request: Request, course_id: str):
    """Authorize one invitation-management operation for the course owner."""

    user = getattr(request.state, "user", None)
    owner_sub = _current_sub(user)
    if not _role_in(user, "teacher"):
        return None, _private_error({"error": "forbidden"}, status_code=403)
    guard = teaching_guards._guard_course_owner(course_id, owner_sub, repo_provider=_get_repo)
    if guard:
        return None, guard
    return (_get_repo(), owner_sub), None


@teaching_course_invitations_router.post("/api/teaching/courses/{course_id}/invitations")
async def create_course_invitation(request: Request, course_id: str):
    """Create a 24-hour invitation and atomically revoke the previous one."""

    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    context, error = _owner_context(request, course_id)
    if error:
        return error
    repo, owner_sub = context
    if not hasattr(repo, "create_course_invitation"):
        return _private_error({"error": "service_unavailable"}, status_code=503)
    try:
        invitation = repo.create_course_invitation(
            course_id, owner_sub, secrets.token_urlsafe(32)
        )
        if not invitation:
            return _private_error({"error": "not_found"}, status_code=404)
        return _json_private(
            _serialize_invitation(request, invitation), status_code=201, vary_origin=True
        )
    except InvitationTokenError:
        return _private_error({"error": "service_unavailable"}, status_code=503)
    except TeachingRepositoryUnavailable:
        raise
    except Exception as exc:
        detail = str(exc)
        if "course_metadata_incomplete" in detail:
            return _private_error(
                {"error": "conflict", "detail": "course_metadata_incomplete"}, status_code=409
            )
        if "course_not_active" in detail:
            return _private_error(
                {"error": "conflict", "detail": "course_not_active"}, status_code=409
            )
        return _private_error({"error": "forbidden"}, status_code=403)


@teaching_course_invitations_router.get(
    "/api/teaching/courses/{course_id}/invitations/active"
)
async def get_active_course_invitation(request: Request, course_id: str):
    """Return the owner's current valid invitation and aggregate status."""

    context, error = _owner_context(request, course_id)
    if error:
        return error
    repo, owner_sub = context
    if not hasattr(repo, "get_active_course_invitation"):
        return _private_error({"error": "service_unavailable"}, status_code=503)
    invitation = repo.get_active_course_invitation(course_id, owner_sub)
    if not invitation:
        return _private_error({"error": "not_found"}, status_code=404)
    try:
        return _json_private(_serialize_invitation(request, invitation))
    except InvitationTokenError:
        return _private_error({"error": "service_unavailable"}, status_code=503)


@teaching_course_invitations_router.delete(
    "/api/teaching/courses/{course_id}/invitations/{invitation_id}"
)
async def revoke_course_invitation(request: Request, course_id: str, invitation_id: str):
    """Immediately revoke an owner-managed invitation."""

    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    context, error = _owner_context(request, course_id)
    if error:
        return error
    repo, owner_sub = context
    if not hasattr(repo, "revoke_course_invitation"):
        return _private_error({"error": "service_unavailable"}, status_code=503)
    changed = repo.revoke_course_invitation(course_id, invitation_id, owner_sub)
    if not changed:
        return _private_error({"error": "not_found"}, status_code=404)
    return Response(status_code=204, headers={"Cache-Control": "private, no-store"})


@teaching_course_invitations_router.post(
    "/api/teaching/courses/{course_id}/invitations/{invitation_id}/email-deliveries"
)
async def queue_course_invitation_emails(
    request: Request,
    course_id: str,
    invitation_id: str,
    payload: CourseInvitationEmailPayload,
):
    """Validate school addresses and enqueue isolated, deduplicated deliveries."""

    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    context, error = _owner_context(request, course_id)
    if error:
        return error
    repo, owner_sub = context
    try:
        recipients = normalize_invitation_recipients(
            payload.recipients,
            allowed_domains=os.getenv("ALLOWED_REGISTRATION_DOMAINS"),
        )
        deliveries = [
            {
                "email": email,
                "digest": recipient_digest(email, invitation_id, _secret()),
            }
            for email in recipients
        ]
    except (ValueError, InvitationTokenError) as exc:
        return _private_error(
            {"error": "bad_request", "detail": str(exc)}, status_code=400, vary_origin=True
        )
    if not hasattr(repo, "queue_course_invite_mail_batch"):
        return _private_error({"error": "service_unavailable"}, status_code=503)
    result = repo.queue_course_invite_mail_batch(
        course_id, invitation_id, owner_sub, deliveries
    )
    if not result:
        return _private_error({"error": "not_found"}, status_code=404)
    return _json_private(result, status_code=202, vary_origin=True)


@teaching_course_invitations_router.get(
    "/api/teaching/courses/{course_id}/invitations/{invitation_id}/email-deliveries/status"
)
async def get_course_invitation_email_status(
    request: Request, course_id: str, invitation_id: str
):
    """Return only aggregate status and still-needed failed addresses."""

    context, error = _owner_context(request, course_id)
    if error:
        return error
    repo, owner_sub = context
    if not hasattr(repo, "get_course_invite_mail_status"):
        return _private_error({"error": "service_unavailable"}, status_code=503)
    status = repo.get_course_invite_mail_status(course_id, invitation_id, owner_sub)
    if status is None:
        return _private_error({"error": "not_found"}, status_code=404)
    return _json_private(status)


@teaching_course_invitations_router.post(
    "/api/teaching/courses/{course_id}/invitations/{invitation_id}/email-deliveries/retry"
)
async def retry_course_invitation_emails(
    request: Request, course_id: str, invitation_id: str
):
    """Requeue retryable failures without extending invitation validity."""

    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    context, error = _owner_context(request, course_id)
    if error:
        return error
    repo, owner_sub = context
    if not hasattr(repo, "retry_course_invite_mail_deliveries"):
        return _private_error({"error": "service_unavailable"}, status_code=503)
    queued = repo.retry_course_invite_mail_deliveries(course_id, invitation_id, owner_sub)
    if queued is None:
        return _private_error({"error": "not_found"}, status_code=404)
    return _json_private({"queued": queued}, status_code=202, vary_origin=True)


@teaching_course_invitations_router.post("/api/course-invitations/preview")
async def preview_course_invitation(
    request: Request, payload: CourseInvitationTokenPayload
):
    """Resolve a valid capability to title and expiry, and nothing else."""

    parsed = _parse_token(payload)
    if not parsed:
        return _public_response({"error": "not_found"}, status_code=404)
    repo = _get_repo()
    if not hasattr(repo, "preview_course_invitation"):
        return _public_response({"error": "service_unavailable"}, status_code=503)
    invitation_id, nonce = parsed
    preview = repo.preview_course_invitation(invitation_id, nonce)
    if not preview:
        return _public_response({"error": "not_found"}, status_code=404)
    return _public_response(preview, status_code=200)


@teaching_course_invitations_router.post("/api/course-invitations/redeem")
async def redeem_course_invitation(
    request: Request, payload: CourseInvitationTokenPayload
):
    """Redeem a capability for an authenticated learner only."""

    user = getattr(request.state, "user", None)
    if not _role_in(user, "student") or _role_in(user, "teacher") or _role_in(user, "admin"):
        return _public_response({"error": "forbidden"}, status_code=403)
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        csrf.headers["Referrer-Policy"] = "no-referrer"
        return csrf
    parsed = _parse_token(payload)
    if not parsed:
        return _public_response({"error": "not_found"}, status_code=404)
    repo = _get_repo()
    if not hasattr(repo, "redeem_course_invitation"):
        return _public_response({"error": "service_unavailable"}, status_code=503)
    invitation_id, nonce = parsed
    try:
        result = repo.redeem_course_invitation(
            invitation_id, nonce, _current_sub(user)
        )
    except TeachingRepositoryUnavailable:
        raise
    except Exception as exc:
        if "invite_already_used_membership_removed" in str(exc):
            return _public_response(
                {
                    "error": "conflict",
                    "detail": "invite_already_used_membership_removed",
                },
                status_code=409,
            )
        return _public_response({"error": "forbidden"}, status_code=403)
    if not result:
        return _public_response({"error": "not_found"}, status_code=404)
    status_code = 201 if result["result"] == "joined" else 200
    result["course_href"] = f"/learning/courses/{result['course_id']}"
    return _public_response(result, status_code=status_code)
