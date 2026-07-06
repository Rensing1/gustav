"""Internal Learning upload routes for dev stubs and same-origin proxying."""

from __future__ import annotations

import hashlib as _hashlib
import importlib
import os
import re
import sys as _sys
from pathlib import Path as _Path

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.storage.learning_policy import STORAGE_KEY_RE, resolve_local_verify_root_from_env
from backend.web.routes.learning_upload_proxy import (
    decode_proxy_headers as _decode_proxy_headers,
    filter_upload_proxy_headers as _filter_upload_proxy_headers,
    normalized_parts as _normalized_parts,
)


learning_internal_upload_router = APIRouter(tags=["Learning"])


def _learning_module():
    module = _sys.modules.get("backend.web.routes.learning")
    if module is None:  # pragma: no cover - defensive import fallback
        module = importlib.import_module("backend.web.routes.learning")
    return module


def _cache_headers_success() -> dict[str, str]:
    return _learning_module()._cache_headers_success()


def _cache_headers_error() -> dict[str, str]:
    return _learning_module()._cache_headers_error()


def _require_student(request: Request):
    return _learning_module()._require_student(request)


def _require_strict_same_origin(request: Request) -> bool:
    return bool(_learning_module()._require_strict_same_origin(request))


def _dev_upload_stub_enabled() -> bool:
    return bool(_learning_module()._dev_upload_stub_enabled())


def _upload_proxy_enabled() -> bool:
    return bool(_learning_module()._upload_proxy_enabled())


def _upload_proxy_timeout_seconds() -> float:
    return float(_learning_module()._upload_proxy_timeout_seconds())


def _max_upload_bytes() -> int:
    return int(_learning_module()._max_upload_bytes())


def _urlparse(raw: str):
    return _learning_module()._urlparse(raw)


async def _read_request_stream_with_limit(request: Request, limit: int) -> tuple[bytes | None, str | None]:
    return await _learning_module()._read_request_stream_with_limit(request, limit)


def _current_async_forward_upload():
    return _learning_module()._current_async_forward_upload()


def _current_emit_upload_proxy_telemetry():
    return _learning_module()._current_emit_upload_proxy_telemetry()


def _allowed_image_mime() -> set[str]:
    return set(_learning_module().ALLOWED_IMAGE_MIME)


def _allowed_file_mime() -> set[str]:
    return set(_learning_module().ALLOWED_FILE_MIME)


@learning_internal_upload_router.put("/api/learning/internal/upload-stub")
async def internal_upload_stub(request: Request):
    """Accept a small file upload and persist under STORAGE_VERIFY_ROOT."""

    if not _dev_upload_stub_enabled():
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_cache_headers_error())
    user, error = _require_student(request)
    if error:
        return error
    if not _require_strict_same_origin(request):
        return JSONResponse({"error": "forbidden", "detail": "csrf_violation"}, status_code=403, headers=_cache_headers_error())

    storage_key = str(request.query_params.get("storage_key") or "").strip()
    if not storage_key or not STORAGE_KEY_RE.fullmatch(storage_key):
        return JSONResponse({"error": "bad_request", "detail": "invalid_storage_key"}, status_code=400, headers=_cache_headers_error())

    root = resolve_local_verify_root_from_env()
    if not root:
        return JSONResponse(
            {"error": "service_unavailable", "detail": "upload_stub_storage_unavailable"},
            status_code=503,
            headers=_cache_headers_error(),
        )
    base = _Path(root).resolve()
    target = (base / storage_key).resolve()
    try:
        common = os.path.commonpath([str(base), str(target)])
    except Exception:
        return JSONResponse({"error": "bad_request", "detail": "path_error"}, status_code=400, headers=_cache_headers_error())
    if common != str(base):
        return JSONResponse({"error": "bad_request", "detail": "path_escape"}, status_code=400, headers=_cache_headers_error())

    body, body_error = await _read_request_stream_with_limit(request, _max_upload_bytes())
    if body_error:
        return JSONResponse({"error": "bad_request", "detail": body_error}, status_code=400, headers=_cache_headers_error())

    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("wb") as fh:
        fh.write(body)

    h = _hashlib.sha256()
    h.update(body)
    return JSONResponse({"sha256": h.hexdigest(), "size_bytes": len(body)}, status_code=200, headers=_cache_headers_success())


@learning_internal_upload_router.put("/api/learning/internal/upload-proxy")
async def internal_upload_proxy(request: Request):
    """Proxy a file upload to a presigned Storage URL as a same-origin fallback."""

    target_host_for_log = "n/a"
    content_type_for_log = request.headers.get("content-type") or "application/octet-stream"

    def _proxy_error(payload: dict[str, str], *, status_code: int, reason: str) -> JSONResponse:
        _current_emit_upload_proxy_telemetry()(
            outcome="error",
            status_code=status_code,
            reason=reason,
            target_host=target_host_for_log,
            content_type=content_type_for_log,
            size_bytes=None,
        )
        return JSONResponse(payload, status_code=status_code, headers=_cache_headers_error())

    user, error = _require_student(request)
    if error:
        _current_emit_upload_proxy_telemetry()(
            outcome="error",
            status_code=int(getattr(error, "status_code", 401)),
            reason="auth",
            target_host=target_host_for_log,
            content_type=content_type_for_log,
            size_bytes=None,
        )
        return error
    if not _require_strict_same_origin(request):
        return _proxy_error({"error": "forbidden", "detail": "csrf_violation"}, status_code=403, reason="csrf_violation")
    if not _upload_proxy_enabled():
        return _proxy_error({"error": "not_found"}, status_code=404, reason="feature_disabled")

    target = str(request.query_params.get("url") or "").strip()
    header_token = str(request.query_params.get("headers") or "").strip()
    forward_headers = _filter_upload_proxy_headers(_decode_proxy_headers(header_token))
    if not target:
        return _proxy_error({"error": "bad_request", "detail": "missing_url"}, status_code=400, reason="missing_url")
    base = (os.getenv("SUPABASE_URL") or "").strip()
    public_base = (os.getenv("SUPABASE_PUBLIC_URL") or "").strip()
    try:
        parsed_target = _urlparse(target)
        parsed_base = _urlparse(base) if base else None
        parsed_public = _urlparse(public_base) if public_base else None
    except Exception:
        return _proxy_error({"error": "bad_request", "detail": "invalid_url"}, status_code=400, reason="invalid_url_parse")

    target_scheme, target_host, target_port = _normalized_parts(parsed_target)
    target_host_for_log = target_host or "n/a"

    if not target_scheme or target_scheme not in {"http", "https"} or not target_host:
        return _proxy_error({"error": "bad_request", "detail": "invalid_url"}, status_code=400, reason="invalid_url_parts")

    local_hosts = {"localhost", "::1", "host.docker.internal"}
    is_local_http = target_host in local_hosts or target_host.startswith("127.")
    if target_scheme == "http" and not is_local_http:
        return _proxy_error({"error": "bad_request", "detail": "invalid_url"}, status_code=400, reason="invalid_url_scheme")
    allowed_hosts: list[tuple[str, str, int | None]] = []
    for parsed in (parsed_base, parsed_public):
        if not parsed:
            continue
        scheme, host, port = _normalized_parts(parsed)
        if host:
            allowed_hosts.append((scheme, host, port))
    if not allowed_hosts:
        return _proxy_error({"error": "bad_request", "detail": "invalid_url_host"}, status_code=400, reason="missing_allowed_hosts")

    matched_scheme = None
    matched_port: int | None = None
    for scheme, host, port in allowed_hosts:
        if target_host == host:
            matched_scheme = scheme
            matched_port = port
            break

    if matched_scheme is None:
        return _proxy_error({"error": "bad_request", "detail": "invalid_url_host"}, status_code=400, reason="invalid_url_host")
    if matched_scheme == "https" and target_scheme != "https":
        return _proxy_error({"error": "bad_request", "detail": "invalid_url"}, status_code=400, reason="invalid_url_scheme")
    if matched_port and target_port and target_port != matched_port:
        return _proxy_error({"error": "bad_request", "detail": "invalid_url_host"}, status_code=400, reason="invalid_url_port")

    path = parsed_target.path or "/"
    while "//" in path:
        path = path.replace("//", "/")
    if ".." in path or re.search(r"%2e", path, flags=re.IGNORECASE):
        return _proxy_error({"error": "bad_request", "detail": "invalid_url"}, status_code=400, reason="invalid_url_path")
    if not path.startswith("/storage/v1/object/"):
        return _proxy_error({"error": "bad_request", "detail": "invalid_url"}, status_code=400, reason="invalid_url_path")

    body, body_error = await _read_request_stream_with_limit(request, _max_upload_bytes())
    if body_error:
        return _proxy_error({"error": "bad_request", "detail": body_error}, status_code=400, reason=body_error)
    content_type = request.headers.get("content-type") or "application/octet-stream"
    content_type_for_log = content_type
    allowed_mime = (_allowed_image_mime() | _allowed_file_mime() | {"application/octet-stream"})
    if content_type not in allowed_mime:
        return _proxy_error({"error": "bad_request", "detail": "mime_not_allowed"}, status_code=400, reason="mime_not_allowed")

    try:
        resp = await _current_async_forward_upload()(
            url=target,
            payload=body,
            content_type=content_type,
            timeout=_upload_proxy_timeout_seconds(),
            headers=forward_headers or None,
        )
    except Exception:
        return _proxy_error({"error": "bad_gateway", "detail": "proxy_failed"}, status_code=502, reason="proxy_failed")
    if getattr(resp, "status_code", 500) >= 300:
        return _proxy_error({"error": "bad_gateway", "detail": "upstream_error"}, status_code=502, reason="upstream_error")

    h = _hashlib.sha256()
    h.update(body)
    _current_emit_upload_proxy_telemetry()(
        outcome="success",
        status_code=200,
        reason="ok",
        target_host=target_host_for_log,
        content_type=content_type_for_log,
        size_bytes=len(body),
    )
    return JSONResponse({"sha256": h.hexdigest(), "size_bytes": len(body)}, status_code=200, headers=_cache_headers_success())
