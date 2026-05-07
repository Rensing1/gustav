"""
Learning repo submission-kind guard.

Intent:
    The DB repo must reject spoofed submission kinds at the persistence boundary
    even if a web adapter misses a task-type rule.
"""

from __future__ import annotations

import pytest

from backend.learning.repo_db import _validate_task_submission_kind


@pytest.mark.parametrize(
    "task_kind,submission_kind,mime_type,error",
    [
        ("filius", "text", None, "invalid_input"),
        ("filius", "image", "image/png", "invalid_input"),
        ("filius", "file", "application/pdf", "invalid_file_payload"),
        ("native", "file", "application/x.filius.fls", "invalid_file_payload"),
        ("visual", "file", "application/x.filius.fls", "invalid_file_payload"),
        ("scratch", "file", "application/x.filius.fls", "invalid_file_payload"),
        ("calliope", "file", "application/x.filius.fls", "invalid_file_payload"),
    ],
)
def test_submission_kind_guard_rejects_wrong_filius_payloads(task_kind: str, submission_kind: str, mime_type: str | None, error: str) -> None:
    with pytest.raises(ValueError) as exc:
        _validate_task_submission_kind(
            task_kind=task_kind,
            submission_kind=submission_kind,
            mime_type=mime_type,
        )

    assert str(exc.value) == error


def test_submission_kind_guard_accepts_filius_fls() -> None:
    _validate_task_submission_kind(
        task_kind="filius",
        submission_kind="file",
        mime_type="application/x.filius.fls",
    )
