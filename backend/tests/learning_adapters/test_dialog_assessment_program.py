"""Dialog assessment must never turn malformed model output into a grade."""

from types import SimpleNamespace

import pytest

from backend.learning.adapters.dspy import dialog_assessment_program as program
from backend.learning.adapters.dspy.types import LeanCriterionResult


def _predict(monkeypatch, criteria_results, feedback_md="Ihre Begründung ist nachvollziehbar."):
    calls = []

    def predict(signature):
        assert signature is program.DialogAssessmentSignature

        def run(**kwargs):
            calls.append(kwargs)
            return SimpleNamespace(criteria_results=criteria_results, feedback_md=feedback_md)

        return run

    monkeypatch.setattr(program.dspy, "Predict", predict)
    return calls


def _analyze(criteria=("Begründen", "Einordnen")):
    return program.analyze_dialog(
        student_performance={"messages": [{"text": "Meine Begründung"}], "closing_answer_md": None},
        conversation_context={"assistant_messages": ["Eine Rückfrage"]},
        criteria=criteria,
        instruction_md="Begründen und ordnen Sie ein.",
    )


def test_dialog_schema_requires_score_and_explanation():
    schema = program.DialogAssessmentSignature.model_json_schema()
    item = schema["properties"]["criteria_results"]["items"]
    if "$ref" in item:
        item = schema["$defs"][item["$ref"].rsplit("/", 1)[1]]
    assert set(item["required"]) == {"score", "explanation_md"}
    assert item["properties"]["score"]["type"] == "integer"


@pytest.mark.parametrize("typed", [False, True])
def test_valid_dialog_preserves_scores_evidence_and_separate_inputs(monkeypatch, typed):
    items = [
        {"score": 8, "explanation_md": "Eine tragfähige Begründung."},
        {"score": 10, "explanation_md": "Eine zutreffende Einordnung."},
    ]
    calls = _predict(monkeypatch, [LeanCriterionResult(**item) for item in items] if typed else items)

    result = _analyze()

    assert result.analysis_json == {
        "schema": "criteria.v2",
        "score": 5,
        "criteria_results": [
            {"criterion": name, "max_score": 10, **item}
            for name, item in zip(("Begründen", "Einordnen"), items)
        ],
    }
    assert result.feedback_md == "Ihre Begründung ist nachvollziehbar."
    assert calls[0]["student_performance"]["messages"] == [{"text": "Meine Begründung"}]
    assert calls[0]["conversation_context"] == {"assistant_messages": ["Eine Rückfrage"]}


@pytest.mark.parametrize("invalid", [
    {},
    {"rating": "very good", "reason": "Correct reasoning"},
    {"explanation_md": "Die Begründung ist gut."},
    {"score": 8},
    {"score": None, "explanation_md": "Begründung"},
    {"score": True, "explanation_md": "Begründung"},
    {"score": "8", "explanation_md": "Begründung"},
    {"score": 8.0, "explanation_md": "Begründung"},
    {"score": "good", "explanation_md": "Begründung"},
    {"score": 8, "explanation_md": None},
    {"score": 8, "explanation_md": "   "},
    {"score": -1, "explanation_md": "Begründung"},
    {"score": 11, "explanation_md": "Begründung"},
    "very good",
])
def test_invalid_item_cannot_become_completed_zero_grade(monkeypatch, invalid):
    _predict(monkeypatch, [invalid, {"score": 8, "explanation_md": "Begründung"}])
    with pytest.raises(RuntimeError, match="^invalid_analysis_json$"):
        _analyze()


@pytest.mark.parametrize("count", [0, 1, 3])
def test_wrong_number_of_results_is_rejected(monkeypatch, count):
    _predict(monkeypatch, [{"score": 8, "explanation_md": "Begründung"}] * count)
    with pytest.raises(RuntimeError, match="^invalid_analysis_json$"):
        _analyze()


def test_explicit_zero_with_evidence_is_a_valid_grade(monkeypatch):
    _predict(monkeypatch, [{"score": 0, "explanation_md": "Die Antwort enthält keine Begründung."}])
    result = _analyze(criteria=["Begründen"])
    assert result.analysis_json["criteria_results"][0]["score"] == 0
    assert result.analysis_json["score"] == 0


def test_no_criteria_keeps_formative_feedback_without_grade(monkeypatch):
    _predict(monkeypatch, [])
    result = _analyze(criteria=[])
    assert result.analysis_json == {}
    assert result.feedback_md


def test_empty_feedback_is_rejected(monkeypatch):
    _predict(monkeypatch, [], feedback_md=" ")
    with pytest.raises(RuntimeError, match="^empty_feedback_md$"):
        _analyze(criteria=[])


@pytest.mark.parametrize("teacher_context", [None, "Fachwissen und zulässige Varianten; Rückmeldung knapp halten."])
@pytest.mark.parametrize("criteria", [[], ["Begründen"]])
def test_dialog_forwards_internal_context_separately(monkeypatch, teacher_context, criteria):
    calls = _predict(monkeypatch, [
        {"score": 10, "explanation_md": "Sie begründen Ihre Position schlüssig."}
        for _ in criteria
    ])
    result = program.analyze_dialog(
        student_performance={"messages": [{"text": "Meine Begründung"}]},
        conversation_context={"assistant_messages": ["Eine Rückfrage"]},
        criteria=criteria,
        instruction_md="Begründen Sie.",
        teacher_context_md=teacher_context,
    )
    assert calls[0]["teacher_context_md"] == teacher_context
    assert "teacher_context_md" not in calls[0]["student_performance"]
    assert "teacher_context_md" not in calls[0]["conversation_context"]
    assert "teacher_context_md" in program.DialogAssessmentSignature.input_fields
    assert "teacher_context_md" not in result.analysis_json
    if not criteria:
        assert result.analysis_json == {}


def test_dialog_prompt_preserves_performance_boundaries():
    prompt = program.DialogAssessmentSignature.instructions
    for required in (
        "Übernommene Satzanfänge sind Hilfen und kein eigenständiger Leistungsbeleg",
        "niemals als Schülerleistung", "Abschlussantwort", "0 Punkte",
        "Unsicherheit allein rechtfertigt weder einen Abzug",
        "Feste Überschriften oder Satzanzahlen sind nicht erforderlich",
        "ohne diese Leistung automatisch zu übernehmen",
        "Bei leerer Kriterienliste", "Sie-Form",
    ):
        assert required in prompt
