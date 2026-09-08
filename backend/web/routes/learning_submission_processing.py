"""Submission payload validation and dev-only PDF processing helpers."""

from __future__ import annotations

import importlib
import os
import sys as _sys
from pathlib import Path as _Path
from typing import Any

from backend.learning.submission_payload import validate_submission_payload as validate_payload
from backend.storage.config import get_learning_max_upload_bytes


def _learning_module():
    module = _sys.modules.get("backend.web.routes.learning")
    if module is None:  # pragma: no cover - defensive import fallback
        module = importlib.import_module("backend.web.routes.learning")
    return module


def _storage_bucket() -> str:
    return str(_learning_module()._storage_bucket())


def _get_repo():
    return _learning_module()._get_repo()


def validate_submission_payload(payload: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Supply deployment configuration to the framework-independent input rules."""
    return validate_payload(payload, max_upload_bytes=get_learning_max_upload_bytes())


def dev_try_process_pdf(*, root: str, storage_key: str, submission_id: str, course_id: str, task_id: str, student_sub: str) -> None:
    """Best-effort dev helper: render, persist pages, and mark extracted."""

    base = _Path(root).resolve()
    pdf_path = (base / storage_key).resolve()
    common = os.path.commonpath([str(base), str(pdf_path)])
    if common != str(base) or not pdf_path.exists() or not pdf_path.is_file():
        return

    try:
        data = pdf_path.read_bytes()
    except Exception:
        return

    try:
        from backend.vision.persistence import (  # type: ignore
            SubmissionScope,
            persist_rendered_pages,
        )
        from backend.vision.pipeline import process_pdf_bytes  # type: ignore
    except Exception:
        return

    try:
        pages, _meta = process_pdf_bytes(data)
    except Exception:
        return

    class _FSWriter:
        def __init__(self, root_dir: _Path) -> None:
            self._root = root_dir

        def put_object(self, *, bucket: str, key: str, body: bytes, content_type: str) -> None:  # noqa: D401
            target = (self._root / bucket / key).resolve()
            common2 = os.path.commonpath([str(self._root), str(target)])
            if common2 != str(self._root):
                raise RuntimeError("path_escape_blocked")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(body)

    scope = SubmissionScope(
        course_id=str(course_id), task_id=str(task_id), student_sub=str(student_sub), submission_id=str(submission_id)
    )
    try:
        persist_rendered_pages(
            storage=_FSWriter(base),
            bucket=_storage_bucket(),
            scope=scope,
            pages=pages,
            repo=_get_repo(),  # type: ignore[arg-type]
        )
    except Exception:
        return
