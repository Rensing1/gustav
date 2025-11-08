"""
Integration tests for the PDF preprocessing use case.

We exercise the pipeline that renders PDF submissions into preprocessed page
images, persists them, and transitions the submission status accordingly. The
tests run against the real Postgres schema (via psycopg) while mocking the
rendering pipeline to keep them deterministic and lightweight.
"""
from __future__ import annotations

import os
import types
import uuid
from dataclasses import dataclass

import pytest

from backend.tests.utils.db import require_db_or_skip as _require_db_or_skip

pytest.importorskip("psycopg")

import psycopg  # type: ignore  # noqa: E402

from backend.learning.repo_db import DBLearningRepo  # noqa: E402
from backend.vision.pdf_renderer import PdfRenderError  # noqa: E402

# Import target use case (to be implemented via TDD).
from backend.learning.usecases.pdf_preprocessing import (  # type: ignore  # noqa: E402
    PreprocessPdfSubmissionUseCase,
    SubmissionContext,
)


def _service_dsn() -> str:
    """Return a service-level DSN for setup/teardown operations."""
    host = os.getenv("TEST_DB_HOST", "127.0.0.1")
    port = os.getenv("TEST_DB_PORT", "54322")
    user = os.getenv("APP_DB_USER", "gustav_app")
    password = os.getenv("APP_DB_PASSWORD", "CHANGE_ME_DEV")
    return (
        os.getenv("SERVICE_ROLE_DSN")
        or os.getenv("RLS_TEST_SERVICE_DSN")
        or os.getenv("DATABASE_URL")
        or f"postgresql://{user}:{password}@{host}:{port}/postgres"
    )


@dataclass
class SeededSubmission:
    submission_id: str
    course_id: str
    task_id: str
    student_sub: str
    storage_key: str
    sha256: str
    size_bytes: int


def _seed_pdf_submission(*, size_bytes: int) -> SeededSubmission:
    """Create a pending PDF submission via direct SQL inserts."""
    _require_db_or_skip()

    teacher = f"teacher-{uuid.uuid4()}"
    student = f"student-{uuid.uuid4()}"
    storage_key = f"submissions/{uuid.uuid4()}/{uuid.uuid4()}/{student}/orig/sample.pdf"
    sha256 = "a" * 64
    submission_id = uuid.uuid4()

    dsn = _service_dsn()
    with psycopg.connect(dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, false)", (teacher,))
            cur.execute(
                "insert into public.courses (title, teacher_id) values (%s, %s) returning id",
                ("PDF Course", teacher),
            )
            course_id = cur.fetchone()[0]
            cur.execute(
                "insert into public.units (title, author_id) values (%s, %s) returning id",
                ("Unit", teacher),
            )
            unit_id = cur.fetchone()[0]
            cur.execute(
                "insert into public.unit_sections (unit_id, title, position) values (%s, %s, %s) returning id",
                (unit_id, "Section", 1),
            )
            section_id = cur.fetchone()[0]
            cur.execute(
                """
                insert into public.unit_tasks (unit_id, section_id, instruction_md, position)
                values (%s, %s, %s, %s) returning id
                """,
                (unit_id, section_id, "Solve the worksheet", 1),
            )
            task_id = cur.fetchone()[0]
            cur.execute(
                "insert into public.course_memberships (course_id, student_id, role) values (%s, %s, 'student')",
                (course_id, student),
            )
            cur.execute("select set_config('app.current_sub', %s, false)", (student,))
            cur.execute(
                """
                insert into public.learning_submissions (
                  id, course_id, task_id, student_sub, kind,
                  storage_key, mime_type, size_bytes, sha256, attempt_nr,
                  analysis_status, analysis_json, text_body, feedback_md, error_code
                ) values (
                  %s::uuid, %s::uuid, %s::uuid, %s, 'file',
                  %s, 'application/pdf', %s, %s, 1,
                  'pending', null, null, null, null
                )
                """,
                (
                    str(submission_id),
                    str(course_id),
                    str(task_id),
                    student,
                    storage_key,
                    int(size_bytes),
                    sha256,
                ),
            )
            conn.commit()

    return SeededSubmission(
        submission_id=str(submission_id),
        course_id=str(course_id),
        task_id=str(task_id),
        student_sub=student,
        storage_key=storage_key,
        sha256=sha256,
        size_bytes=size_bytes,
    )


def _fetch_status(submission_id: str) -> tuple[str, str | None, dict | None]:
    dsn = _service_dsn()
    with psycopg.connect(dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute(
                """
                select analysis_status, error_code, analysis_json
                  from public.learning_submissions
                 where id = %s::uuid
                """,
                (submission_id,),
            )
            row = cur.fetchone()
    assert row is not None, "expected submission row"
    return row[0], row[1], row[2]


class _MemoryStorage:
    """Simple in-memory BinaryWriteStorage stub."""

    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}

    def put_object(self, *, bucket: str, key: str, body: bytes, content_type: str) -> None:
        self.objects[(bucket, key)] = body


def _build_context(seed: SeededSubmission) -> SubmissionContext:
    return SubmissionContext(
        submission_id=seed.submission_id,
        course_id=seed.course_id,
        task_id=seed.task_id,
        student_sub=seed.student_sub,
        storage_key=seed.storage_key,
        mime_type="application/pdf",
        size_bytes=seed.size_bytes,
        sha256=seed.sha256,
    )


def test_pdf_preprocessing_marks_extracted(monkeypatch):
    """Happy path: pages rendered, stored, and submission transitions to extracted."""
    seed = _seed_pdf_submission(size_bytes=2048)
    repo = DBLearningRepo(dsn=_service_dsn())

    pages = []
    for idx in range(2):
        page = types.SimpleNamespace(
            index=idx,
            width=100,
            height=200,
            mode="L",
            png_bytes=f"page-{idx}".encode("utf-8"),
        )
        pages.append(page)

    def _fake_process(_: bytes):
        meta = types.SimpleNamespace(page_count=2, dpi=300, grayscale=True, used_annotations=True)
        return pages, meta

    import sys as _sys

    monkeypatch.setitem(
        _sys.modules,
        "backend.vision.pipeline",
        types.SimpleNamespace(process_pdf_bytes=_fake_process),
    )

    storage = _MemoryStorage()
    bucket = os.getenv("LEARNING_SUBMISSIONS_BUCKET", "learning-submissions")
    usecase = PreprocessPdfSubmissionUseCase(
        repo=repo,
        worker_dsn=_service_dsn(),
        storage=storage,
        bucket=bucket,
    )

    pdf_bytes = b"%PDF-1.4\nHappy Path\n"
    usecase.execute(context=_build_context(seed), pdf_bytes=pdf_bytes)

    status, error_code, analysis_json = _fetch_status(seed.submission_id)
    assert status == "extracted"
    assert error_code is None
    assert isinstance(analysis_json, dict)
    assert "page_keys" in analysis_json
    assert len(analysis_json["page_keys"]) == 2
    assert len(storage.objects) == 2


def test_pdf_preprocessing_marks_failed_for_corrupt_pdf(monkeypatch):
    """Corrupt PDFs should mark the submission failed with input_corrupt."""
    seed = _seed_pdf_submission(size_bytes=4096)
    repo = DBLearningRepo(dsn=_service_dsn())

    def _fail(_: bytes):
        raise PdfRenderError("failed_to_open_pdf")

    import sys as _sys

    monkeypatch.setitem(
        _sys.modules,
        "backend.vision.pipeline",
        types.SimpleNamespace(process_pdf_bytes=_fail),
    )

    storage = _MemoryStorage()
    usecase = PreprocessPdfSubmissionUseCase(
        repo=repo,
        worker_dsn=_service_dsn(),
        storage=storage,
        bucket=os.getenv("LEARNING_SUBMISSIONS_BUCKET", "learning-submissions"),
    )

    usecase.execute(context=_build_context(seed), pdf_bytes=b"%PDF-corrupt")

    status, error_code, _ = _fetch_status(seed.submission_id)
    assert status == "failed"
    assert error_code == "input_corrupt"


def test_pdf_preprocessing_rejects_oversized_submission(monkeypatch):
    """Oversized PDFs should be rejected before invoking the renderer."""
    oversize = 10 * 1024 * 1024  # DB constraint max (10 MiB)
    seed = _seed_pdf_submission(size_bytes=oversize)
    repo = DBLearningRepo(dsn=_service_dsn())

    called = {"n": 0}

    def _should_not_run(_: bytes):
        called["n"] += 1
        return [], types.SimpleNamespace(page_count=0, dpi=300, grayscale=True, used_annotations=True)

    import sys as _sys

    monkeypatch.setitem(
        _sys.modules,
        "backend.vision.pipeline",
        types.SimpleNamespace(process_pdf_bytes=_should_not_run),
    )

    storage = _MemoryStorage()
    usecase = PreprocessPdfSubmissionUseCase(
        repo=repo,
        worker_dsn=_service_dsn(),
        storage=storage,
        bucket=os.getenv("LEARNING_SUBMISSIONS_BUCKET", "learning-submissions"),
        size_limit_bytes=oversize - 1,  # tighten limit to force declared size > limit
    )

    usecase.execute(context=_build_context(seed), pdf_bytes=b"%PDF-oversize")

    status, error_code, _ = _fetch_status(seed.submission_id)
    assert status == "failed"
    assert error_code == "input_too_large"
    assert called["n"] == 0, "renderer should not be invoked for oversize submissions"
