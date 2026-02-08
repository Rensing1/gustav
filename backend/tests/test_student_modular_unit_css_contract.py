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
    assert re.search(r"\.module-card\s+summary\b", css) is None


def test_student_modular_unit_css_overview_mode_overrides_graph_clamp_height() -> None:
    """Overview mode must not use the fixed clamp height.

    Why:
        In overview mode we lock page scrolling and let the graph fill the
        remaining viewport height via flex. A later generic rule uses
        `height: clamp(...)` which can override the earlier overview rules and
        cause visible cropping on iPads.
    """
    css_path = Path("backend/web/static/css/student_modular_unit.css")
    css = css_path.read_text(encoding="utf-8")

    assert re.search(
        r"html\.mode-overview\s+\.modular-unit-page\s+\.graph-shell\s*\{[^}]*\bmargin-bottom:\s*0\b",
        css,
        re.S,
    )
    assert re.search(
        r"html\.mode-overview\s+\.modular-unit-page\s+\.graph-container\s*\{[^}]*\bheight:\s*auto\b",
        css,
        re.S,
    )


def test_student_modular_unit_css_does_not_use_global_container_vertical_padding() -> None:
    """The modular workspace must not inherit global vertical `.container` padding.

    Why:
        `gustav.css` adds generous vertical padding to `.container` for some
        pages. The modular student workspace uses multiple `.container`
        wrappers (header + workspace sections). On iPads this wastes a lot of
        viewport height and makes the graph feel cramped.
    """
    css_path = Path("backend/web/static/css/student_modular_unit.css")
    css = css_path.read_text(encoding="utf-8")

    assert ".modular-unit-page .unit-head.container" in css
    assert ".modular-unit-page .workspace-view.container" in css
    assert "padding-top: 0" in css
    assert "padding-bottom: 0" in css
