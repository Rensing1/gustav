"""Unit tests for Teaching DB task row serialization.

Why:
    The Postgres repository is a boundary between persistence and the Teaching
    use cases. Its plain-dict task shape should match the marker config fields
    exposed by the API contract, even before the web adapter normalizes data.
"""

from __future__ import annotations

from backend.teaching.repo_db import _task_row_to_dict


def _task_row(kind: str) -> tuple[object, ...]:
    return (
        "task-1",
        "unit-1",
        "section-1",
        "Bearbeite die Aufgabe",
        ["Kriterium"],
        None,
        None,
        None,
        1,
        "2026-05-10T09:00:00+00:00",
        "2026-05-10T09:00:00+00:00",
        kind,
        None,
        {},
    )


def test_task_row_to_dict_exposes_filius_marker_config() -> None:
    task = _task_row_to_dict(_task_row("filius"))

    assert task["kind"] == "filius"
    assert task["filius"] == {}
    assert task["h5p"] is None
    assert task["visual"] is None
    assert task["scratch"] is None
    assert task["calliope"] is None
