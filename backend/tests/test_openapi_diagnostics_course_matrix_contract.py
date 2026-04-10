from __future__ import annotations

from pathlib import Path

import yaml


def test_openapi_documents_diagnostics_course_matrix_view() -> None:
    spec = yaml.safe_load(Path("api/openapi.yml").read_text(encoding="utf-8"))

    assert "/api/diagnostics/views/courses/{course_id}/matrix" in spec["paths"]

    schema = spec["components"]["schemas"]["DiagnosticsCourseMatrixView"]
    assert schema["required"] == ["user", "course", "units", "rows"]
