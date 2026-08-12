"""Deterministic completion of asynchronously evaluated practice attempts.

Why:
    The language model may explain criterion results, but it must never decide
    the learner's fulfillment ratio, classification or next due date. This
    module validates the structured result and applies the released scheduler
    in ordinary application code.
"""

from __future__ import annotations

from datetime import datetime
import math
from typing import Sequence

from backend.learning.practice.scheduler import (
    PreviousPracticeState,
    classify_native,
    schedule,
    scheduler_classification,
)


def fulfillment_from_analysis(analysis: dict, criteria: Sequence[str]) -> float:
    """Return the equal average of trusted ten-point criterion results.

    Every configured criterion must have exactly one result in the original
    order. The AI contract always scores each criterion from zero to ten;
    accepting any other maximum would make the deterministic result ambiguous.
    """

    results = analysis.get("criteria_results") if isinstance(analysis, dict) else None
    if not criteria or not isinstance(results, list) or len(results) != len(criteria):
        raise ValueError("invalid_practice_analysis")

    normalized_scores: list[float] = []
    for expected, result in zip(criteria, results, strict=True):
        if not isinstance(result, dict) or str(result.get("criterion") or "") != str(expected):
            raise ValueError("invalid_practice_analysis")
        try:
            score = float(result["score"])
            maximum = float(result["max_score"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("invalid_practice_analysis") from exc
        if not math.isfinite(score) or not math.isfinite(maximum) or maximum != 10 or not 0 <= score <= 10:
            raise ValueError("invalid_practice_analysis")
        normalized_scores.append(score / 10)
    return sum(normalized_scores) / len(normalized_scores)


def complete_worker_practice_attempt(
    *, conn, submission_id: str, analysis_json: dict, feedback_md: str
) -> None:  # noqa: ANN001
    """Complete a linked practice attempt inside the worker transaction.

    The database helpers lock and persist the learner-owned rows. If the
    submission is an ordinary learning submission, the context helper returns
    no row and this function deliberately does nothing.
    """

    with conn.cursor() as cur:
        cur.execute(
            "select * from public.learning_worker_get_practice_attempt_context(%s::uuid)",
            (submission_id,),
        )
        row = cur.fetchone()
    if not row:
        return

    values = dict(row) if hasattr(row, "keys") else {
        name: row[index]
        for index, name in enumerate(
            (
                "attempt_id", "criteria", "presentation_number", "solution_seen",
                "support_pending", "previous_stability_days", "previous_interval_seconds",
                "previous_due_at", "previous_last_attempt_at", "previous_review_count",
                "previous_scheduler_version", "completed_at",
            )
        )
    }
    fulfillment = fulfillment_from_analysis(analysis_json, list(values["criteria"] or []))
    supported = bool(values["solution_seen"] or values["support_pending"] or int(values["presentation_number"]) == 2)
    classification = classify_native(fulfillment, supported=supported)
    previous = None
    if values["previous_stability_days"] is not None:
        previous = PreviousPracticeState(
            stability_days=float(values["previous_stability_days"]),
            interval_seconds=int(values["previous_interval_seconds"]),
            due_at=values["previous_due_at"],
            last_attempt_at=values["previous_last_attempt_at"],
            review_count=int(values["previous_review_count"]),
            scheduler_version=str(values["previous_scheduler_version"]),
        )
    completed_at = values["completed_at"]
    if not isinstance(completed_at, datetime):  # pragma: no cover - DB contract guard
        raise ValueError("invalid_practice_completion_time")
    result = schedule(
        previous=previous,
        classification=scheduler_classification(classification),
        fulfillment=fulfillment,
        completed_at=completed_at,
        supported_recall=supported,
    )
    with conn.cursor() as cur:
        cur.execute(
            """
            select public.learning_worker_complete_practice_attempt(
              %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s
            )
            """,
            (
                values["attempt_id"], fulfillment, classification, supported,
                result.stability_days, result.interval_seconds, result.due_at,
                completed_at, feedback_md,
            ),
        )


def fail_worker_practice_attempt(*, conn, submission_id: str, error_code: str) -> None:  # noqa: ANN001
    """Keep a terminal technical failure in the audit and reopen its item."""

    with conn.cursor() as cur:
        cur.execute(
            "select public.learning_worker_fail_practice_attempt(%s::uuid, %s)",
            (submission_id, error_code),
        )
