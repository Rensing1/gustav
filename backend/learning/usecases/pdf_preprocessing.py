"""
PDF preprocessing use case (TDD scaffolding).

Intent:
    Convert a stored PDF submission into preprocessed page images, persist the
    derived assets, and transition the submission to the `extracted` status.

Parameters:
    - repo: Learning repository implementing `mark_extracted`.
    - worker_dsn: Postgres DSN with privileges to update submissions under RLS.
    - storage: BinaryWriteStorage implementation used to persist PNG pages.
    - bucket: Supabase storage bucket for learning submissions.

Expected behavior:
    - Reject oversized inputs (`input_too_large`) before rendering.
    - Map PDF render errors to `input_corrupt`.
    - Persist derived page images and mark submission `extracted` on success.

Permissions:
    Caller must ensure the student owns the submission. This use case sets
    `app.current_sub` to the student when performing direct DB writes.
"""
from __future__ import annotations

from dataclasses import dataclass
import importlib
from typing import Protocol

import psycopg  # type: ignore

from backend.vision.pdf_renderer import PdfRenderError
from backend.learning.repo_db import _sanitize_error_message as _sanitize_repo_error_message


class BinaryWriteStorage(Protocol):
    """Minimal storage port (subset of backend.storage.ports.BinaryWriteStorage)."""

    def put_object(self, *, bucket: str, key: str, body: bytes, content_type: str) -> None: ...


class MarkExtractedRepo(Protocol):
    """Repository contract used to transition submissions to `extracted`."""

    def mark_extracted(self, *, submission_id: str, page_keys: list[str]) -> None: ...


@dataclass(frozen=True)
class SubmissionContext:
    """Aggregate the identifiers needed to locate and update a submission."""

    submission_id: str
    course_id: str
    task_id: str
    student_sub: str
    storage_key: str
    mime_type: str
    size_bytes: int
    sha256: str


class PreprocessPdfSubmissionUseCase:
    """Render a PDF submission to images, store them, and update status."""

    def __init__(
        self,
        *,
        repo: MarkExtractedRepo,
        worker_dsn: str,
        storage: BinaryWriteStorage,
        bucket: str,
        size_limit_bytes: int | None = None,
    ) -> None:
        self._repo = repo
        self._worker_dsn = worker_dsn
        self._storage = storage
        self._bucket = bucket
        self._size_limit = size_limit_bytes or 10 * 1024 * 1024  # 10 MiB default

    def execute(self, *, context: SubmissionContext, pdf_bytes: bytes) -> None:
        """Drive the preprocessing workflow for a single submission."""
        if context.size_bytes and context.size_bytes > self._size_limit:
            self._mark_failed(context=context, code="input_too_large", message="declared size exceeds configured limit")
            return

        try:
            pipeline = importlib.import_module("backend.vision.pipeline")
            process_pdf_bytes = getattr(pipeline, "process_pdf_bytes")
        except Exception:
            self._mark_failed(context=context, code="input_unsupported", message="pdf pipeline unavailable")
            return

        try:
            pages, _meta = process_pdf_bytes(pdf_bytes)
        except PdfRenderError as exc:
            self._mark_failed(context=context, code="input_corrupt", message=str(exc) or "pdf render failed")
            return
        except Exception as exc:  # pragma: no cover - defensive guard
            self._mark_failed(context=context, code="input_unsupported", message=str(exc) or "unsupported pdf input")
            return

        if not pages:
            self._mark_failed(context=context, code="input_unsupported", message="pdf rendered zero pages")
            return

        # Import inside the hot path to avoid coupling during module import.
        from backend.vision.persistence import SubmissionScope, persist_rendered_pages  # type: ignore

        scope = SubmissionScope(
            course_id=context.course_id,
            task_id=context.task_id,
            student_sub=context.student_sub,
            submission_id=context.submission_id,
        )

        class _PersistPage:
            """Adapter to expose PNG bytes under the attribute expected by persistence."""

            def __init__(self, data: bytes) -> None:
                self.png_bytes = data

        persist_pages = []
        for page in pages:
            data = getattr(page, "png_bytes", None)
            if data is None:
                data = getattr(page, "data", None)
            if data is None:
                self._mark_failed(context=context, code="input_unsupported", message="pdf page missing image bytes")
                return
            persist_pages.append(_PersistPage(data))

        try:
            persist_rendered_pages(
                storage=self._storage,
                bucket=self._bucket,
                scope=scope,
                pages=persist_pages,
                repo=self._repo,
            )
        except Exception as exc:
            self._mark_failed(context=context, code="input_corrupt", message=str(exc) or "persist rendered pages failed")

    def _mark_failed(self, *, context: SubmissionContext, code: str, message: str) -> None:
        """Set submission status to failed with the provided error code/message."""
        clean_message = _sanitize_repo_error_message(message) or "processing_failed"
        with psycopg.connect(self._worker_dsn) as conn:  # type: ignore[arg-type]
            with conn.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, false)", (context.student_sub,))
                cur.execute(
                    "select public.learning_worker_update_failed(%s::uuid, %s, %s)",
                    (context.submission_id, code, clean_message),
                )
            conn.commit()
