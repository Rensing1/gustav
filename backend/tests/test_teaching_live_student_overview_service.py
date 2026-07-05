"""Unit tests for the student live overview service.

Focus:
    - normalize selected unit ids canonically
    - batch-load tasks for the selected course units
    - keep the service independent from HTTP and HTML concerns
"""

from __future__ import annotations

from typing import List, Sequence

from backend.teaching.services.live_student_overview import StudentLiveOverviewService


LOWER_UNIT_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
UPPER_UNIT_ID = LOWER_UNIT_ID.upper()


class FakeStudentLiveOverviewRepo:
    def __init__(self) -> None:
        self.batch_calls: list[tuple[str, tuple[str, ...], str]] = []

    def list_course_units_for_owner(self, course_id: str, owner_sub: str) -> List[dict]:
        return [
            {"id": LOWER_UNIT_ID, "title": "Einheit A"},
            {"id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", "title": "Einheit B"},
        ]

    def course_has_member(self, course_id: str, owner_sub: str, student_sub: str) -> bool:
        return True

    def list_tasks_for_course_units_owner(
        self,
        course_id: str,
        unit_ids: Sequence[str],
        owner_sub: str,
    ) -> List[dict]:
        normalized = tuple(str(unit_id) for unit_id in unit_ids)
        self.batch_calls.append((course_id, normalized, owner_sub))
        return [
            {
                "unit_id": LOWER_UNIT_ID,
                "id": "task-1",
                "instruction_md": "### Aufgabe A1",
                "position": 1,
                "kind": "native",
            }
        ]

    def list_tasks_for_course_unit_owner(self, course_id: str, unit_id: str, owner_sub: str) -> List[dict]:
        raise AssertionError("service should batch-load tasks for selected units")

    def list_latest_submission_aggregates_for_owner(
        self,
        *,
        course_id: str,
        owner_sub: str,
        student_sub: str,
        unit_ids: Sequence[str],
    ) -> List[dict]:
        return [
            {
                "unit_id": LOWER_UNIT_ID,
                "task_id": "task-1",
                "has_submission": True,
                "average_score": 8.0,
                "h5p_completed": None,
            }
        ]


def test_student_live_overview_normalizes_uuid_filters_and_batches_tasks() -> None:
    repo = FakeStudentLiveOverviewRepo()
    service = StudentLiveOverviewService(repo=repo)

    overview = service.build(
        course_id="course-1",
        owner_sub="teacher-1",
        student_sub="student-1",
        raw_unit_ids=[UPPER_UNIT_ID],
    )

    assert [unit.id for unit in overview.units] == [LOWER_UNIT_ID]
    assert repo.batch_calls == [("course-1", (LOWER_UNIT_ID,), "teacher-1")]
    assert overview.units[0].tasks[0].has_submission is True
    assert overview.units[0].tasks[0].average_score == 8.0
