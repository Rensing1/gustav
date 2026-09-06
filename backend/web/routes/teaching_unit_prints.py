"""HTTP adapter for transient teacher-authored print PDFs."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response

from backend.teaching.printouts import (
    PrintExportError,
    list_printable_content,
    validate_selection,
)
from backend.teaching.printouts import (
    create_printable_pdf as build_printable_pdf,
)
from backend.teaching.printouts_pdf import IsolatedLearningUnitPdfRenderer
from backend.web.routes import teaching_guards
from backend.web.routes.teaching import _get_repo
from backend.web.routes.teaching_payloads import TeachingUnitPrintPayload
from backend.web.routes.teaching_shared import (
    _current_sub,
    _is_uuid_like,
    _json_private,
    _private_error,
    _require_teacher,
)
from backend.web.routes.teaching_unit_materials import _material_file_settings, _storage_adapter

teaching_unit_prints_router = APIRouter(tags=["Teaching"])
PDF_RENDERER = IsolatedLearningUnitPdfRenderer()


@teaching_unit_prints_router.get("/api/teaching/units/{unit_id}/printable-content")
async def get_printable_content(request: Request, unit_id: str):
    """Return the ordered selection model for an authored learning unit."""

    user, error = _require_teacher(request)
    if error:
        return error
    if not _is_uuid_like(unit_id):
        return _private_error({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    author_id = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, author_id, repo_provider=_get_repo)
    if guard:
        return guard
    payload = list_printable_content(_get_repo(), unit_id=unit_id, author_id=author_id)
    if payload is None:
        return _private_error({"error": "not_found"}, status_code=404)
    return _json_private(payload, status_code=200)


@teaching_unit_prints_router.post("/api/teaching/units/{unit_id}/printable-pdf")
async def create_printable_pdf(request: Request, unit_id: str, payload: TeachingUnitPrintPayload):
    """Validate an author-only PDF request before resource-intensive rendering."""

    user, error = _require_teacher(request)
    if error:
        return error
    csrf = teaching_guards._csrf_guard(request)
    if csrf:
        return csrf
    if not _is_uuid_like(unit_id):
        return _private_error({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400)
    author_id = _current_sub(user)
    guard = teaching_guards._guard_unit_author(unit_id, author_id, repo_provider=_get_repo)
    if guard:
        return guard
    try:
        # Validate before any repository traversal or storage reads. The use case
        # repeats this check because HTTP is not its only possible caller.
        material_ids, task_ids = validate_selection(payload.material_ids, payload.task_ids)
        if any(not _is_uuid_like(item_id) for item_id in [*material_ids, *task_ids]):
            raise ValueError("invalid_print_selection")
        # The renderer moves untrusted PDF work into a resource-limited child
        # process; repository and storage access remain in this request worker.
        generated = build_printable_pdf(
            _get_repo(),
            storage=_storage_adapter(),
            renderer=PDF_RENDERER,
            unit_id=unit_id,
            author_id=author_id,
            material_ids=material_ids,
            task_ids=task_ids,
            storage_bucket=_material_file_settings().storage_bucket,
        )
    except OverflowError as exc:
        return _private_error({"error": "payload_too_large", "detail": str(exc)}, status_code=413)
    except ValueError as exc:
        return _private_error({"error": "bad_request", "detail": str(exc)}, status_code=400)
    except PrintExportError as exc:
        error = "bad_request" if exc.status_code == 400 else "payload_too_large" if exc.status_code == 413 else exc.code
        body: dict[str, object] = {"error": error, "detail": exc.code}
        if exc.material_title:
            body["material"] = {"title": exc.material_title}
        return _private_error(body, status_code=exc.status_code)
    return Response(
        content=generated.content,
        media_type="application/pdf",
        headers={
            "Cache-Control": "private, no-store",
            "Content-Disposition": f'attachment; filename="{generated.filename}"',
            "X-Content-Type-Options": "nosniff",
        },
    )


__all__ = ["PDF_RENDERER", "teaching_unit_prints_router"]
