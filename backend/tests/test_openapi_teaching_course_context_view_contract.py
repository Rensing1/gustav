from __future__ import annotations

from pathlib import Path

import yaml


def test_openapi_documents_teacher_course_context_view() -> None:
    spec = yaml.safe_load(Path("api/openapi.yml").read_text(encoding="utf-8"))

    assert "/api/teaching/views/courses/{course_id}/context" in spec["paths"]

    schema = spec["components"]["schemas"]["TeacherCourseContextView"]
    assert schema["required"] == ["user", "course", "units", "members"]

    course = spec["components"]["schemas"]["TeacherCourseContextCourse"]
    assert course["required"] == [
        "id",
        "title",
        "href",
        "members_href",
        "diagnostics_href",
        "members_count",
        "units_count",
    ]


def test_openapi_documents_teacher_course_ai_usage_view() -> None:
    spec = yaml.safe_load(Path("api/openapi.yml").read_text(encoding="utf-8"))

    path = "/api/teaching/views/courses/{course_id}/ai-usage"
    assert path in spec["paths"]
    operation = spec["paths"][path]["get"]
    assert operation["security"] == [{"bearerAuth": []}]

    param_names = {item["name"] for item in operation["parameters"]}
    assert {"course_id", "from", "to", "unit_id", "task_id", "student_sub", "limit", "offset"} <= param_names

    response = operation["responses"]["200"]
    assert "Cache-Control" in response["headers"]
    assert response["content"]["application/json"]["schema"]["$ref"] == "#/components/schemas/TeacherCourseAiUsageView"

    view = spec["components"]["schemas"]["TeacherCourseAiUsageView"]
    assert view["required"] == ["user", "course", "filters", "totals", "learners", "pagination", "generated_at"]

    totals = spec["components"]["schemas"]["AiUsageTotals"]
    assert totals["required"] == ["input_tokens", "output_tokens", "total_tokens", "known_events", "unknown_events", "breakdown"]
