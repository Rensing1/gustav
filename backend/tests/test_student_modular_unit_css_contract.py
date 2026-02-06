"""
Contract-ish test for the modular student workspace CSS.

Why this exists:
  The modular student workspace uses a `<details class="module-card">` wrapper
  with its own `<summary>`. Inside that wrapper we also render task history,
  which itself uses nested `<details>/<summary>` elements.

  A too-broad CSS selector like `.module-card summary { ... }` would style
  *all* nested summaries and break the look-and-feel of task history (attempts)
  compared to the linear unit view.

This test guards against that regression by requiring a direct-child selector.
"""

from __future__ import annotations

import re
from pathlib import Path


def test_student_modular_unit_css_scopes_module_card_summary_to_direct_child() -> None:
    css_path = Path("backend/web/static/css/student_modular_unit.css")
    css = css_path.read_text(encoding="utf-8")

    # Must style only the module card's own summary.
    assert ".module-card > summary" in css
    assert ".module-card > summary::-webkit-details-marker" in css

    # Must NOT style nested summaries (e.g. task history attempts).
    assert re.search(r"\\.module-card\\s+summary\\b", css) is None
