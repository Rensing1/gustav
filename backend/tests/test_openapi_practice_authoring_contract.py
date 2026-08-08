"""Contract-first tests for practice-module authoring."""

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]


def _schemas() -> dict:
    spec = yaml.safe_load((ROOT / "api" / "openapi.yml").read_text(encoding="utf-8"))
    return spec["components"]["schemas"]


def test_teaching_module_contract_exposes_immutable_module_kind() -> None:
    schemas = _schemas()
    module = schemas["TeachingUnitModule"]
    create = schemas["TeachingUnitModuleCreate"]
    update = schemas["TeachingUnitModuleUpdate"]

    assert "module_kind" in module["required"]
    assert module["properties"]["module_kind"]["enum"] == ["learning", "practice"]
    assert create["properties"]["module_kind"] == {
        "type": "string",
        "enum": ["learning", "practice"],
        "default": "learning",
    }
    assert "module_kind" not in update["properties"]


def test_teacher_task_contract_exposes_model_solution_without_learner_leak() -> None:
    schemas = _schemas()
    for name in ("Task", "TaskCreate", "TaskUpdate", "TeacherUnitNodeEditorTask"):
        prop = schemas[name]["properties"]["model_solution_md"]
        assert prop["type"] == "string"
        assert prop["nullable"] is True

    learner = schemas["LearningTask"]["properties"]
    assert "model_solution_md" not in learner
    assert "teacher_context_md" not in learner


def test_teacher_node_editor_exposes_practice_context() -> None:
    schemas = _schemas()
    node = schemas["TeacherUnitNodeEditorNode"]["properties"]
    settings = schemas["TeacherUnitNodeEditorSettings"]["properties"]

    assert node["module_kind"]["enum"] == ["learning", "practice"]
    assert settings["module_kind"]["enum"] == ["learning", "practice"]
