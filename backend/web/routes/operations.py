"""Operations endpoints (internal tooling for teachers/operators)."""

from __future__ import annotations

import os
import sys
import time
from urllib.parse import urljoin

# Temporary compatibility while legacy tests still import `routes.operations`.
if __name__ == "backend.web.routes.operations":
    sys.modules.setdefault("routes.operations", sys.modules[__name__])
elif __name__ == "routes.operations":
    sys.modules.setdefault("backend.web.routes.operations", sys.modules[__name__])

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.learning.workers import health as worker_health
from backend.web.security.guards import has_any_role

operations_router = APIRouter(tags=["Operations"])

# In-memory cache to avoid repeatedly probing the OpenAI-compatible endpoint.
#
# Why:
#   The footer indicator can poll periodically and HTMX navigation may trigger
#   multiple refreshes close together. We keep a short TTL cache so we don't
#   spam `/models` unnecessarily.
#
# Security:
#   This is internal tooling only (teacher/operator). The cached payload does
#   not contain PII.
_OPENAI_HEALTH_CACHE_TTL_SECONDS = 15.0
_OPENAI_HEALTH_CACHE: dict[str, object] = {"key": None, "at": 0.0, "body": None, "status_code": None}


def _private_response(body: dict, *, status_code: int) -> JSONResponse:
    """Return JSON with private cache headers and CSRF-aware Vary.

    Security: Internal tooling must not be cached by shared caches and should
    vary by Origin for CSRF-aware intermediaries.
    """
    return JSONResponse(
        body,
        status_code=status_code,
        headers={"Cache-Control": "private, no-store", "Vary": "Origin"},
    )


def _require_teacher_or_operator(request: Request):
    user = getattr(request.state, "user", None)
    if not user:
        return None, _private_response({"error": "unauthenticated"}, status_code=401)
    if not has_any_role(user, {"teacher", "operator"}):
        return None, _private_response({"error": "forbidden"}, status_code=403)
    return user, None


def _openai_health_cache_key() -> tuple[str, object]:
    """Return a cache key for the OpenAI health probe."""
    base_url = (os.getenv("OPENAI_BASE_URL") or "").strip()
    # Include the callable object itself, not its integer id.
    # Why:
    #   CPython may reuse object ids after GC. Using the callable reference
    #   avoids accidental cache collisions across monkeypatched probe objects.
    return base_url, _probe_openai_health


def _join_openai_models_url(base_url: str) -> str:
    """Return a best-effort models URL for an OpenAI-compatible base URL."""
    raw = (base_url or "").strip()
    if not raw:
        return ""
    if not raw.endswith("/"):
        raw = raw + "/"
    return urljoin(raw, "models")


async def _probe_openai_health() -> tuple[dict, int]:
    """Probe OPENAI_BASE_URL by requesting `/models`.

    Returns:
        (body, status_code)
    """
    base_url = (os.getenv("OPENAI_BASE_URL") or "").strip()
    if not base_url:
        body = {
            "status": "degraded",
            "configured": False,
            "reachable": False,
            "modelsLoaded": False,
            "modelsCount": 0,
            "detail": "missing_OPENAI_BASE_URL",
        }
        return body, 503

    models_url = _join_openai_models_url(base_url)
    if not models_url:
        body = {
            "status": "degraded",
            "configured": True,
            "reachable": False,
            "modelsLoaded": False,
            "modelsCount": 0,
            "detail": "invalid_OPENAI_BASE_URL",
        }
        return body, 503

    headers: dict[str, str] = {}
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        import httpx

        async with httpx.AsyncClient(timeout=2.0, trust_env=False) as client:
            resp = await client.get(models_url, headers=headers)
    except Exception:
        body = {
            "status": "degraded",
            "configured": True,
            "reachable": False,
            "modelsLoaded": False,
            "modelsCount": 0,
            "detail": "connect_failed",
        }
        return body, 503

    reachable = True
    models_count = 0
    detail: str | None = None

    if resp.status_code != 200:
        detail = f"http_{resp.status_code}"
    else:
        try:
            payload = resp.json()
        except Exception:
            payload = None
        # OpenAI shape: {"object":"list","data":[{"id":"..."}]}
        if isinstance(payload, dict):
            data = payload.get("data")
            if isinstance(data, list):
                models_count = len([m for m in data if isinstance(m, dict)])
        elif isinstance(payload, list):
            # Some endpoints return a bare list
            models_count = len([m for m in payload if isinstance(m, (dict, str))])

    models_loaded = models_count > 0
    status = "healthy" if reachable and models_loaded and detail is None else "degraded"
    status_code = 200 if status == "healthy" else 503
    body = {
        "status": status,
        "configured": True,
        "reachable": reachable,
        "modelsLoaded": models_loaded,
        "modelsCount": models_count,
        "detail": detail,
    }
    return body, status_code


@operations_router.get("/internal/health/learning-worker")
async def learning_worker_health(request: Request):
    """
    Return diagnostics for the learning worker pipeline.

    Permissions:
        Caller must have `teacher` or `operator` role (auth via gustav_session).
    """
    _, error = _require_teacher_or_operator(request)
    if error:
        return error

    probe = await worker_health.LEARNING_WORKER_HEALTH_SERVICE.probe()
    body = {
        "status": probe.status,
        "currentRole": probe.current_role,
        "checks": [
            {"check": check.check, "status": check.status, "detail": check.detail}
            for check in probe.checks
        ],
    }
    status_code = 200 if probe.status == "healthy" else 503
    return _private_response(body, status_code=status_code)


@operations_router.get("/internal/health/openai")
async def openai_health(request: Request):
    """
    Return diagnostics for the configured OpenAI-compatible endpoint.

    Permissions:
        Caller must have `teacher` or `operator` role (auth via gustav_session).
    """
    _, error = _require_teacher_or_operator(request)
    if error:
        return error

    cache_key = _openai_health_cache_key()
    now = time.monotonic()
    cached_key = _OPENAI_HEALTH_CACHE.get("key")
    cached_at = float(_OPENAI_HEALTH_CACHE.get("at") or 0.0)
    cached_body = _OPENAI_HEALTH_CACHE.get("body")
    cached_status = _OPENAI_HEALTH_CACHE.get("status_code")
    if cached_key == cache_key and cached_body is not None and (now - cached_at) < _OPENAI_HEALTH_CACHE_TTL_SECONDS:
        return _private_response(dict(cached_body), status_code=int(cached_status or 503))

    body, status_code = await _probe_openai_health()
    _OPENAI_HEALTH_CACHE.update(
        {"key": cache_key, "at": now, "body": dict(body), "status_code": int(status_code)}
    )
    return _private_response(body, status_code=status_code)
