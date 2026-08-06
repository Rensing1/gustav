from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]


def _spec() -> dict:
    return yaml.safe_load((ROOT / "api" / "openapi.yml").read_text(encoding="utf-8"))


def test_course_lifecycle_and_personal_archive_paths_are_contract_first() -> None:
    spec = _spec()
    paths = spec["paths"]

    assert "/api/teaching/courses/{course_id}/archive" in paths
    assert "/api/teaching/courses/{course_id}/restore" in paths
    assert "/api/teaching/courses/archive-batch" in paths
    assert "/api/teaching/courses/{course_id}/deletion-impact" in paths
    assert "/api/teaching/courses/{course_id}/deletion-jobs" in paths
    assert "/api/learning/courses/{course_id}/portfolio" in paths
    assert "/api/learning/courses/{course_id}/exports" in paths
    assert "/api/learning/exports/{export_id}" in paths
    assert "/api/learning/exports/{export_id}/download" in paths


def test_course_contract_exposes_structured_lifecycle_metadata() -> None:
    schemas = _spec()["components"]["schemas"]
    course = schemas["Course"]
    course_create = schemas["CourseCreate"]
    list_item = schemas["TeacherCourseListItem"]

    assert {"status", "metadata_complete"} <= set(course["required"])
    assert {"title", "subject", "grade_level", "school_year_start"} <= set(course_create["required"])
    assert course["properties"]["status"]["enum"] == ["active", "archived", "deleting"]
    assert list_item["properties"]["school_year_start"]["type"] == "integer"


def test_unsafe_direct_course_delete_is_not_part_of_the_contract() -> None:
    assert "delete" not in _spec()["paths"]["/api/teaching/courses/{course_id}"]
