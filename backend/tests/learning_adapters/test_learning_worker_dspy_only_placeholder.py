"""
Placeholder test module for future worker + DB DSPy-only integration tests.

Intent:
    This file is added as a planning marker for the next TDD step once the
    DSPy-only feedback adapter behaviour is implemented. It deliberately
    contains no executable tests yet, to avoid coupling worker behaviour to
    a pipeline that is still under refactoring.

Next steps:
    - Add integration tests that verify `learning_submissions` rows are
      updated with `criteria.v2` analysis_json and DSPy-generated feedback_md
      without any legacy LM calls.
"""

from __future__ import annotations

