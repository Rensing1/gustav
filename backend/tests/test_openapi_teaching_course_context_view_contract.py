from __future__ import annotations

from pathlib import Path

import yaml


def test_openapi_documents_teacher_course_context_view() -> None:
    spec = yaml.safe_load(Path("api/openapi.yml").read_text(encoding="utf-8"))

    assert "/api/teaching/views/courses/{course_id}/context" in spec["paths"]

    schema = spec["components"]["schemas"]["TeacherCourseContextView"]
    assert schema["required"] == ["user", "course", "units", "members"]
