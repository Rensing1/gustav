"""Pure implementation of the approved ``gustav-practice-v1`` scheduler.

Why:
    Scheduling is a pedagogical business rule. This module deliberately has no
    database, clock, web-framework or AI dependency: validated inputs always
    produce the same IEEE-754 binary64 result and exact due instant.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import math


SCHEDULER_VERSION = "gustav-practice-v1"
SECONDS_PER_DAY = 86_400
TARGET_RETENTION = 0.90
MIN_STABILITY_DAYS = 1.0
MAX_STABILITY_DAYS = 36_525.0


@dataclass(frozen=True)
class PreviousPracticeState:
    """Scheduler-relevant state before one valid practice attempt."""

    stability_days: float
    interval_seconds: int
    due_at: datetime
    last_attempt_at: datetime
    review_count: int
    scheduler_version: str


@dataclass(frozen=True)
class SchedulerResult:
    """Complete deterministic state after one valid practice attempt."""

    stability_days: float
    interval_seconds: int
    due_at: datetime
    last_attempt_at: datetime
    review_count: int
    scheduler_version: str
    retrievability: float | None
    schedule_changed: bool


def _utc(value: datetime, field: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"invalid_{field}")
    return value.astimezone(timezone.utc)


def _fulfillment(value: object) -> float:
    if isinstance(value, bool):
        raise ValueError("invalid_fulfillment")
    try:
        fulfillment = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid_fulfillment") from exc
    if not math.isfinite(fulfillment) or not 0.0 <= fulfillment <= 1.0:
        raise ValueError("invalid_fulfillment")
    return fulfillment


def _classification(value: object, fulfillment: float, supported: bool) -> str:
    classification = str(value or "").strip().lower()
    if classification not in {"mastered", "partial", "insufficient"}:
        raise ValueError("invalid_classification")
    if supported and classification == "mastered":
        raise ValueError("invalid_supported_classification")
    if classification == "mastered" and fulfillment < 0.85:
        raise ValueError("classification_mismatch")
    # H5P partial results may be any strict fraction below one, while native
    # partial results stop below 0.85. Source-specific validation happens
    # before this shared scheduler boundary.
    if classification == "partial" and not (
        0.0 < fulfillment < 1.0 or (supported and fulfillment == 1.0)
    ):
        raise ValueError("classification_mismatch")
    if classification == "insufficient" and fulfillment >= 0.40:
        raise ValueError("classification_mismatch")
    return classification


def _validate_previous(previous: PreviousPracticeState) -> PreviousPracticeState:
    stability = float(previous.stability_days)
    if not math.isfinite(stability) or not MIN_STABILITY_DAYS <= stability <= MAX_STABILITY_DAYS:
        raise ValueError("invalid_previous_stability")
    if isinstance(previous.interval_seconds, bool) or int(previous.interval_seconds) <= 0:
        raise ValueError("invalid_previous_interval")
    if int(previous.review_count) < 1:
        raise ValueError("invalid_review_count")
    if previous.scheduler_version != SCHEDULER_VERSION:
        raise ValueError("invalid_scheduler_version")
    return PreviousPracticeState(
        stability_days=stability,
        interval_seconds=int(previous.interval_seconds),
        due_at=_utc(previous.due_at, "previous_due_at"),
        last_attempt_at=_utc(previous.last_attempt_at, "previous_attempt_at"),
        review_count=int(previous.review_count),
        scheduler_version=previous.scheduler_version,
    )


def _interval_seconds(stability_days: float) -> int:
    seconds = stability_days * SECONDS_PER_DAY
    if not math.isfinite(seconds) or seconds <= 0:
        raise ValueError("invalid_scheduler_result")
    return math.floor(seconds + 0.5)


def classify_native(fulfillment: object, *, supported: bool) -> str:
    """Return the learner-visible native classification from rubric fulfillment."""

    value = _fulfillment(fulfillment)
    if value >= 0.85:
        return "partial" if supported else "secure"
    if value >= 0.40:
        return "partial"
    return "insufficient"


def classify_h5p(fulfillment: object, *, supported: bool) -> str:
    """Return the learner-visible H5P classification from its score fraction."""

    value = _fulfillment(fulfillment)
    if value == 1.0:
        return "partial" if supported else "secure"
    if value > 0.0:
        return "partial"
    return "insufficient"


def scheduler_classification(visible_classification: str) -> str:
    """Map the learner word ``secure`` to the normative scheduler word."""

    return "mastered" if visible_classification == "secure" else visible_classification


def schedule(
    *,
    previous: PreviousPracticeState | None,
    completed_at: datetime,
    fulfillment: object,
    classification: object,
    supported_recall: bool,
) -> SchedulerResult:
    """Calculate one exact scheduler transition.

    Parameters:
        previous: Existing state, or ``None`` for a learner's first exposure.
        completed_at: A timezone-aware completion instant.
        fulfillment: Finite rubric or score fraction in ``[0, 1]``.
        classification: Normative ``mastered``, ``partial`` or ``insufficient``.
        supported_recall: Whether solution access supported this attempt.

    Permissions:
        None. This is a pure domain function; authorization belongs to the
        calling use case before any state is loaded or persisted.
    """

    completed = _utc(completed_at, "completed_at")
    e = _fulfillment(fulfillment)
    supported = bool(supported_recall)
    kind = _classification(classification, e, supported)

    if previous is None:
        if supported:
            raise ValueError("supported_initial_attempt")
        quality = 1.0 if kind == "mastered" else e
        raw_stability = math.pow(2.0, quality)
        if not math.isfinite(raw_stability):  # pragma: no cover - bounded input
            raise ValueError("invalid_scheduler_result")
        stability = min(MAX_STABILITY_DAYS, max(MIN_STABILITY_DAYS, raw_stability))
        interval = _interval_seconds(stability)
        return SchedulerResult(
            stability_days=stability,
            interval_seconds=interval,
            due_at=completed + timedelta(seconds=interval),
            last_attempt_at=completed,
            review_count=1,
            scheduler_version=SCHEDULER_VERSION,
            retrievability=None,
            schedule_changed=True,
        )

    state = _validate_previous(previous)
    elapsed_seconds = (completed - state.last_attempt_at).total_seconds()
    if elapsed_seconds < 0:
        raise ValueError("attempt_before_previous")
    elapsed_days = elapsed_seconds / SECONDS_PER_DAY
    retrievability = math.pow(1.0 + elapsed_days / (9.0 * state.stability_days), -1.0)
    if not math.isfinite(retrievability):
        raise ValueError("invalid_retrievability")

    if supported or (kind == "mastered" and elapsed_seconds < SECONDS_PER_DAY):
        return SchedulerResult(
            stability_days=state.stability_days,
            interval_seconds=state.interval_seconds,
            due_at=state.due_at,
            last_attempt_at=completed,
            review_count=state.review_count + 1,
            scheduler_version=SCHEDULER_VERSION,
            retrievability=retrievability,
            schedule_changed=False,
        )

    if kind == "mastered":
        raw_stability = state.stability_days * (
            1.0 + e * (1.0 - retrievability) / (1.0 - TARGET_RETENTION)
        )
    else:
        exponent = 2.0 * (1.0 + retrievability / TARGET_RETENTION)
        raw_stability = 1.0 + (state.stability_days - 1.0) * math.pow(e, exponent)
    if not math.isfinite(raw_stability):
        raise ValueError("invalid_scheduler_result")
    stability = min(MAX_STABILITY_DAYS, max(MIN_STABILITY_DAYS, raw_stability))
    interval = _interval_seconds(stability)
    return SchedulerResult(
        stability_days=stability,
        interval_seconds=interval,
        due_at=completed + timedelta(seconds=interval),
        last_attempt_at=completed,
        review_count=state.review_count + 1,
        scheduler_version=SCHEDULER_VERSION,
        retrievability=retrievability,
        schedule_changed=True,
    )
