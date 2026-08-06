"""Unit tests for safe, offline-readable learner exports."""

from __future__ import annotations

import io
import json
import zipfile

import pytest

from backend.learning.workers.course_lifecycle_jobs import ExportTooLarge, build_export_zip


def _snapshot() -> dict:
    return {
        "course": {"id": "course-1", "title": "Politik 10", "school_year_start": 2025},
        "cutoff_at": "2026-07-01T12:00:00+00:00",
        "submissions": [
            {
                "id": "submission-1", "kind": "file", "created_at": "2026-06-01T10:00:00+00:00",
                "text_body": None, "feedback_md": "<script>alert(1)</script> Gute Arbeit",
                "analysis_json": {"criteria": ["begründet"]}, "storage_key": "private/student/../lösung.pdf",
                "mime_type": "application/pdf", "task_snapshot": {"instruction_md": "Begründe <b>sachlich</b>."},
            }
        ],
    }


def test_export_zip_is_offline_readable_and_escapes_content() -> None:
    archive = build_export_zip(_snapshot(), load_file=lambda _key: b"PDF", max_bytes=100_000)
    with zipfile.ZipFile(io.BytesIO(archive)) as result:
        assert {"index.html", "manifest.json"}.issubset(result.namelist())
        assert all(".." not in name for name in result.namelist())
        html = result.read("index.html").decode("utf-8")
        assert "&lt;script&gt;" in html
        assert "<script" not in html
        assert "http://" not in html and "https://" not in html
        manifest = json.loads(result.read("manifest.json"))
        assert manifest["course"]["title"] == "Politik 10"
        assert len(manifest["submissions"]) == 1


def test_export_fails_atomically_when_limit_is_exceeded() -> None:
    with pytest.raises(ExportTooLarge):
        build_export_zip(_snapshot(), load_file=lambda _key: b"x" * 20_000, max_bytes=1_000)
