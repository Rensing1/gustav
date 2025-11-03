"""
Deterministic Vision adapter for local development and tests.

Intent:
    Provide a minimal implementation that adheres to the worker's
    `VisionAdapterProtocol` without requiring external AI services.

Behavior:
    - Text submissions reuse the stored `text_body`.
    - Non-text submissions yield a placeholder Markdown block so the pipeline
      continues without errors.
"""

from __future__ import annotations

from typing import Any, Dict

from backend.learning.workers.process_learning_submission_jobs import VisionResult


class StubVisionAdapter:
    """Return either the submission text or a deterministic placeholder."""

    def extract(self, *, submission: Dict[str, Any], job_payload: Dict[str, Any]) -> VisionResult:
        text_md = submission.get("text_body") or job_payload.get("text_body")
        if not text_md:
            text_md = "## Vision placeholder\n\n_No OCR performed in stub mode._"
        return VisionResult(text_md=text_md, raw_metadata={"adapter": "stub"})


def build() -> StubVisionAdapter:
    """Factory used by the worker to instantiate the adapter."""
    return StubVisionAdapter()
