"""Submission payload validation and dev-only PDF processing helpers."""

from __future__ import annotations

import importlib
import os
import sys as _sys
from pathlib import Path as _Path
from typing import Any

from backend.storage.learning_policy import ALLOWED_FILE_MIME, ALLOWED_IMAGE_MIME, STORAGE_KEY_RE


def _learning_module():
    module = _sys.modules.get("backend.web.routes.learning")
    if module is None:  # pragma: no cover - defensive import fallback
        module = importlib.import_module("backend.web.routes.learning")
    return module


def _max_upload_bytes() -> int:
    return int(_learning_module()._max_upload_bytes())


def _storage_bucket() -> str:
    return str(_learning_module()._storage_bucket())


def _get_repo():
    return _learning_module()._get_repo()


def validate_submission_payload(payload: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Validate and normalize text, upload, and H5P submission payloads."""

    if not isinstance(payload, dict):
        raise ValueError("invalid_input")
    intent_raw = payload.get("intent")
    if intent_raw is None:
        intent = "submit"
    elif not isinstance(intent_raw, str):
        raise ValueError("invalid_input")
    else:
        intent = intent_raw.strip().lower()
    if intent not in {"feedback", "submit"}:
        raise ValueError("invalid_input")
    kind = payload.get("kind")
    if kind not in ("text", "image", "file", "h5p"):
        raise ValueError("invalid_input")
    if kind == "text":
        text_body = payload.get("text_body")
        if not isinstance(text_body, str) or not text_body.strip():
            raise ValueError("invalid_input")
        if len(text_body) > 65_536:
            raise ValueError("invalid_input")
        return kind, {"intent": intent, "text_body": text_body.strip()}
    if kind == "h5p":
        required = {"score_raw", "score_max"}
        if not required.issubset(payload.keys()):
            raise ValueError("invalid_h5p_payload")
        try:
            raw_int = int(payload.get("score_raw"))
            max_int = int(payload.get("score_max"))
        except (TypeError, ValueError):
            raise ValueError("invalid_h5p_payload") from None
        if raw_int < 0 or max_int < 0 or raw_int > max_int:
            raise ValueError("invalid_h5p_payload")
        return kind, {"intent": intent, "score_raw": raw_int, "score_max": max_int}

    detail = "invalid_image_payload" if kind == "image" else "invalid_file_payload"
    required = {"storage_key", "mime_type", "size_bytes", "sha256"}
    if not required.issubset(payload.keys()):
        raise ValueError(detail)
    size_bytes = payload.get("size_bytes")
    try:
        size_int = int(size_bytes)
    except (TypeError, ValueError):
        raise ValueError(detail) from None
    if size_int <= 0 or size_int > _max_upload_bytes():
        raise ValueError(detail)
    mime_type_raw = payload.get("mime_type")
    if not isinstance(mime_type_raw, str) or not mime_type_raw:
        raise ValueError(detail)
    mime_type = mime_type_raw.strip().lower()
    allowed_mime = ALLOWED_IMAGE_MIME if kind == "image" else ALLOWED_FILE_MIME
    if mime_type not in allowed_mime:
        raise ValueError(detail)
    storage_key = payload.get("storage_key")
    if not isinstance(storage_key, str) or not storage_key:
        raise ValueError(detail)
    if not STORAGE_KEY_RE.fullmatch(storage_key):
        raise ValueError(detail)
    sha256 = payload.get("sha256")
    if not isinstance(sha256, str):
        raise ValueError(detail)
    sha256_normalized = sha256.strip().lower()
    if len(sha256_normalized) != 64 or any(c not in "0123456789abcdef" for c in sha256_normalized):
        raise ValueError(detail)
    return kind, {
        "intent": intent,
        "storage_key": storage_key,
        "mime_type": mime_type,
        "size_bytes": size_int,
        "sha256": sha256_normalized,
    }


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
        from backend.vision.pipeline import process_pdf_bytes  # type: ignore
        from backend.vision.persistence import SubmissionScope, persist_rendered_pages  # type: ignore
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
