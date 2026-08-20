import pytest

from backend.learning.usecases.submissions import FinalizeLatestDraftInput, FinalizeLatestDraftUseCase


class RecordingRepo:
    def __init__(self) -> None:
        self.finalized: dict[str, object] | None = None

    def finalize_latest_feedback_submission(
        self,
        *,
        student_sub: str,
        course_id: str,
        task_id: str,
        feedback_submission_id: str,
        idempotency_key: str | None,
    ) -> dict:
        self.finalized = {
            "student_sub": student_sub,
            "course_id": course_id,
            "task_id": task_id,
            "feedback_submission_id": feedback_submission_id,
            "idempotency_key": idempotency_key,
        }
        return {"id": "final-submission"}


def test_finalize_usecase_binds_the_selected_feedback_submission() -> None:
    repo = RecordingRepo()
    usecase = FinalizeLatestDraftUseCase(repo)  # type: ignore[arg-type]

    result = usecase.execute(
        FinalizeLatestDraftInput(
            course_id="course-1",
            task_id="task-1",
            student_sub="student-1",
            feedback_submission_id="feedback-1",
            idempotency_key="finalize-feedback-1",
        )
    )

    assert result == {"id": "final-submission"}
    assert repo.finalized == {
        "student_sub": "student-1",
        "course_id": "course-1",
        "task_id": "task-1",
        "feedback_submission_id": "feedback-1",
        "idempotency_key": "finalize-feedback-1",
    }


def test_finalize_usecase_rejects_a_key_for_another_feedback_submission() -> None:
    repo = RecordingRepo()
    usecase = FinalizeLatestDraftUseCase(repo)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="idempotency_key_mismatch"):
        usecase.execute(
            FinalizeLatestDraftInput(
                course_id="course-1",
                task_id="task-1",
                student_sub="student-1",
                feedback_submission_id="feedback-1",
                idempotency_key="finalize-feedback-2",
            )
        )

    assert repo.finalized is None
