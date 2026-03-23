from __future__ import annotations

from pathlib import Path

import yaml


def test_openapi_documents_home_view_models() -> None:
    spec = yaml.safe_load(Path("api/openapi.yml").read_text(encoding="utf-8"))

    assert "/api/learning/views/learner-home" in spec["paths"]
    assert "/api/teaching/views/teacher-home" in spec["paths"]

    learner_schema = spec["components"]["schemas"]["LearnerHome"]
    assert learner_schema["required"] == ["user", "courses"]

    teacher_schema = spec["components"]["schemas"]["TeacherHome"]
    assert teacher_schema["required"] == ["user", "entries"]

