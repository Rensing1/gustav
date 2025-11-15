"""TDD: Persist rendered PDF pages to storage and update status.

We validate that the persistence helper writes deterministic page keys and
marks the submission as "extracted" with the list of keys.
"""
from __future__ import annotations

from typing import List


class _FakeStorage:
    def __init__(self) -> None:
        self.calls: List[tuple[str, str, bytes, str]] = []

    def put_object(self, *, bucket: str, key: str, body: bytes, content_type: str) -> None:
        self.calls.append((bucket, key, body, content_type))


class _FakeRepo:
    def __init__(self) -> None:
        self.marked: tuple[str, List[str]] | None = None

    def mark_extracted(self, *, submission_id: str, page_keys: List[str]) -> None:
        self.marked = (submission_id, list(page_keys))


def test_persist_rendered_pages_writes_pngs_and_marks_extracted():
    from backend.vision.persistence import SubmissionScope, persist_rendered_pages

    # Arrange: two minimal pages
    class _Page:
        def __init__(self, b: bytes) -> None:
            self.png_bytes = b
            self.width = 100
            self.height = 200

    pages = [_Page(b"p1"), _Page(b"p2")]  # duck-type RenderPage
    storage = _FakeStorage()
    repo = _FakeRepo()
    scope = SubmissionScope(
        course_id="COURSE-1",
        task_id="TASK-1",
        student_sub="student-42",
        submission_id="00000000-0000-0000-0000-00000000abcd",
    )

    # Act
    keys = persist_rendered_pages(
        storage=storage,
        bucket="learning-submissions",
        scope=scope,
        pages=pages,  # type: ignore[arg-type]
        repo=repo,
    )

    # Assert: two writes, ordered, correct content type and suffixes
    assert len(storage.calls) == 2
    assert all(call[0] == "learning-submissions" for call in storage.calls)
    assert storage.calls[0][3] == "image/png" and storage.calls[1][3] == "image/png"
    k1 = storage.calls[0][1]
    k2 = storage.calls[1][1]
    assert k1.endswith("/page_0001.png") and k2.endswith("/page_0002.png")
    # Prefix includes the submission scope
    for k in (k1, k2):
        assert "/derived/00000000-0000-0000-0000-00000000abcd/" in k

    # Keys returned and repo marked extracted with the same list
    assert keys == [k1, k2]
    assert repo.marked is not None
    marked_submission, marked_keys = repo.marked
    assert marked_submission == scope.submission_id
    assert marked_keys == keys

