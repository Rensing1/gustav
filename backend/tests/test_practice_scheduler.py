"""Normative golden, boundary and property tests for gustav-practice-v1."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import math

import pytest

from backend.learning.practice.scheduler import (
    PreviousPracticeState,
    classify_h5p,
    classify_native,
    schedule,
)


UTC = timezone.utc
BASE = datetime(2026, 8, 4, 8, 0, tzinfo=UTC)


def previous(stability: float, *, last: datetime = BASE) -> PreviousPracticeState:
    interval = math.floor(stability * 86_400 + 0.5)
    return PreviousPracticeState(
        stability_days=stability,
        interval_seconds=interval,
        due_at=last + timedelta(seconds=interval),
        last_attempt_at=last,
        review_count=1,
        scheduler_version="gustav-practice-v1",
    )


@pytest.mark.parametrize(
    ("state", "completed_at", "fulfillment", "classification", "supported", "expected_s", "seconds", "due", "changed"),
    [
        (None, BASE, 0.00, "insufficient", False, 1.0, 86_400, "2026-08-05T08:00:00+00:00", True),
        (None, BASE, 0.40, "partial", False, 1.319507911, 114_005, "2026-08-05T15:40:05+00:00", True),
        (None, BASE, 0.84, "partial", False, 1.790050142, 154_660, "2026-08-06T02:57:40+00:00", True),
        (None, BASE, 0.85, "mastered", False, 2.0, 172_800, "2026-08-06T08:00:00+00:00", True),
        (None, BASE, 0.99, "partial", False, 1.986184991, 171_606, "2026-08-06T07:40:06+00:00", True),
        (previous(2), BASE + timedelta(days=2), 1.0, "mastered", False, 4.0, 345_600, "2026-08-10T08:00:00+00:00", True),
        (previous(2), BASE + timedelta(days=1), 1.0, "mastered", False, 3.052631579, 263_747, "2026-08-08T09:15:47+00:00", True),
        (previous(2), BASE + timedelta(hours=12), 1.0, "mastered", False, 2.0, 172_800, "2026-08-06T08:00:00+00:00", False),
        (previous(30), BASE + timedelta(days=30), 0.60, "partial", False, 4.7584, 411_126, "2026-09-08T02:12:06+00:00", True),
        (previous(30), BASE + timedelta(days=30), 0.00, "insufficient", False, 1.0, 86_400, "2026-09-04T08:00:00+00:00", True),
        (previous(30), BASE + timedelta(days=3), 0.60, "partial", False, 4.397197761, 379_918, "2026-08-11T17:31:58+00:00", True),
        (previous(30), BASE + timedelta(days=300), 1.0, "mastered", False, 187.894736842, 16_234_105, "2027-12-05T05:28:25+00:00", True),
        (previous(30), BASE + timedelta(days=30), 0.60, "partial", True, 30.0, 2_592_000, "2026-09-03T08:00:00+00:00", False),
        (previous(30_000), datetime(2108, 9, 23, 8, 0, tzinfo=UTC), 1.0, "mastered", False, 36_525.0, 3_155_760_000, "2208-09-24T08:00:00+00:00", True),
    ],
)
def test_gustav_practice_v1_golden_vectors(
    state: PreviousPracticeState | None,
    completed_at: datetime,
    fulfillment: float,
    classification: str,
    supported: bool,
    expected_s: float,
    seconds: int,
    due: str,
    changed: bool,
) -> None:
    result = schedule(
        previous=state,
        completed_at=completed_at,
        fulfillment=fulfillment,
        classification=classification,
        supported_recall=supported,
    )
    assert result.stability_days == pytest.approx(expected_s, abs=1e-9)
    assert result.interval_seconds == seconds
    assert result.due_at.isoformat() == due
    assert result.schedule_changed is changed
    assert result.last_attempt_at == completed_at


def test_invalid_fulfillment_rejects_without_a_result() -> None:
    with pytest.raises(ValueError, match="invalid_fulfillment"):
        schedule(
            previous=previous(2),
            completed_at=BASE + timedelta(days=3),
            fulfillment=1.01,
            classification="mastered",
            supported_recall=False,
        )


@pytest.mark.parametrize(
    ("value", "expected"),
    [(0.0, "insufficient"), (0.399999, "insufficient"), (0.4, "partial"), (0.849999, "partial"), (0.85, "secure"), (1.0, "secure")],
)
def test_native_classification_boundaries(value: float, expected: str) -> None:
    assert classify_native(value, supported=False) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [(0.0, "insufficient"), (0.01, "partial"), (0.99, "partial"), (1.0, "secure")],
)
def test_h5p_classification_boundaries(value: float, expected: str) -> None:
    assert classify_h5p(value, supported=False) == expected


def test_supported_classifications_are_capped_and_supported_new_state_is_rejected() -> None:
    assert classify_native(1.0, supported=True) == "partial"
    assert classify_h5p(1.0, supported=True) == "partial"
    with pytest.raises(ValueError, match="supported_initial_attempt"):
        schedule(
            previous=None,
            completed_at=BASE,
            fulfillment=0.6,
            classification="partial",
            supported_recall=True,
        )


def test_supported_perfect_recall_is_a_valid_noop() -> None:
    state = previous(2)
    result = schedule(
        previous=state,
        completed_at=BASE + timedelta(days=1),
        fulfillment=1.0,
        classification="partial",
        supported_recall=True,
    )
    assert result.stability_days == state.stability_days
    assert result.due_at == state.due_at


def test_scheduler_properties_across_fulfillment_and_elapsed_samples() -> None:
    state = previous(30)
    reductions = [
        schedule(previous=state, completed_at=BASE + timedelta(days=30), fulfillment=e, classification="partial" if e >= 0.4 else "insufficient", supported_recall=False).stability_days
        for e in (0.0, 0.2, 0.4, 0.6, 0.84)
    ]
    assert reductions == sorted(reductions)
    assert all(1 <= value <= 30 for value in reductions)
    growth = [
        schedule(previous=state, completed_at=BASE + timedelta(days=days), fulfillment=1.0, classification="mastered", supported_recall=False).stability_days
        for days in (1, 3, 15, 30, 60, 300)
    ]
    assert growth == sorted(growth)
    assert all(30 <= value <= 36_525 for value in growth)


def test_negative_elapsed_and_non_finite_values_are_rejected() -> None:
    with pytest.raises(ValueError, match="attempt_before_previous"):
        schedule(previous=previous(2), completed_at=BASE - timedelta(seconds=1), fulfillment=1.0, classification="mastered", supported_recall=False)
    for invalid in (math.nan, math.inf, -math.inf):
        with pytest.raises(ValueError, match="invalid_fulfillment"):
            schedule(previous=None, completed_at=BASE, fulfillment=invalid, classification="partial", supported_recall=False)
