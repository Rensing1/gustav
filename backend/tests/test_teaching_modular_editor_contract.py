"""Contract-ish tests for the teacher modular unit editor.

Why these tests exist:
  The teacher modular editor relies on client-side JS for edge rendering and
  drag/drop. We don't run a browser test suite in CI, so regressions can sneak
  in easily.

  These lightweight tests therefore lock a few *implementation contracts*
  that matter for UX quality:
  - edges are rendered as smooth SVG paths (student-like look)
  - redraw is throttled via requestAnimationFrame (scroll performance)
  - default edge styles are neutral (no progress/status colors in editor)
"""

from __future__ import annotations

from pathlib import Path


def _read_js() -> str:
    return Path("backend/web/static/js/teaching_modular_unit_editor.js").read_text(encoding="utf-8")


def _read_css() -> str:
    return Path("backend/web/static/css/teaching_modular_unit_editor.css").read_text(encoding="utf-8")


def test_editor_edges_are_svg_paths_with_curves() -> None:
    js = _read_js()

    # We want a student-like look: draw SVG <path> with cubic curves, not an
    # orthogonal <polyline>.
    assert "createElementNS('http://www.w3.org/2000/svg', 'path')" in js
    assert "setAttribute('d'" in js
    assert " C " in js or "C " in js

    # Regression guard: avoid going back to polylines.
    assert "createElementNS('http://www.w3.org/2000/svg', 'polyline')" not in js


def test_editor_edge_redraw_is_throttled_with_request_animation_frame() -> None:
    js = _read_js()

    # Scrolling the editor graph should not trigger an unbounded draw() call.
    # We require an rAF-based throttle helper.
    assert "requestAnimationFrame" in js
    assert "scheduleDraw" in js


def test_editor_edge_styles_are_neutral_like_student_ui() -> None:
    css = _read_css()

    # Marker arrow should inherit stroke color like in the student graph.
    assert "fill: context-stroke" in css

    # Default edge color should not be a success/green tone.
    assert "163, 217, 106" not in css

    # Edge layer should use theme tokens.
    assert "var(--color-text-muted" in css or "color-mix(" in css
