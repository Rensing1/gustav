"""
DSPy vision program (minimal, deterministic scaffold).

Intent:
    Provide a callable that the local Vision adapter may use when `dspy` is
    importable, returning Markdown text and lightweight metadata.

Design:
    - Deterministic, no heavy model wiring. Educational scaffold only.
    - Accepts the submission snapshot and job payload (mime, storage_key).
    - Returns a concise Markdown text extraction/summary.
"""

from __future__ import annotations

from typing import Dict


def extract_text(*, submission: Dict, job_payload: Dict) -> tuple[str, dict]:
    """Produce a tiny Markdown summary of the input via DSPy path.

    Parameters:
        submission: Minimal submission row snapshot used by the worker.
        job_payload: Queue payload with `mime_type` and `storage_key`.

    Returns:
        `(text_md, meta)` where `meta` contains adapter diagnostics.
    """
    try:  # pragma: no cover - presence is asserted in adapter tests indirectly
        import dspy  # type: ignore
        _ = getattr(dspy, "__version__", None)
    except Exception:
        raise ImportError("dspy is not available")

    kind = (submission or {}).get("kind") or "unknown"
    mime = (job_payload or {}).get("mime_type") or (submission or {}).get("mime_type") or "n/a"
    storage = (job_payload or {}).get("storage_key") or "n/a"

    text_md = (
        f"### DSPy Vision\n\nKind: {kind}; MIME: {mime}.\n\n"
        f"Quelle: {storage}"
    )
    meta = {"adapter": "local_vision", "backend": "dspy", "program": "dspy_vision"}
    return text_md, meta
