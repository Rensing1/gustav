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

from dataclasses import dataclass, field
from typing import Optional, Protocol, Sequence


# ----------------------------- Result types ---------------------------------


@dataclass
class TokenUsageEvent:
    """Technical token counter for one observed model response.

    Parameters:
        event_key: Capture-generated UUID used for idempotent persistence.
        model: Provider/model identifier as reported by the configured LM.
        stage: Processing stage (`ocr`, `analysis`, `feedback`).
        modality: Input modality (`text`, `visual`).
        call_kind: Call type (`primary`, `repair`, `no_criteria`).
        usage_known: Whether token counters are known for this response.
        input_tokens/output_tokens/total_tokens: Optional provider counters.
        unknown_reason: Stable technical code when usage is unknown.
        error_code: Stable content-free code when the model call failed.
    """

    event_key: str
    model: str
    stage: str
    modality: str
    call_kind: str
    usage_known: bool
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    unknown_reason: str | None = None
    error_code: str | None = None


@dataclass
class VisionResult:
    """Vision adapter response.

    Parameters:
        text_md: Markdown text extracted from the submission.
        raw_metadata: Optional adapter-specific diagnostics for observability.
    """

    text_md: str
    raw_metadata: Optional[dict] = None
    usage_events: list[TokenUsageEvent] = field(default_factory=list)


@dataclass
class FeedbackResult:
    """Feedback adapter response.

    Parameters:
        feedback_md: Markdown feedback presented to the learner.
        analysis_json: Criteria-based report; schema='criteria.v2'.
        parse_status: Optional status marker (e.g., "parsed_structured", "repaired_structured") for telemetry.
    """

    feedback_md: str
    analysis_json: dict
    parse_status: Optional[str] = None
    usage_events: list[TokenUsageEvent] = field(default_factory=list)


# ----------------------------- Protocols ------------------------------------


class VisionAdapterProtocol(Protocol):
    """Vision adapter turns submissions into Markdown text."""

    def extract(self, *, submission: dict, job_payload: dict) -> VisionResult:
        ...


class FeedbackAdapterProtocol(Protocol):
    """Feedback adapter generates formative feedback for Markdown text."""

    def analyze(self, *, text_md: str, criteria: Sequence[str]) -> FeedbackResult:
        ...

    def analyze_dialog(
        self,
        *,
        student_performance: dict,
        conversation_context: dict,
        criteria: Sequence[str],
        instruction_md: str,
    ) -> FeedbackResult:
        ...


# ------------------------------ Errors --------------------------------------


class VisionError(Exception):
    """Base class for Vision adapter failures."""

    def __init__(self, *args: object, usage_events: list[TokenUsageEvent] | None = None) -> None:
        super().__init__(*args)
        self.usage_events = list(usage_events or [])


class VisionTransientError(VisionError):
    """Recoverable Vision error; worker should retry with backoff."""


class VisionPermanentError(VisionError):
    """Non-recoverable Vision error; worker marks submission failed."""


class FeedbackError(Exception):
    """Base class for Feedback adapter failures."""

    def __init__(self, *args: object, usage_events: list[TokenUsageEvent] | None = None) -> None:
        super().__init__(*args)
        self.usage_events = list(usage_events or [])


class FeedbackTransientError(FeedbackError):
    """Recoverable Feedback error; worker should retry."""


class FeedbackPermanentError(FeedbackError):
    """Non-recoverable Feedback error; worker marks submission failed."""


class FeedbackInvalidAnalysisError(FeedbackPermanentError):
    """Deterministic structured-analysis error; retrying would not help."""


__all__ = [
    # Results
    "TokenUsageEvent",
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
    "FeedbackInvalidAnalysisError",
]
