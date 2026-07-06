"""Learning submission command routes.

This module owns the write-side submission endpoints for learners. Runtime
helpers are resolved through the public `learning.py` facade so existing tests
and gradual router splits can keep monkeypatching the same compatibility
surface while the large command handlers live outside the route hotspot.
"""

from __future__ import annotations

import logging
import os
import re
import sys
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.learning.submission_kind_policy import validate_task_submission_kind
from backend.learning.usecases.submissions import (
    CreateSubmissionInput,
    CreateSubmissionUseCase,
    FinalizeLatestDraftInput,
    FinalizeLatestDraftUseCase,
)
from backend.storage.learning_policy import resolve_local_verify_root_from_env
from backend.storage.mime_types import FILIUS_FLS_MIME, MAKECODE_HEX_MIME, PDF_MIME, SCRATCH_SB3_MIME
from backend.storage.submission_content_signatures import validate_submission_content_signature


learning_submission_commands_router = APIRouter(tags=["Learning"])
logger = logging.getLogger("gustav.web.learning")


def _learning_facade() -> Any:
    module = sys.modules.get("backend.web.routes.learning")
    if module is None:  # pragma: no cover - defensive import fallback
        import backend.web.routes.learning as module  # type: ignore
    return module


def _cache_headers_error() -> dict[str, str]:
    return _learning_facade()._cache_headers_error()


def _cache_headers_success() -> dict[str, str]:
    return _learning_facade()._cache_headers_success()


def _valid_idempotency_key(value: str | None) -> bool:
    return value is None or bool(re.fullmatch(r"[A-Za-z0-9_-]{1,64}", value))


def _current_create_submission_use_case() -> type:
    return getattr(_learning_facade(), "CreateSubmissionUseCase", CreateSubmissionUseCase)


def _current_finalize_latest_draft_use_case() -> type:
    return getattr(_learning_facade(), "FinalizeLatestDraftUseCase", FinalizeLatestDraftUseCase)


@learning_submission_commands_router.post("/api/learning/courses/{course_id}/tasks/{task_id}/submissions")
async def create_submission(request: Request, course_id: str, task_id: str, payload: dict[str, Any]):
    """Create a student submission for a task.

    Security:
        Enforces same-origin using Origin or Referer; rejects cross-site POSTs.

    Permissions:
        Caller must be an enrolled student with access to the released task.
    """

    learning = _learning_facade()
    if not learning._require_strict_same_origin(request):
        return JSONResponse({"error": "forbidden", "detail": "csrf_violation"}, status_code=403, headers=_cache_headers_error())

    user, error = learning._require_student(request)
    if error:
        return error

    try:
        UUID(course_id)
        UUID(task_id)
    except ValueError:
        return JSONResponse({"error": "bad_request", "detail": "invalid_uuid"}, status_code=400, headers=_cache_headers_error())

    idempotency_key = request.headers.get("Idempotency-Key")
    if idempotency_key is not None and len(idempotency_key) > 64:
        return JSONResponse({"error": "bad_request", "detail": "invalid_input"}, status_code=400, headers=_cache_headers_error())
    if not _valid_idempotency_key(idempotency_key):
        return JSONResponse({"error": "bad_request", "detail": "invalid_input"}, status_code=400, headers=_cache_headers_error())

    try:
        kind, clean_payload = learning._validate_submission_payload(payload)
    except ValueError as exc:
        detail = str(exc) if str(exc) else "invalid_input"
        return JSONResponse({"error": "bad_request", "detail": detail}, status_code=400, headers=_cache_headers_error())

    if kind in ("image", "file"):
        storage_key = clean_payload.get("storage_key")
        sha256 = clean_payload.get("sha256")
        size_bytes = clean_payload.get("size_bytes")
        mime_type = clean_payload.get("mime_type")
        try:
            ok, _reason = learning._verify_storage_object(
                str(storage_key), str(sha256), int(size_bytes), str(mime_type)
            )
        except Exception:
            ok = False
        if not ok:
            detail = "invalid_image_payload" if kind == "image" else "invalid_file_payload"
            return JSONResponse({"error": "bad_request", "detail": detail}, status_code=400, headers=_cache_headers_error())

    validation_bytes: bytes | None = None
    task_kind_for_submission = "native"
    task_kind_for_submission_normalized = "native"
    if kind in ("image", "file"):
        repo = learning._get_repo()
        task_kind_reader = getattr(repo, "get_task_kind_for_student", None)
        if callable(task_kind_reader):
            try:
                task_kind_for_submission = str(
                    task_kind_reader(
                        student_sub=str(user.get("sub", "")),
                        course_id=str(course_id),
                        task_id=str(task_id),
                    )
                )
            except PermissionError:
                return JSONResponse({"error": "forbidden"}, status_code=403, headers=_cache_headers_error())
            except LookupError:
                return JSONResponse({"error": "not_found"}, status_code=404, headers=_cache_headers_error())
            except Exception:
                return JSONResponse(
                    {"error": "service_unavailable", "detail": "submission_validation_unavailable"},
                    status_code=503,
                    headers=_cache_headers_error(),
                )
        task_kind_for_submission_normalized = str(task_kind_for_submission or "native").strip().lower()
        try:
            validate_task_submission_kind(
                task_kind=task_kind_for_submission_normalized,
                submission_kind=kind,
                mime_type=str(clean_payload.get("mime_type") or ""),
            )
        except ValueError as exc:
            return JSONResponse(
                {"error": "bad_request", "detail": str(exc) or "invalid_input"},
                status_code=400,
                headers=_cache_headers_error(),
            )
        storage_key = str(clean_payload.get("storage_key") or "")
        mime_type = str(clean_payload.get("mime_type") or "")
        validation_bytes = await learning._load_storage_bytes_for_validation(
            storage_key=storage_key, max_bytes=learning._max_upload_bytes()
        )
        if not validation_bytes:
            return JSONResponse(
                {"error": "service_unavailable", "detail": "submission_validation_unavailable"},
                status_code=503,
                headers=_cache_headers_error(),
            )
        try:
            validate_submission_content_signature(mime_type, validation_bytes)
        except ValueError:
            logger.info(
                "learning_upload_content_signature_mismatch",
                extra={
                    "reason": "invalid_upload_content",
                    "mime_type": str(mime_type).strip().lower(),
                    "task_kind": task_kind_for_submission_normalized,
                    "byte_count": len(validation_bytes),
                },
            )
            return JSONResponse(
                {"error": "bad_request", "detail": "invalid_upload_content"},
                status_code=400,
                headers=_cache_headers_error(),
            )

    if kind == "file" and str(clean_payload.get("mime_type") or "").strip().lower() == SCRATCH_SB3_MIME:
        if task_kind_for_submission_normalized == "scratch":
            sb3_bytes = validation_bytes
            if not sb3_bytes:
                return JSONResponse(
                    {"error": "service_unavailable", "detail": "sb3_validation_unavailable"},
                    status_code=503,
                    headers=_cache_headers_error(),
                )
            from backend.storage.sb3_validation import SB3ValidationError, load_project_json

            try:
                _ = load_project_json(sb3_bytes)
            except SB3ValidationError as exc:
                return JSONResponse(
                    {"error": "bad_request", "detail": str(exc.code)},
                    status_code=400,
                    headers=_cache_headers_error(),
                )

    if kind == "file" and str(clean_payload.get("mime_type") or "").strip().lower() == MAKECODE_HEX_MIME:
        if task_kind_for_submission_normalized == "calliope":
            hex_bytes = validation_bytes
            if not hex_bytes:
                return JSONResponse(
                    {"error": "service_unavailable", "detail": "hex_validation_unavailable"},
                    status_code=503,
                    headers=_cache_headers_error(),
                )
            from backend.storage.makecode_hex_validation import MakeCodeHexValidationError, extract_makecode_project_from_hex

            try:
                _ = extract_makecode_project_from_hex(hex_bytes)
            except MakeCodeHexValidationError as exc:
                if str(exc.code) in {"invalid_hex_file", "missing_makecode_source"}:
                    logger.info(
                        "calliope_hex_soft_extraction_error",
                        extra={"detail": str(exc.code), "course_id": str(course_id), "task_id": str(task_id)},
                    )
                else:
                    return JSONResponse(
                        {"error": "bad_request", "detail": str(exc.code)},
                        status_code=400,
                        headers=_cache_headers_error(),
                    )

    if kind == "file" and str(clean_payload.get("mime_type") or "").strip().lower() == FILIUS_FLS_MIME:
        if task_kind_for_submission_normalized != "filius":
            return JSONResponse(
                {"error": "bad_request", "detail": "invalid_file_payload"},
                status_code=400,
                headers=_cache_headers_error(),
            )

        fls_bytes = validation_bytes
        if not fls_bytes:
            return JSONResponse(
                {"error": "service_unavailable", "detail": "filius_validation_unavailable"},
                status_code=503,
                headers=_cache_headers_error(),
            )
        from backend.storage.filius_validation import FiliusValidationError, extract_configuration_xml_bytes

        try:
            _ = extract_configuration_xml_bytes(fls_bytes)
        except FiliusValidationError as exc:
            return JSONResponse(
                {"error": "bad_request", "detail": str(exc.code)},
                status_code=400,
                headers=_cache_headers_error(),
            )

    submission_input = CreateSubmissionInput(
        course_id=course_id,
        task_id=task_id,
        student_sub=str(user.get("sub", "")),
        intent=str(clean_payload.get("intent") or "submit"),
        kind=kind,
        text_body=clean_payload.get("text_body"),
        storage_key=clean_payload.get("storage_key"),
        mime_type=clean_payload.get("mime_type"),
        size_bytes=clean_payload.get("size_bytes"),
        sha256=clean_payload.get("sha256"),
        score_raw=clean_payload.get("score_raw"),
        score_max=clean_payload.get("score_max"),
        idempotency_key=idempotency_key,
    )

    try:
        submission = _current_create_submission_use_case()(learning._get_repo()).execute(submission_input)
    except PermissionError:
        try:
            raw_origin = str(request.headers.get("origin") or request.headers.get("referer") or "")
            origin_hdr = learning._redact_origin_for_diag_log(raw_origin)
            scheme = (request.url.scheme or "http").lower()
            host_hdr = (request.headers.get("host") or request.url.hostname or "").lower()
            if ":" in host_hdr:
                host_only, port_str = host_hdr.rsplit(":", 1)
                host = host_only
                try:
                    port = int(port_str)
                except Exception:
                    port = 443 if scheme == "https" else 80
            else:
                host = host_hdr
                port = int(request.url.port) if request.url.port else (443 if scheme == "https" else 80)
            default = 443 if scheme == "https" else 80
            server_origin = f"{scheme}://{host}{(':' + str(port)) if port != default else ''}"
            diag = f"reason=permission,env={learning._environment_for_request(request)},origin={origin_hdr},server={server_origin}"
        except Exception:
            diag = "reason=permission,env=?,origin=?,server=?"
        try:
            log_path = (os.getenv("CSRF_DIAG_LOG") or "").strip()
            if log_path:
                with open(log_path, "a", encoding="utf-8") as fp:
                    fp.write(f"create_submission: {diag}\n")
        except Exception:
            pass
        return JSONResponse({"error": "forbidden"}, status_code=403, headers=_cache_headers_error())
    except LookupError:
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_cache_headers_error())
    except ValueError as exc:
        detail = str(exc) or "invalid_input"
        return JSONResponse({"error": "bad_request", "detail": detail}, status_code=400, headers=_cache_headers_error())
    except Exception:
        return JSONResponse(
            {"error": "service_unavailable", "detail": "submission_persistence_unavailable"},
            status_code=503,
            headers=_cache_headers_error(),
        )

    try:
        if kind == "file" and str(clean_payload.get("mime_type")) == PDF_MIME:
            root = resolve_local_verify_root_from_env() or ""
            env = learning._environment_for_request(request)
            prod_like = env in {"prod", "production", "stage", "staging"}
            if root and (not prod_like):
                learning._dev_try_process_pdf(
                    root=root,
                    storage_key=str(clean_payload.get("storage_key") or ""),
                    submission_id=str(submission.get("id")),
                    course_id=str(course_id),
                    task_id=str(task_id),
                    student_sub=str(user.get("sub", "")),
                )
    except Exception:
        pass

    status_code = 201 if kind == "h5p" else 202
    return JSONResponse(submission, status_code=status_code, headers=_cache_headers_success())


@learning_submission_commands_router.post("/api/learning/courses/{course_id}/tasks/{task_id}/submissions/finalize")
async def finalize_submission(request: Request, course_id: str, task_id: str, payload: dict[str, Any] | None = None):
    """Create a final submission from the latest completed feedback draft."""
    learning = _learning_facade()
    if not learning._require_strict_same_origin(request):
        return JSONResponse({"error": "forbidden", "detail": "csrf_violation"}, status_code=403, headers=_cache_headers_error())

    user, auth_error = learning._require_student(request)
    if auth_error:
        return auth_error

    try:
        UUID(course_id)
        UUID(task_id)
    except ValueError:
        return JSONResponse({"error": "bad_request", "detail": "invalid_uuid"}, status_code=400, headers=_cache_headers_error())

    idempotency_key = request.headers.get("Idempotency-Key")
    if idempotency_key is not None and len(idempotency_key) > 64:
        return JSONResponse({"error": "bad_request", "detail": "invalid_input"}, status_code=400, headers=_cache_headers_error())
    if not _valid_idempotency_key(idempotency_key):
        return JSONResponse({"error": "bad_request", "detail": "invalid_input"}, status_code=400, headers=_cache_headers_error())

    finalize_input = FinalizeLatestDraftInput(
        course_id=course_id,
        task_id=task_id,
        student_sub=str(user.get("sub", "")),
        idempotency_key=idempotency_key,
    )

    try:
        submission = _current_finalize_latest_draft_use_case()(learning._get_repo()).execute(finalize_input)
    except PermissionError:
        return JSONResponse({"error": "forbidden"}, status_code=403, headers=_cache_headers_error())
    except LookupError as exc:
        detail = str(exc) or "not_found"
        if detail == "draft_missing":
            return JSONResponse({"error": "conflict", "detail": detail}, status_code=409, headers=_cache_headers_error())
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_cache_headers_error())
    except RuntimeError as exc:
        return JSONResponse({"error": "conflict", "detail": str(exc) or "draft_not_ready"}, status_code=409, headers=_cache_headers_error())
    except ValueError as exc:
        return JSONResponse({"error": "bad_request", "detail": str(exc) or "invalid_input"}, status_code=400, headers=_cache_headers_error())
    except Exception:
        return JSONResponse(
            {"error": "service_unavailable", "detail": "submission_persistence_unavailable"},
            status_code=503,
            headers=_cache_headers_error(),
        )

    decorated = learning._attach_submission_files(submission, course_id=course_id, task_id=task_id)
    return JSONResponse(decorated, status_code=201, headers=_cache_headers_success())
