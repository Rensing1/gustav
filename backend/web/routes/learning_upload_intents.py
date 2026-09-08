"""Learning upload-intent routes.

Why:
    Upload intents combine CSRF checks, student authorization, task-kind MIME
    policy, storage-key generation, lazy storage wiring, and optional same-
    origin proxying. Keeping this route in a focused module reduces the
    Learning route hotspot while preserving the public API contract.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote as _quote
from urllib.parse import urlparse as _urlparse
from uuid import UUID
from uuid import uuid4 as _uuid4

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.learning.usecases.submissions import ListSubmissionsInput, ListSubmissionsUseCase
from backend.storage.config import get_learning_max_upload_bytes as _max_upload_bytes
from backend.storage.config import get_submissions_bucket as _storage_bucket
from backend.storage.keys import make_submission_key
from backend.storage.learning_policy import ALLOWED_IMAGE_MIME
from backend.storage.mime_types import (
    FILIUS_FLS_MIME,
    JPEG_MIME,
    MAKECODE_HEX_MIME,
    PDF_MIME,
    PNG_MIME,
    SCRATCH_SB3_MIME,
)
from backend.storage.upload_intents import normalize_upload_intent_headers
from backend.teaching.storage import NullStorageAdapter
from backend.web.learning_upload_intent_providers import learning_upload_intent_providers
from backend.web.routes.app_session_helpers import current_user as _current_user
from backend.web.routes.learning_upload_config import (
    dev_upload_stub_enabled as _dev_upload_stub_enabled,
)
from backend.web.routes.learning_upload_config import (
    upload_intent_ttl_seconds as _upload_intent_ttl_seconds,
)
from backend.web.routes.learning_upload_config import (
    upload_proxy_enabled as _upload_proxy_enabled,
)
from backend.web.routes.learning_upload_proxy import encode_proxy_headers as _encode_proxy_headers
from backend.web.routes.security import _is_same_origin

learning_upload_intents_router = APIRouter(tags=["Learning"])


def _cache_headers_success() -> dict[str, str]:
    """Never cache private authorization or signing responses."""
    return {"Cache-Control": "private, no-store", "Vary": "Origin"}


_cache_headers_error = _cache_headers_success


def _require_strict_same_origin(request: Request) -> bool:
    """Require a present, matching Origin/Referer before any adapter access."""
    return bool(request.headers.get("origin") or request.headers.get("referer")) and _is_same_origin(request)


@learning_upload_intents_router.post("/api/learning/courses/{course_id}/tasks/{task_id}/upload-intents")
def create_upload_intent(request: Request, course_id: str, task_id: str, payload: dict[str, Any]):
    """Authorize and sign an upload for the student's task using one DB adapter.

    Parameters are the authenticated request, course/task UUIDs and file metadata.
    Require the student role and same origin before resolving the repository.
    Membership and current task visibility remain enforced by the existing
    use case and DB adapter. Sign only after authorization and MIME validation;
    failures retain the existing private HTTP responses. Synchronous database
    and storage work runs in FastAPI's bounded threadpool.
    """

    user = _current_user(request)
    if not user:
        return JSONResponse({"error": "unauthenticated"}, status_code=401, headers=_cache_headers_error())
    roles = user.get("roles") or []
    if not isinstance(roles, list) or "student" not in roles:
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_cache_headers_error())
    if not _require_strict_same_origin(request):
        return JSONResponse(
            {"error": "forbidden", "detail": "csrf_violation"},
            status_code=403,
            headers=_cache_headers_error(),
        )

    try:
        UUID(course_id)
        UUID(task_id)
    except ValueError:
        return JSONResponse({"error": "bad_request", "detail": "invalid_uuid"}, status_code=400, headers=_cache_headers_error())

    if not isinstance(payload, dict):
        return JSONResponse({"error": "bad_request", "detail": "invalid_input"}, status_code=400, headers=_cache_headers_error())
    kind = payload.get("kind")
    filename = str(payload.get("filename") or "").strip()
    mime_type = str(payload.get("mime_type") or "").strip().lower()
    size_bytes = payload.get("size_bytes")
    try:
        size_int = int(size_bytes)
    except Exception:
        return JSONResponse({"error": "bad_request", "detail": "invalid_input"}, status_code=400, headers=_cache_headers_error())
    if not filename or len(filename) > 255:
        return JSONResponse({"error": "bad_request", "detail": "invalid_input"}, status_code=400, headers=_cache_headers_error())
    if size_int <= 0 or size_int > _max_upload_bytes():
        return JSONResponse({"error": "bad_request", "detail": "size_exceeded"}, status_code=400, headers=_cache_headers_error())
    if kind not in {"image", "file"}:
        return JSONResponse({"error": "bad_request", "detail": "invalid_input"}, status_code=400, headers=_cache_headers_error())

    try:
        repo = learning_upload_intent_providers(request).repository()
        ListSubmissionsUseCase(repo).execute(
            ListSubmissionsInput(
                course_id=str(course_id),
                task_id=str(task_id),
                student_sub=str(user.get("sub", "")),
                limit=1,
                offset=0,
            )
        )
    except PermissionError:
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_cache_headers_error())
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_cache_headers_error())
    except Exception:
        return JSONResponse(
            {"error": "service_unavailable", "detail": "authorization_unavailable"},
            status_code=503,
            headers=_cache_headers_error(),
        )

    task_kind = "native"
    if callable(getattr(repo, "get_task_kind_for_student", None)):
        try:
            task_kind = str(
                repo.get_task_kind_for_student(
                    student_sub=str(user.get("sub", "")),
                    course_id=str(course_id),
                    task_id=str(task_id),
                )
            )
        except PermissionError:
            return JSONResponse({"error": "not_found"}, status_code=404, headers=_cache_headers_error())
        except LookupError:
            return JSONResponse({"error": "not_found"}, status_code=404, headers=_cache_headers_error())
        except Exception:
            return JSONResponse(
                {"error": "service_unavailable", "detail": "authorization_unavailable"},
                status_code=503,
                headers=_cache_headers_error(),
            )

    task_kind = (task_kind or "native").strip().lower()
    if task_kind == "scratch":
        if kind != "file" or mime_type != SCRATCH_SB3_MIME:
            return JSONResponse({"error": "bad_request", "detail": "mime_not_allowed"}, status_code=400, headers=_cache_headers_error())
        accepted = [SCRATCH_SB3_MIME]
    elif task_kind == "calliope":
        if kind != "file" or mime_type != MAKECODE_HEX_MIME:
            return JSONResponse({"error": "bad_request", "detail": "mime_not_allowed"}, status_code=400, headers=_cache_headers_error())
        accepted = [MAKECODE_HEX_MIME]
    elif task_kind == "filius":
        if kind != "file" or mime_type != FILIUS_FLS_MIME:
            return JSONResponse({"error": "bad_request", "detail": "mime_not_allowed"}, status_code=400, headers=_cache_headers_error())
        accepted = [FILIUS_FLS_MIME]
    else:
        if kind == "image":
            allowed_image_mime = ALLOWED_IMAGE_MIME
            if mime_type not in allowed_image_mime:
                return JSONResponse(
                    {"error": "bad_request", "detail": "mime_not_allowed"}, status_code=400, headers=_cache_headers_error()
                )
            accepted = sorted(list(allowed_image_mime))
        else:
            if mime_type != PDF_MIME:
                return JSONResponse({"error": "bad_request", "detail": "mime_not_allowed"}, status_code=400, headers=_cache_headers_error())
            accepted = [PDF_MIME]

    import time as _time

    student_sub = str(user.get("sub", "student")).lower()
    ts = int(_time.time() * 1000)
    if mime_type == PNG_MIME:
        ext = ".png"
    elif mime_type == JPEG_MIME:
        ext = ".jpg"
    elif mime_type == SCRATCH_SB3_MIME:
        ext = ".sb3"
    elif mime_type == MAKECODE_HEX_MIME:
        ext = ".hex"
    elif mime_type == FILIUS_FLS_MIME:
        ext = ".fls"
    else:
        ext = ".pdf"
    storage_key = make_submission_key(
        course_id=str(course_id),
        task_id=str(task_id),
        student_sub=str(student_sub),
        ext=ext,
        epoch_ms=ts,
        uuid_hex=_uuid4().hex,
    )

    bucket = _storage_bucket()
    try:
        adapter = learning_upload_intent_providers(request).storage()
    except Exception:
        adapter = NullStorageAdapter()

    if not bucket or isinstance(adapter, NullStorageAdapter):
        if _dev_upload_stub_enabled():
            presign_url = f"/api/learning/internal/upload-stub?storage_key={_quote(storage_key)}"
            intent = {
                "intent_id": str(_uuid4()),
                "storage_key": storage_key,
                "url": presign_url,
                "headers": normalize_upload_intent_headers({}, fallback_content_type=mime_type),
                "accepted_mime_types": accepted,
                "max_size_bytes": _max_upload_bytes(),
                "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=_upload_intent_ttl_seconds())).isoformat(timespec="seconds"),
            }
            return JSONResponse(intent, status_code=200, headers=_cache_headers_success())
        return JSONResponse(
            {"error": "service_unavailable", "detail": "storage_adapter_not_configured"},
            status_code=503,
            headers=_cache_headers_error(),
        )

    ttl_seconds = _upload_intent_ttl_seconds()
    upload_headers = {"Content-Type": mime_type}
    try:
        presigned = adapter.presign_upload(
            bucket=bucket,
            key=storage_key,
            expires_in=ttl_seconds,
            headers=upload_headers,
        )
    except RuntimeError as exc:
        if str(exc) == "storage_adapter_not_configured":
            return JSONResponse(
                {"error": "service_unavailable", "detail": "storage_adapter_not_configured"},
                status_code=503,
                headers=_cache_headers_error(),
            )
        raise

    presign_url = presigned.get("url")
    if not presign_url:
        return JSONResponse(
            {"error": "service_unavailable", "detail": "presign_failed"},
            status_code=503,
            headers=_cache_headers_error(),
        )

    url_out = str(presign_url)
    try:
        headers_src: dict[str, Any] = dict(presigned.get("headers") or upload_headers)
    except Exception:
        headers_src = dict(upload_headers)
    proxy_headers_token = _encode_proxy_headers(headers_src)

    if _upload_proxy_enabled():
        base = (os.getenv("SUPABASE_URL") or "").strip()
        try:
            parsed_target = _urlparse(str(presign_url))
            parsed_base = _urlparse(base)
            th = parsed_target.hostname or ""
            bh = parsed_base.hostname or ""
        except Exception:
            th = bh = ""
        if th and bh and th == bh:
            url_out = f"/api/learning/internal/upload-proxy?url={_quote(str(presign_url))}"
            if proxy_headers_token:
                url_out += f"&headers={_quote(proxy_headers_token)}"
    headers_out = normalize_upload_intent_headers(headers_src, fallback_content_type=mime_type)
    intent = {
        "intent_id": str(_uuid4()),
        "storage_key": storage_key,
        "url": url_out,
        "headers": headers_out,
        "accepted_mime_types": accepted,
        "max_size_bytes": _max_upload_bytes(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)).isoformat(timespec="seconds"),
    }
    return JSONResponse(intent, status_code=200, headers=_cache_headers_success())
