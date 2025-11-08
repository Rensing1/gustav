"""
Ports for Learning adapters: shared result types, protocols, and errors.

Intent:
    Provide framework-agnostic contracts between the worker and concrete
    adapters (local, stub, cloud). Keeping these definitions in a dedicated
    module avoids circular imports and clarifies boundaries.

Design:
    - Result dataclasses: VisionResult, FeedbackResult
    - Protocols: VisionAdapterProtocol, FeedbackAdapterProtocol
    - Error taxonomy: transient vs. permanent for Vision/Feedback

Notes:
    These types are intentionally minimal for educational clarity (KISS).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol, Sequence


# ----------------------------- Result types ---------------------------------


@dataclass
class VisionResult:
    """Vision adapter response.

    Parameters:
        text_md: Markdown text extracted from the submission.
        raw_metadata: Optional adapter-specific diagnostics for observability.
    """

    text_md: str
    raw_metadata: Optional[dict] = None


@dataclass
class FeedbackResult:
    """Feedback adapter response.

    Parameters:
        feedback_md: Markdown feedback presented to the learner.
        analysis_json: Criteria-based report; schema='criteria.v2'.
    """

    feedback_md: str
    analysis_json: dict


# ----------------------------- Protocols ------------------------------------


class VisionAdapterProtocol(Protocol):
    """Vision adapter turns submissions into Markdown text."""

    def extract(self, *, submission: dict, job_payload: dict) -> VisionResult:
        ...


class FeedbackAdapterProtocol(Protocol):
    """Feedback adapter generates formative feedback for Markdown text."""

    def analyze(self, *, text_md: str, criteria: Sequence[str]) -> FeedbackResult:
        ...


# ------------------------------ Errors --------------------------------------


class VisionError(Exception):
    """Base class for Vision adapter failures."""


class VisionTransientError(VisionError):
    """Recoverable Vision error; worker should retry with backoff."""


class VisionPermanentError(VisionError):
    """Non-recoverable Vision error; worker marks submission failed."""


class FeedbackError(Exception):
    """Base class for Feedback adapter failures."""


class FeedbackTransientError(FeedbackError):
    """Recoverable Feedback error; worker should retry."""


class FeedbackPermanentError(FeedbackError):
    """Non-recoverable Feedback error; worker marks submission failed."""


__all__ = [
    # Results
    "VisionResult",
    "FeedbackResult",
    # Protocols
    "VisionAdapterProtocol",
    "FeedbackAdapterProtocol",
    # Errors
    "VisionError",
    "VisionTransientError",
    "VisionPermanentError",
    "FeedbackError",
    "FeedbackTransientError",
    "FeedbackPermanentError",
]
