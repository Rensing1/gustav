"""Submission mapping helpers for the Learning Postgres repository.

Why:
    DBLearningRepo should orchestrate RLS-aware queries and writes. Mapping
    submission rows, sanitizing public error strings, and building deterministic
    analysis stubs are pure data-shaping logic that is easier to test in a
    small DB-free module.
"""

from __future__ import annotations

import json
import re
from typing import Any, Iterable, Optional, Sequence


ERROR_MAX_LENGTH = 256
SENSITIVE_TOKEN_PATTERN = re.compile(r"(?i)(secret|token|password|key)[-_a-z0-9]*\s*[:=]\s*\S+")
FILESYSTEM_PATH_PATTERN = re.compile(r"(?:[A-Za-z]:\\[^\s]+|/[^\s]+)")


def sanitize_error_message(value: Optional[str]) -> Optional[str]:
    """Strip secrets and truncate lengthy adapter errors for safe exposure."""

    if not value:
        return None
    collapsed = " ".join(str(value).split())
    if not collapsed:
        return None
    scrubbed = SENSITIVE_TOKEN_PATTERN.sub("[redacted]", collapsed)
    scrubbed = FILESYSTEM_PATH_PATTERN.sub("[path]", scrubbed)
    if len(scrubbed) > ERROR_MAX_LENGTH:
        scrubbed = scrubbed[: ERROR_MAX_LENGTH - 3].rstrip() + "..."
    return scrubbed


def render_feedback(kind: str, attempt: int) -> str:
    """Return deterministic MVP feedback text for one submission attempt."""

    if kind == "text":
        return f"Attempt {attempt}: Thanks for your explanation."
    if kind == "file":
        return f"Attempt {attempt}: PDF submission received."
    return f"Attempt {attempt}: Image submission received."


def build_analysis_payload(
    *,
    kind: str,
    text_body: Optional[str],
    storage_key: Optional[str],
    sha256: Optional[str],
    criteria: Sequence[str],
) -> dict:
    """Produce the synchronous analysis stub used until ML integration."""

    if kind == "text":
        text = (text_body or "").strip()
    elif kind == "file":
        text = pdf_text_stub(storage_key, sha256)
    else:
        text = image_text_stub(storage_key, sha256)
    length = len(text)
    scores = build_scores(criteria, length)
    return {
        "text": text,
        "length": length,
        "scores": scores,
    }


def build_scores(criteria: Sequence[str], text_length: int) -> list[dict]:
    """Generate rubric-style scores with deterministic, easy-to-read values."""

    names = [criterion for criterion in criteria if criterion]
    if not names:
        names = ["Submission"]
    base_score = 6 if text_length < 20 else 8
    scores: list[dict] = []
    for index, criterion in enumerate(names):
        score = min(10, base_score + min(index, 2))
        scores.append(
            {
                "criterion": criterion,
                "score": score,
                "explanation": "Stubbed analysis until machine learning is integrated.",
            }
        )
    return scores


def image_text_stub(storage_key: Optional[str], sha256: Optional[str]) -> str:
    """Derive a deterministic textual placeholder for OCR output."""

    if storage_key:
        token = storage_key.split("/")[-1]
    elif sha256:
        token = sha256[:12]
    else:
        token = "image"
    return f"OCR placeholder for {token}"


def pdf_text_stub(storage_key: Optional[str], sha256: Optional[str]) -> str:
    """Produce a stable placeholder for PDF-derived text."""

    if storage_key:
        token = storage_key.split("/")[-1]
    elif sha256:
        token = sha256[:12]
    else:
        token = "document.pdf"
    return f"PDF text placeholder for {token}"


def row_to_submission(row: Iterable[Any]) -> dict:
    """Map a DB row to an API submission dict with safe fallbacks."""

    (
        submission_id,
        attempt_nr,
        intent,
        kind,
        score_raw,
        score_max,
        text_body,
        mime_type,
        size_bytes,
        storage_key,
        sha256,
        status,
        analysis_raw,
        feedback_md,
        error_code,
        vision_attempts,
        vision_last_error,
        feedback_last_attempt_at,
        feedback_last_error,
        created_at,
        completed_at,
    ) = list(row)
    if kind == "h5p":
        analysis_payload = None
    elif status != "completed":
        analysis_payload = None
    else:
        analysis_payload = analysis_raw
        if isinstance(analysis_payload, str):
            try:
                analysis_payload = json.loads(analysis_payload)
            except Exception:  # pragma: no cover - defensive
                pass
        if not isinstance(analysis_payload, dict):
            analysis_payload = {}
        existing_text = str(
            (analysis_payload.get("text") if isinstance(analysis_payload, dict) else "") or ""
        )
        if not existing_text.strip():
            if kind == "text":
                analysis_payload["text"] = (text_body or "").strip()
            elif kind == "file":
                analysis_payload["text"] = pdf_text_stub(storage_key, sha256)
            else:
                analysis_payload["text"] = image_text_stub(storage_key, sha256)
    telemetry_attempts = int(vision_attempts or 0)
    return {
        "id": submission_id,
        "attempt_nr": int(attempt_nr),
        "intent": intent,
        "kind": kind,
        "score_raw": score_raw,
        "score_max": score_max,
        "text_body": text_body,
        "mime_type": mime_type,
        "size_bytes": size_bytes,
        "storage_key": storage_key,
        "sha256": sha256,
        "analysis_status": status,
        "analysis_json": analysis_payload,
        "feedback_md": feedback_md if status == "completed" else None,
        "error_code": error_code,
        "vision_attempts": telemetry_attempts,
        "vision_last_error": sanitize_error_message(vision_last_error),
        "feedback_last_attempt_at": feedback_last_attempt_at,
        "feedback_last_error": sanitize_error_message(feedback_last_error),
        "created_at": created_at,
        "completed_at": completed_at,
    }
