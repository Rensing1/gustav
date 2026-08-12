"""OpenAPI contract tests for learner practice stacks and sessions."""

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]


def _spec() -> dict:
    return yaml.safe_load((ROOT / "api" / "openapi.yml").read_text(encoding="utf-8"))


def test_practice_stack_and_session_paths_are_contracted() -> None:
    paths = _spec()["paths"]
    expected = {
        "/api/learning/practice/stacks": {"get"},
        "/api/learning/practice/sessions/active": {"get"},
        "/api/learning/practice/sessions": {"post"},
        "/api/learning/practice/sessions/{session_id}": {"get"},
        "/api/learning/practice/sessions/{session_id}/continue": {"post"},
        "/api/learning/practice/sessions/{session_id}/items/{item_id}/attempts": {"post"},
        "/api/learning/practice/sessions/{session_id}/items/{item_id}/h5p-context": {"post"},
        "/api/learning/practice/attempts/{attempt_id}": {"get"},
        "/api/learning/practice/sessions/{session_id}/items/{item_id}/solution": {"post"},
        "/api/learning/practice/sessions/{session_id}/items/{item_id}/skip": {"post"},
        "/api/learning/practice/sessions/{session_id}/end": {"post"},
    }
    for path, methods in expected.items():
        assert path in paths
        assert methods <= set(paths[path])

    assert "204" in paths["/api/learning/practice/sessions/active"]["get"]["responses"]
    assert "201" in paths["/api/learning/practice/sessions"]["post"]["responses"]
    assert "202" in paths["/api/learning/practice/sessions/{session_id}/items/{item_id}/attempts"]["post"]["responses"]


def test_practice_responses_do_not_contract_hidden_teacher_content() -> None:
    schemas = _spec()["components"]["schemas"]
    item = schemas["LearningPracticeSessionItem"]["properties"]
    stack = schemas["LearningPracticeStack"]["properties"]
    for hidden in ("teacher_context_md", "model_solution_md"):
        assert hidden not in item
        assert hidden not in stack
    assert {"module_kind", "due_tasks_count"} <= set(
        schemas["LearningUnitGraphModule"]["required"]
    )


def test_practice_session_create_contract_has_mode_selection_and_limits() -> None:
    schemas = _spec()["components"]["schemas"]
    create = schemas["LearningPracticeSessionCreate"]
    assert set(create["required"]) == {"mode", "stacks"}
    assert create["properties"]["mode"]["enum"] == ["due", "exam"]
    assert create["properties"]["stacks"]["minItems"] == 1
    assert create["properties"]["stacks"]["maxItems"] == 50
    assert "practice_enabled" not in schemas["SessionBootstrap"]["properties"]
    responses = _spec()["paths"]["/api/learning/practice/sessions"]["post"]["responses"]
    assert "503" not in responses


def test_current_practice_item_identifies_its_latest_attempt() -> None:
    item = _spec()["components"]["schemas"]["LearningPracticeSessionItem"]
    assert "latest_attempt_id" in item["required"]
    assert item["properties"]["latest_attempt_id"] == {
        "type": "string",
        "format": "uuid",
        "nullable": True,
    }


def test_practice_attempt_contract_separates_native_and_token_bound_h5p_inputs() -> None:
    variants = _spec()["components"]["schemas"]["LearningPracticeAttemptCreate"]["oneOf"]
    assert {"answer_text"} == set(variants[0]["required"])
    assert {"score_raw", "score_max", "practice_completion_token"} == set(variants[1]["required"])
