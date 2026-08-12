"""Deterministic completion rules for native practice attempts."""

from __future__ import annotations

import pytest

from backend.learning.practice.completion import fulfillment_from_analysis
from backend.learning.workers import process_learning_submission_jobs as worker


def test_fulfillment_is_the_equal_average_of_ten_point_criteria() -> None:
    analysis = {
        "criteria_results": [
            {"criterion": "A", "score": 8, "max_score": 10},
            {"criterion": "B", "score": 5, "max_score": 10},
        ]
    }
    assert fulfillment_from_analysis(analysis, ["A", "B"]) == pytest.approx(0.65)


@pytest.mark.parametrize(
    "analysis,criteria",
    [
        ({"criteria_results": []}, ["A"]),
        ({"criteria_results": [{"criterion": "A", "score": 9, "max_score": 9}]}, ["A"]),
        ({"criteria_results": [{"criterion": "A", "score": 1, "max_score": 0}]}, ["A"]),
        ({"criteria_results": [{"criterion": "A", "score": 11, "max_score": 10}]}, ["A"]),
        ({"criteria_results": [{"criterion": "B", "score": 5, "max_score": 10}]}, ["A"]),
    ],
)
def test_fulfillment_rejects_incomplete_or_untrusted_analysis(analysis: dict, criteria: list[str]) -> None:
    with pytest.raises(ValueError, match="invalid_practice_analysis"):
        fulfillment_from_analysis(analysis, criteria)


def test_worker_marks_invalid_practice_analysis_as_terminal_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []
    job = worker.QueuedJob(
        id="11111111-1111-1111-1111-111111111111",
        submission_id="22222222-2222-2222-2222-222222222222",
        retry_count=0,
        payload={"practice_attempt_id": "33333333-3333-3333-3333-333333333333"},
    )

    monkeypatch.setattr(
        worker,
        "complete_worker_practice_attempt",
        lambda **_: (_ for _ in ()).throw(ValueError("invalid_practice_analysis")),
    )
    monkeypatch.setattr(
        worker,
        "_update_submission_failed",
        lambda **kwargs: calls.append(("submission", kwargs["error_code"])),
    )
    monkeypatch.setattr(
        worker,
        "fail_worker_practice_attempt",
        lambda **kwargs: calls.append(("attempt", kwargs["error_code"])),
    )
    monkeypatch.setattr(
        worker,
        "_mark_job_failed",
        lambda **kwargs: calls.append(("job", kwargs["error_code"])),
    )
    monkeypatch.setattr(worker.telemetry, "increment_counter", lambda *args, **kwargs: None)

    assert worker._complete_practice_attempt_or_fail(  # type: ignore[attr-defined]
        conn=object(),
        job=job,
        analysis_json={"criteria_results": []},
        feedback_md="Rückmeldung",
    ) is False
    assert calls == [
        ("submission", "practice_analysis_invalid"),
        ("attempt", "practice_analysis_invalid"),
        ("job", "practice_analysis_invalid"),
    ]
