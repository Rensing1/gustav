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
from pathlib import Path
from types import SimpleNamespace

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


def _load_signatures_module() -> object:
    # Ensure a clean import (pytest may have imported it earlier under a different `dspy`).
    sys.modules.pop("backend.learning.adapters.dspy.signatures", None)
    return importlib.import_module("backend.learning.adapters.dspy.signatures")


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
    "signature_name",
    [
        "FeedbackAnalysisSignature",
        "FeedbackSynthesisSignature",
        "FeedbackNoCriteriaSignature",
        "VisualFeedbackAnalysisSignature",
        "VisualFeedbackSynthesisSignature",
        "VisualFeedbackNoCriteriaSignature",
        "VisionOcrSignature",
    ],
)
def test_signature_docstrings_match_reference(monkeypatch: pytest.MonkeyPatch, signature_name: str) -> None:
    _install_fake_dspy(monkeypatch)
    docs_blocks = _extract_signature_blocks_from_docs()
    assert signature_name in docs_blocks, f"Missing docs block for {signature_name}"

    sigs = _load_signatures_module()
    cls = getattr(sigs, signature_name)
    doc = inspect.getdoc(cls) or ""
    assert doc == docs_blocks[signature_name]
