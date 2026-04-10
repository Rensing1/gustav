from __future__ import annotations

from pathlib import Path

import yaml


def test_openapi_documents_live_view_models() -> None:
    spec = yaml.safe_load(Path("api/openapi.yml").read_text(encoding="utf-8"))

    assert "/api/live/views/courses/{course_id}/units/{unit_id}/matrix" in spec["paths"]
    assert "/api/live/views/courses/{course_id}/units/{unit_id}/detail-sheet" in spec["paths"]

    matrix_schema = spec["components"]["schemas"]["LiveUnitMatrixView"]
    assert matrix_schema["required"] == ["user", "course", "unit", "tasks", "rows"]

    detail_schema = spec["components"]["schemas"]["LiveDetailSheetView"]
    assert detail_schema["required"] == ["user", "course", "unit", "student", "task", "submission"]
