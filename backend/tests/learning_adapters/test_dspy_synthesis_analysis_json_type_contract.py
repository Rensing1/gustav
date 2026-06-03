"""Regression tests for the DSPy synthesis `analysis_json` input contract.

Why:
    Production warned about `Type mismatch for field 'analysis_json'` even
    though the payload was valid `criteria.v2` JSON. These tests exercise the
    same DSPy type compatibility check without performing any model call.
"""

from __future__ import annotations

import importlib
import sys
from typing import Any

from dspy.predict.predict import _is_value_compatible_with_type


def _load_real_signatures_module() -> object:
    """Reload signatures with the real DSPy package, not a lightweight test stub."""
    sys.modules.pop("backend.learning.adapters.dspy.signatures", None)
    return importlib.import_module("backend.learning.adapters.dspy.signatures")


def _criteria_v2_payload() -> dict[str, Any]:
    return {
        "schema": "criteria.v2",
        "score": 4,
        "criteria_results": [
            {
                "criterion": "Inhalt",
                "max_score": 10,
                "score": 8,
                "explanation_md": "Die Antwort enthält eine nachvollziehbare Begründung.",
            }
        ],
    }


def test_text_synthesis_signature_accepts_normalized_criteria_v2_dict() -> None:
    sigs = _load_real_signatures_module()
    field = sigs.FeedbackSynthesisSignature.input_fields["analysis_json"]  # type: ignore[attr-defined]

    assert _is_value_compatible_with_type(_criteria_v2_payload(), field.annotation)


def test_visual_synthesis_signature_accepts_normalized_criteria_v2_dict() -> None:
    sigs = _load_real_signatures_module()
    field = sigs.VisualFeedbackSynthesisSignature.input_fields["analysis_json"]  # type: ignore[attr-defined]

    assert _is_value_compatible_with_type(_criteria_v2_payload(), field.annotation)
