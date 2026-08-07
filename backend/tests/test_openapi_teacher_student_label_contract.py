"""OpenAPI documents one learner-label contract for every teacher surface."""

from __future__ import annotations

from pathlib import Path

import yaml


SPEC_PATH = Path(__file__).resolve().parents[2] / "api" / "openapi.yml"


def test_openapi_reuses_teacher_student_label_across_teacher_read_models() -> None:
    spec = yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))
    schemas = spec["components"]["schemas"]
    label_ref = {"$ref": "#/components/schemas/TeacherStudentLabel"}

    assert "firstName lastName" in schemas["TeacherStudentLabel"]["description"]
    assert schemas["TeacherCourseContextMember"]["properties"]["name"] == label_ref
    assert schemas["CourseMember"]["properties"]["name"] == label_ref
    assert schemas["DiagnosticsCourseMatrixStudent"]["properties"]["name"] == label_ref
    assert schemas["DiagnosticsLearnerProfileLearner"]["properties"]["name"] == label_ref
    assert schemas["LiveMatrixStudent"]["properties"]["name"] == label_ref
    assert schemas["LiveDetailStudent"]["properties"]["name"] == label_ref

    concern_name = schemas["TeacherConcernBoxEntry"]["properties"]["student_name"]
    assert concern_name["allOf"] == [label_ref]
    assert concern_name["nullable"] is True


def test_general_profile_display_name_keeps_its_separate_contract() -> None:
    spec = yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))
    name = spec["components"]["schemas"]["Me"]["properties"]["name"]

    assert name["type"] == "string"
    assert "display_name" in name["description"]
    assert "$ref" not in name
