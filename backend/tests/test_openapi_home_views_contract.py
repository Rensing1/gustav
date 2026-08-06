from __future__ import annotations

from pathlib import Path

import yaml


def test_openapi_documents_home_view_models() -> None:
    spec = yaml.safe_load(Path("api/openapi.yml").read_text(encoding="utf-8"))

    assert "/api/learning/views/learner-home" in spec["paths"]
    assert "/api/learning/views/concern-box" in spec["paths"]
    assert "/api/learning/concern-box/entries" in spec["paths"]
    assert "/api/teaching/views/teacher-home" in spec["paths"]
    assert "/api/teaching/views/concern-box" in spec["paths"]
    assert "/api/teaching/concern-box/entries/{entry_id}/archive" in spec["paths"]
    assert "/api/teaching/concern-box/entries/{entry_id}/restore" in spec["paths"]
    assert "/api/teaching/views/courses" in spec["paths"]

    learner_schema = spec["components"]["schemas"]["LearnerHome"]
    assert learner_schema["required"] == ["user", "current_courses", "past_courses"]

    learner_concern_schema = spec["components"]["schemas"]["LearnerConcernBoxView"]
    assert learner_concern_schema["required"] == ["user", "courses"]

    teacher_schema = spec["components"]["schemas"]["TeacherHome"]
    assert teacher_schema["required"] == [
        "user",
        "courses",
        "recent_units",
        "units_href",
        "create_unit_href",
    ]
    assert teacher_schema["properties"]["recent_units"]["maxItems"] == 3

    teacher_concern_schema = spec["components"]["schemas"]["TeacherConcernBoxView"]
    assert teacher_concern_schema["required"] == ["user", "scopes", "active_scope", "entries"]

    teacher_courses_schema = spec["components"]["schemas"]["TeacherCourseListView"]
    assert teacher_courses_schema["required"] == [
        "user",
        "status",
        "query",
        "school_year_start",
        "subject",
        "courses",
    ]

    teacher_course_item = spec["components"]["schemas"]["TeacherCourseListItem"]
    assert teacher_course_item["required"] == [
        "id",
        "title",
        "href",
        "members_count",
        "units_count",
        "status",
        "metadata_complete",
    ]
