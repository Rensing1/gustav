"""
Persistence helpers for rendered PDF pages.

Why:
    After rendering a PDF to per-page PNGs, we need to persist the artifacts
    and record their locations for later OCR/vision processing. This module is
    intentionally thin and IO-focused; higher-level orchestration should call
    into it after authorization and job routing.

Design:
    - Storage keys: submissions/{course}/{task}/{student}/derived/{submission}/page_0001.png
    - Content type: image/png (fixed for now)
    - Repo contract: a tiny port that allows marking a submission as "extracted"
      with a list of page keys.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Protocol

from backend.storage.ports import BinaryWriteStorage
from backend.vision.pdf_renderer import RenderPage


class AnalysisStatusRepo(Protocol):
    """Port for updating analysis status and metadata on a submission."""

    def mark_extracted(self, *, submission_id: str, page_keys: List[str]) -> None: ...


@dataclass(frozen=True)
class SubmissionScope:
    course_id: str
    task_id: str
    student_sub: str
    submission_id: str


def persist_rendered_pages(
    *,
    storage: BinaryWriteStorage,
    bucket: str,
    scope: SubmissionScope,
    pages: List[RenderPage],
    repo: AnalysisStatusRepo,
) -> List[str]:
    """Write rendered pages to storage and mark submission as extracted.

    Intent:
        Persist each page under a deterministic, submission-scoped prefix so
        downstream steps (OCR, UI) can reference them. Update the submission to
        `analysis_status='extracted'` with the list of keys.

    Permissions:
        Caller must ensure the student owns the submission and that the bucket
        is the learning submissions bucket. This function performs only IO.

    Returns:
        List of storage keys written, in page order.
    """
    prefix = (
        f"submissions/{scope.course_id}/{scope.task_id}/{scope.student_sub}/"
        f"derived/{scope.submission_id}"
    )
    keys: List[str] = []
    for idx, page in enumerate(pages, start=1):
        key = f"{prefix}/page_{idx:04}.png"
        storage.put_object(bucket=bucket, key=key, body=page.png_bytes, content_type="image/png")
        keys.append(key)

    repo.mark_extracted(submission_id=scope.submission_id, page_keys=keys)
    return keys

