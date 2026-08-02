"""Contract-first tests for AI dialog tasks.

Why:
    Dialog tasks add author-only configuration and learner-owned session APIs.
    These tests lock the public boundary before persistence or route code is
    introduced, following GUSTAV's contract-first workflow.
"""

from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]


def _spec() -> dict:
    return yaml.safe_load((ROOT / "api" / "openapi.yml").read_text(encoding="utf-8"))


def test_dialog_task_config_separates_author_and_learner_fields() -> None:
    schemas = _spec()["components"]["schemas"]

    author = schemas["DialogTaskConfig"]
    assert author["additionalProperties"] is False
    assert set(author["required"]) == {
        "partner_name",
        "partner_description_md",
        "role_md",
        "learning_goal_md",
        "opening_message_md",
        "response_mode",
        "max_rounds",
    }
    assert author["properties"]["response_mode"]["enum"] == ["free_text", "hybrid"]
    assert author["properties"]["max_rounds"]["default"] == 8
    assert author["properties"]["max_rounds"]["maximum"] == 12

    learner = schemas["LearningDialogTaskConfig"]
    learner_properties = learner["properties"]
    assert "partner_name" in learner_properties
    assert "partner_description_md" in learner_properties
    assert "opening_message_md" in learner_properties
    assert "closing_prompt_md" in learner_properties
    assert "role_md" not in learner_properties
    assert "learning_goal_md" not in learner_properties
    assert "teacher_context_md" not in learner_properties


def test_dialog_kind_and_nested_config_are_present_on_task_contracts() -> None:
    schemas = _spec()["components"]["schemas"]

    for schema_name in ("Task", "TeacherUnitNodeEditorTask"):
        properties = schemas[schema_name]["properties"]
        assert "dialog" in properties
        assert "dialog" in properties["kind"]["enum"]

    for schema_name in ("TaskCreate", "TaskUpdate"):
        dialog = schemas[schema_name]["properties"]["dialog"]
        assert dialog["$ref"] == "#/components/schemas/DialogTaskConfig"

    learning_properties = schemas["LearningTask"]["properties"]
    assert "dialog" in learning_properties["kind"]["enum"]
    assert learning_properties["dialog"]["$ref"] == "#/components/schemas/LearningDialogTaskConfig"
    assert learning_properties["active_dialog_session_id"]["nullable"] is True


def test_learning_dialog_session_schemas_keep_internal_context_private() -> None:
    schemas = _spec()["components"]["schemas"]
    session = schemas["LearningDialogSession"]
    properties = session["properties"]

    assert set(session["required"]) >= {
        "id",
        "course_id",
        "task_id",
        "status",
        "round_count",
        "dialog",
        "turns",
    }
    assert properties["status"]["enum"] == ["active", "completed", "abandoned"]
    assert properties["dialog"]["$ref"] == "#/components/schemas/LearningDialogTaskConfig"
    assert "config_snapshot" not in properties
    assert "role_md" not in properties
    assert "learning_goal_md" not in properties
    assert "teacher_context_md" not in properties

    turn = schemas["LearningDialogTurn"]
    assert turn["properties"]["status"]["enum"] == ["generating", "completed", "failed"]
    assert turn["properties"]["student_message_md"]["maxLength"] == 2000
    assert turn["properties"]["assistant_reply_md"]["maxLength"] == 2000
    assert turn["properties"]["sentence_starters"]["maxItems"] == 3


def test_learning_dialog_session_paths_are_documented() -> None:
    paths = _spec()["paths"]
    base = "/api/learning/courses/{course_id}/tasks/{task_id}/dialog-sessions"
    detail = f"{base}/{{session_id}}"

    expected = {
        base: {"post"},
        detail: {"get"},
        f"{detail}/turns": {"post"},
        f"{detail}/turns/{{turn_id}}/retry": {"post"},
        f"{detail}/complete": {"post"},
        f"{detail}/abandon": {"post"},
    }
    for path, verbs in expected.items():
        assert path in paths
        assert verbs <= set(paths[path])
        for verb in verbs:
            operation = paths[path][verb]
            assert operation["x-permissions"]["requiredRole"] == "student"
            assert {"cookieAuth": []} in operation["security"]

    turn_schema = paths[f"{detail}/turns"]["post"]["requestBody"]["content"]["application/json"]["schema"]
    assert turn_schema["$ref"] == "#/components/schemas/DialogTurnCreate"
    complete_schema = paths[f"{detail}/complete"]["post"]["requestBody"]["content"]["application/json"]["schema"]
    assert complete_schema["$ref"] == "#/components/schemas/DialogSessionComplete"


def test_teacher_dialog_preview_and_transcript_paths_are_documented() -> None:
    paths = _spec()["paths"]
    preview = "/api/teaching/units/{unit_id}/tasks/{task_id}/dialog-preview"
    transcript = (
        "/api/teaching/courses/{course_id}/units/{unit_id}/tasks/{task_id}"
        "/students/{student_sub}/submissions/{submission_id}/dialog"
    )

    assert paths[preview]["post"]["x-permissions"] == {
        "requiredRole": "teacher",
        "authorOnly": True,
    }
    assert paths[transcript]["get"]["x-permissions"] == {
        "requiredRole": "teacher",
        "ownerOnly": True,
    }


def test_dialog_submission_kind_and_reference_are_public() -> None:
    schemas = _spec()["components"]["schemas"]
    submission = schemas["LearningSubmission"]["allOf"][1]["properties"]
    assert "dialog" in submission["kind"]["enum"]
    assert submission["dialog_session_id"]["format"] == "uuid"
    assert submission["dialog_session_id"]["nullable"] is True

    latest = schemas["TeachingLatestSubmission"]["properties"]
    assert "dialog" in latest["kind"]["enum"]
    assert latest["dialog_session_id"]["nullable"] is True
