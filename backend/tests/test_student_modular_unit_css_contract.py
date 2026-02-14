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


def test_student_modular_unit_css_ipad_overview_compacts_page_chrome_without_hiding() -> None:
    """iPad overview mode should compact breadcrumb/footer, not hide them.

    Why:
        Students reported that the graph feels too small on iPads. We keep
        breadcrumb/footer visible for orientation but reduce vertical chrome
        only in overview mode and iPad-like widths.
    """
    css_path = Path("backend/web/static/css/student_modular_unit.css")
    css = css_path.read_text(encoding="utf-8")

    # iPad-focused compact mode block should exist.
    assert "@media (min-width: 768px) and (max-width: 1366px)" in css
    assert "html.mode-overview .main-content" in css
    assert "html.mode-overview .breadcrumb" in css
    assert "html.mode-overview .content-footer" in css
    assert "html.mode-overview .footer-content" in css

    # Keep footer/breadcrumb visible in compact mode (no hidden chrome).
    assert re.search(r"html\.mode-overview\s+\.breadcrumb\s*\{[^}]*display\s*:\s*none", css, re.S) is None
    assert re.search(r"html\.mode-overview\s+\.content-footer\s*\{[^}]*display\s*:\s*none", css, re.S) is None
    assert re.search(r"html\.mode-overview\s+\.footer-content\s*\{[^}]*display\s*:\s*none", css, re.S) is None


def test_student_modular_unit_css_ipad_overview_compacts_header_and_toolbar() -> None:
    """iPad overview mode should reduce vertical space above the graph."""
    css_path = Path("backend/web/static/css/student_modular_unit.css")
    css = css_path.read_text(encoding="utf-8")

    assert "html.mode-overview .modular-unit-page .unit-head" in css
    assert "html.mode-overview .modular-unit-page .unit-title" in css
    assert "html.mode-overview .modular-unit-page .sticky-toolbar" in css
    assert "html.mode-overview .modular-unit-page .sticky-toolbar__inner" in css
    assert "html.mode-overview .modular-unit-page .graph-overlay--top" in css


def test_student_modular_unit_css_ipad_profiles_differentiate_11_and_12_9() -> None:
    """iPad 11 and 12.9 should use separate overview density profiles.

    Why:
        The 11" viewport needs stronger compaction than 12.9". We model this
        via a general iPad compact profile plus a larger-iPad override.
    """
    css_path = Path("backend/web/static/css/student_modular_unit.css")
    css = css_path.read_text(encoding="utf-8")

    # Base iPad profile (covers 11") must exist.
    assert "@media (min-width: 768px) and (max-width: 1366px)" in css

    # Large iPad profile (12.9") should be an explicit override.
    assert "@media (min-width: 1024px) and (min-height: 1024px)" in css

    # 11" profile: denser controls and tighter top spacing.
    assert "--toolbar-control-h: 32px;" in css
    assert "top: var(--space-1);" in css

    # 12.9" override: slightly roomier controls and spacing.
    assert "--toolbar-control-h: 34px;" in css
    assert "top: var(--space-2);" in css
