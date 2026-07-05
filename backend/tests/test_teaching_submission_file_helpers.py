"""Contracts for Teaching submission file helper ownership."""

from __future__ import annotations

import importlib
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEACHING_SOURCE = PROJECT_ROOT / "backend" / "web" / "routes" / "teaching.py"
HELPERS_SOURCE = PROJECT_ROOT / "backend" / "web" / "routes" / "teaching_submission_files.py"


def test_submission_file_helpers_live_outside_teaching_hotspot() -> None:
    """Submission download helpers should not keep growing the Teaching route hotspot."""

    teaching = importlib.import_module("backend.web.routes.teaching")
    helpers = importlib.import_module("backend.web.routes.teaching_submission_files")
    teaching_source = TEACHING_SOURCE.read_text(encoding="utf-8")
    helpers_source = HELPERS_SOURCE.read_text(encoding="utf-8")

    assert "def _safe_download_filename(" not in teaching_source
    assert "def _teaching_submission_file_href(" not in teaching_source
    assert "def safe_download_filename(" in helpers_source
    assert "def teaching_submission_file_href(" in helpers_source
    assert teaching._safe_download_filename is helpers.safe_download_filename
    assert teaching._download_bytes_with_limit is helpers.download_bytes_with_limit
    assert teaching._teaching_submission_file_href is helpers.teaching_submission_file_href


def test_submission_file_helpers_keep_existing_sanitizing_and_href_rules() -> None:
    helpers = importlib.import_module("backend.web.routes.teaching_submission_files")

    assert helpers.safe_download_filename('bad"name\r\n.pdf', "fallback.bin") == "badname.pdf"
    assert helpers.safe_download_filename("  ", "fallback.bin") == "fallback.bin"
    assert (
        helpers.teaching_submission_file_href(
            course_id="course-1",
            unit_id="unit-1",
            task_id="task-1",
            student_sub="student-1",
            disposition="inline",
        )
        == "/api/teaching/courses/course-1/units/unit-1/tasks/task-1/students/student-1/submissions/latest/file"
        "?disposition=inline"
    )
