"""
Keep DSPy Signature docstrings in sync with the prompt reference document.

Why:
    The prompt contract for the learning pipeline lives in the DSPy Signatures.
    `docs/references/LLM-Prompts.md` is intended as a human-readable reference
    of the *exact* prompt texts (Signature docstrings). This test prevents drift
    between docs and code.
"""

from __future__ import annotations

import importlib
import inspect
import re
import sys
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Iterator

import pytest


def _install_fake_dspy(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Signature:
        pass

    def _input_field(*_args, **_kwargs):  # noqa: ANN001, ANN003
        return None

    def _output_field(*_args, **_kwargs):  # noqa: ANN001, ANN003
        return None

    class _Image:  # minimal placeholder used by signatures
        def __init__(self, *, url: str):  # noqa: ANN001
            self.url = url

    fake = SimpleNamespace(Signature=_Signature, InputField=_input_field, OutputField=_output_field, Image=_Image)
    monkeypatch.setitem(sys.modules, "dspy", fake)


@contextmanager
def _load_signature_module(module_name: str) -> Iterator[object]:
    """Import against fake DSPy without replacing a module used by later tests."""

    previous = sys.modules.pop(module_name, None)
    try:
        yield importlib.import_module(module_name)
    finally:
        if previous is None:
            sys.modules.pop(module_name, None)
        else:
            sys.modules[module_name] = previous


def _extract_signature_blocks_from_docs() -> dict[str, str]:
    """
    Parse docs/references/LLM-Prompts.md and extract the ` ```text` blocks for
    Signature docstrings.
    """
    path = Path("docs/references/LLM-Prompts.md")
    content = path.read_text(encoding="utf-8")

    blocks: dict[str, str] = {}
    current_title: str | None = None
    in_text_block = False
    buf: list[str] = []

    for line in content.splitlines():
        m = re.match(r"^###\s+6\.\d+\)\s+([A-Za-z0-9_]+)\s*$", line)
        if m:
            current_title = m.group(1)
            continue
        if line.strip() == "```text" and current_title:
            in_text_block = True
            buf = []
            continue
        if line.strip() == "```" and in_text_block and current_title:
            blocks[current_title] = "\n".join(buf).rstrip("\n")
            in_text_block = False
            current_title = None
            buf = []
            continue
        if in_text_block:
            buf.append(line)

    return blocks


@pytest.mark.parametrize(
    ("module_name", "signature_name"),
    [
        ("backend.learning.adapters.dspy.signatures", "FeedbackAnalysisSignature"),
        ("backend.learning.adapters.dspy.signatures", "FeedbackSynthesisSignature"),
        ("backend.learning.adapters.dspy.signatures", "FeedbackNoCriteriaSignature"),
        ("backend.learning.adapters.dspy.signatures", "VisualFeedbackAnalysisSignature"),
        ("backend.learning.adapters.dspy.signatures", "VisualFeedbackSynthesisSignature"),
        ("backend.learning.adapters.dspy.signatures", "VisualFeedbackNoCriteriaSignature"),
        ("backend.learning.adapters.dspy.signatures", "VisionOcrSignature"),
        ("backend.learning.adapters.dspy.dialog_assessment_program", "DialogAssessmentSignature"),
    ],
)
def test_signature_docstrings_match_reference(
    monkeypatch: pytest.MonkeyPatch,
    module_name: str,
    signature_name: str,
) -> None:
    _install_fake_dspy(monkeypatch)
    docs_blocks = _extract_signature_blocks_from_docs()
    assert signature_name in docs_blocks, f"Missing docs block for {signature_name}"

    with _load_signature_module(module_name) as sigs:
        cls = getattr(sigs, signature_name)
        doc = inspect.getdoc(cls) or ""
        assert doc == docs_blocks[signature_name]


def test_feedback_synthesis_contract_preserves_assessment(monkeypatch: pytest.MonkeyPatch) -> None:
    """The approved synthesis must preserve the assessment and its requirements."""
    _install_fake_dspy(monkeypatch)
    with _load_signature_module("backend.learning.adapters.dspy.signatures") as sigs:
        doc = inspect.getdoc(getattr(sigs, "FeedbackSynthesisSignature")) or ""

    assert "Geben Sie die Befunde der Auswertung zutreffend wieder" in doc
    assert "Führen Sie keine zusätzlichen Anforderungen ein und verändern Sie die Bewertung nicht." in doc


def test_repair_reference_matches_executed_suffix():
    """Documentation must describe the suffix actually sent on a repair call."""
    from backend.learning.adapters.dspy.programs import _run_analysis_repair

    calls = []
    _run_analysis_repair(
        runner=lambda **kwargs: calls.append(kwargs),
        criteria=["Begründen"], text_md="Antwort", repair_reason="{repair_reason}",
    )
    suffix = calls[0]["teacher_instructions_md"]
    reference = Path("docs/references/LLM-Prompts.md").read_text(encoding="utf-8")
    assert f"```text\n{suffix}\n```" in reference


def test_signature_fields_keep_output_and_teacher_guidance_contract(monkeypatch):
    """Keep technical constraints outside the verbatim pedagogical main prompts."""
    _install_fake_dspy(monkeypatch)
    fake = sys.modules["dspy"]
    fake.InputField = lambda **kwargs: kwargs
    fake.OutputField = lambda **kwargs: kwargs
    with _load_signature_module("backend.learning.adapters.dspy.signatures") as sigs:
        for name in (
            "FeedbackAnalysisSignature", "VisualFeedbackAnalysisSignature",
            "FeedbackSynthesisSignature", "VisualFeedbackSynthesisSignature",
            "FeedbackNoCriteriaSignature", "VisualFeedbackNoCriteriaSignature",
        ):
            cls = getattr(sigs, name)
            context = cls.teacher_context_md["desc"]
            assert "Schwerpunkt, Länge und Aufbau" in context
            assert "Bewertungsmaßstab, Sie-Form und Schutzregeln" in context
            if "Analysis" in name:
                result = cls.criteria_results["desc"]
                assert "Genau ein Ergebnis je Eingangskriterium in identischer Reihenfolge" in result
                assert "ganze Zahl 0–10" in result
                assert "nicht leere Begründung" in result
