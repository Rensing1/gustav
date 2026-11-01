import ast
import importlib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


def _signature_docstrings() -> dict[str, str]:
    source = (REPO_ROOT / "backend/learning/adapters/dspy/signatures.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    result: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        docstring = ast.get_docstring(node) or ""
        if len(docstring) > len(result.get(node.name, "")):
            result[node.name] = docstring
    return result


@pytest.mark.parametrize(("signature", "fixture"), [
    ("FeedbackAnalysisSignature", "feedback-analysis-approved.txt"),
    ("FeedbackSynthesisSignature", "feedback-synthesis-approved.txt"),
])
def test_main_prompts_match_approved_text_verbatim(signature, fixture) -> None:
    """Freeze the teacher-approved wording independently of the living reference."""
    approved = (REPO_ROOT / "backend/tests/fixtures/prompts" / fixture).read_text(encoding="utf-8").strip()
    assert _signature_docstrings()[signature] == approved


def test_feedback_signatures_keep_shared_principles_without_rigid_defaults() -> None:
    docs = _signature_docstrings()
    for name, doc in docs.items():
        if name == "VisionOcrSignature":
            continue
        assert "Sie-Form" in doc
        assert "Lehrkraft" in doc
        assert "GUSTAV-Standardstruktur" not in doc
        assert "jeweils zwei kurze Sätze" not in doc
        assert "lieber `score = 0`" not in doc
    for name in ("FeedbackAnalysisSignature", "VisualFeedbackAnalysisSignature"):
        assert "Unsicherheit allein rechtfertigt weder einen Abzug" in docs[name]
        assert "für dieses Kriterium 0 Punkte" in docs[name]
        assert "Technische" in docs[name]
    for name in ("FeedbackSynthesisSignature", "VisualFeedbackSynthesisSignature",
                 "FeedbackNoCriteriaSignature", "VisualFeedbackNoCriteriaSignature"):
        assert "Feste Überschriften oder Satzanzahlen sind nicht erforderlich." in docs[name]
        assert "ohne diese Leistung automatisch zu übernehmen" in docs[name]
        assert "begründeten Bestätigung" in docs[name]
    for name in ("FeedbackNoCriteriaSignature", "VisualFeedbackNoCriteriaSignature"):
        assert "keine Punktebewertung" in docs[name]
        assert "Auswertungsbefunde" not in docs[name]


@pytest.mark.parametrize("visual", [False, True])
def test_repair_uses_exact_approved_suffix_and_preserves_context(visual) -> None:
    from backend.learning.adapters.dspy.programs import _run_analysis_repair

    calls = []
    sentinel = object()

    def runner(**kwargs):
        calls.append(kwargs)
        return sentinel

    media = {"image_data_uri": "data:image/png;base64,AA=="} if visual else {"text_md": "Antwort"}
    result = _run_analysis_repair(
        runner=runner, repair_reason="invalid_analysis_json", criteria=["A", "B"],
        teacher_instructions_md="Aufgabe", teacher_context_md="Interner Kontext", **media,
    )
    approved = (REPO_ROOT / "backend/tests/fixtures/prompts/feedback-repair-approved.txt").read_text(encoding="utf-8").strip()
    assert result is sentinel
    assert calls == [{
        "criteria": ["A", "B"], "teacher_context_md": "Interner Kontext", **media,
        "teacher_instructions_md": "Aufgabe\n\n" + approved.format(repair_reason="invalid_analysis_json"),
    }]


def test_backend_feedback_fixtures_do_not_use_deprecated_du_headings() -> None:
    """Active tests should demonstrate the current formal-address feedback contract."""
    deprecated_headings = (
        "**Das ist " + "dir gut gelungen:**",
        "**Das kannst " + "du besser:**",
    )
    matches: list[str] = []
    for path in (REPO_ROOT / "backend/tests").rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        if any(heading in source for heading in deprecated_headings):
            matches.append(str(path.relative_to(REPO_ROOT)))

    assert matches == []


@pytest.mark.anyio
def test_dspy_feedback_program_normalizes_structured_analysis(monkeypatch: pytest.MonkeyPatch) -> None:
    """Structured DSPy analysis is normalized to criteria.v2 (clamping + ordering)."""

    class _FakeDSPy:
        __version__ = "0.1-test"

    monkeypatch.setitem(__import__("sys").modules, "dspy", _FakeDSPy())

    mod = importlib.import_module("backend.learning.adapters.dspy.feedback_program")
    programs = importlib.import_module("backend.learning.adapters.dspy.programs")

    def fake_run_structured_analysis(*, text_md: str, criteria: list[str], **_kwargs):
        return {
            "schema": "criteria.v2",
            "score": "4.0",
            "criteria_results": [
                {"criterion": "Inhalt", "max_score": 10, "score": 11, "explanation_md": "gut"},
                {"criterion": "Darstellung", "max_score": 5, "score": -1, "explanation_md": "ok"},
            ],
        }

    def fake_run_structured_feedback(*, text_md: str, criteria: list[str], analysis_json, **_kwargs):
        assert criteria == ["Inhalt", "Darstellung"]
        return (
            "**Das ist Ihnen gut gelungen:** Sie haben zentrale Punkte verständlich erklärt.\n\n"
            "**Das können Sie noch besser:** Achten Sie beim nächsten Mal stärker auf eine klare Gliederung."
        )

    monkeypatch.setattr(programs, "run_structured_analysis", fake_run_structured_analysis, raising=False)
    monkeypatch.setattr(programs, "run_structured_feedback", fake_run_structured_feedback, raising=False)

    result = mod.analyze_feedback(text_md="# Lösung\nText", criteria=["Inhalt", "Darstellung"])

    assert result.analysis_json["schema"] == "criteria.v2"
    assert 0 <= int(result.analysis_json["score"]) <= 5
    items = result.analysis_json["criteria_results"]
    assert isinstance(items, list) and len(items) == 2
    inhalt = next(i for i in items if i["criterion"] == "Inhalt")
    darst = next(i for i in items if i["criterion"] == "Darstellung")
    assert 0 <= inhalt["score"] <= inhalt["max_score"]
    assert 0 <= darst["score"] <= darst["max_score"]
    assert "**Das ist Ihnen gut gelungen:**" in result.feedback_md
    assert "**Das können Sie noch besser:**" in result.feedback_md
