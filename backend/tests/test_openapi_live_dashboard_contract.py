from __future__ import annotations

from pathlib import Path

import yaml


def test_openapi_documents_live_dashboard_models() -> None:
    spec = yaml.safe_load(Path("api/openapi.yml").read_text(encoding="utf-8"))

    dashboard_path = spec["paths"]["/api/live/views/courses/{course_id}/units/{unit_id}/dashboard"]["get"]
    assert "/api/live/views/courses/{course_id}/units" in spec["paths"]
    assert [parameter["name"] for parameter in dashboard_path["parameters"]] == ["course_id", "unit_id", "student_sub", "task_id"]

    dashboard_schema = spec["components"]["schemas"]["LiveUnitDashboardView"]
    assert dashboard_schema["required"] == ["user", "course", "unit", "summary", "rows", "selected_student_panel"]

    row_schema = spec["components"]["schemas"]["LiveUnitDashboardRow"]
    assert row_schema["required"] == ["student", "progress_percent", "average_score", "latest_submission", "href"]

    latest_schema = spec["components"]["schemas"]["LiveDashboardLatestSubmission"]
    assert latest_schema["required"] == ["task_id", "task_position", "task_label", "created_at", "average_score"]

    panel_schema = spec["components"]["schemas"]["LiveStudentPanelView"]
    assert panel_schema["required"] == ["student", "tasks", "selected_task_id", "selected_task_detail"]

    units_schema = spec["components"]["schemas"]["LiveCourseUnitsView"]
    assert units_schema["required"] == ["user", "course", "units"]
