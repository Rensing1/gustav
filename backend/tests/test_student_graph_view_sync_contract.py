"""Contract tests for the graph renderer source of truth.

Why this exists:
  The production renderer now lives only in
  `backend/web/static/js/student_graph_view.js`.
  The old ui-dummy app is intentionally removed to avoid drift and stale
  maintenance paths.
"""

from __future__ import annotations

from pathlib import Path


def test_ui_dummies_directory_is_removed() -> None:
    """No obsolete UI dummy workspace should remain in the repository."""
    assert not Path("ui-dummies").exists()


def _read_graph_view_js() -> str:
    return Path("backend/web/static/js/student_graph_view.js").read_text(encoding="utf-8")


def test_student_graph_view_uses_count_aware_symmetric_lane_offsets() -> None:
    """Edge lanes should be symmetric for each group.

    Why:
      For two outgoing edges, students should see one lane above and one lane
      below (instead of center + one side), which avoids a fake "main line"
      impression.
    """
    js = _read_graph_view_js()
    assert "function laneOffsetForIndex(index, count, gap)" in js
    assert "const mid = (size - 1) / 2;" in js
    assert "return (i - mid) * g;" in js


def test_student_graph_view_groups_edges_before_lane_assignment() -> None:
    """Lane assignment should happen per local routing group.

    Why:
      Group-local lanes are more predictable and stable than one global lane
      index across the full graph.
    """
    js = _read_graph_view_js()
    assert "const grouped = new Map();" in js
    assert "function buildLaneGroups(" in js
    assert "const lane = laneOffsetForIndex(idx, list.length, LANE_GAP);" in js


def test_student_graph_view_refactors_edge_pipeline_into_helpers() -> None:
    """Edge rendering should be split into small helpers for maintainability."""
    js = _read_graph_view_js()
    assert "function collectRenderableEdges(" in js
    assert "function buildLaneGroups(" in js
    assert "function sortEdgesDeterministically(" in js
    assert "function computeLaneOffsets(" in js
    assert "function buildEdgePath(" in js


def test_student_graph_view_uses_named_lane_and_curve_constants() -> None:
    """Magic numbers in edge rendering should be named constants."""
    js = _read_graph_view_js()
    assert "const LANE_GAP_PX = 18;" in js
    assert "const SAME_LEVEL_EPSILON = 8;" in js
    assert "const CURVE_FACTOR = 0.55;" in js
    assert "const CURVE_MIN = 36;" in js
    assert "const CURVE_MAX = 160;" in js


def test_student_graph_view_applies_lane_offsets_in_both_curve_branches() -> None:
    """Lane offsets must influence both vertical- and horizontal-dominant curves."""
    js = _read_graph_view_js()
    assert "const c = clamp(ady * CURVE_FACTOR, CURVE_MIN, CURVE_MAX)" in js
    assert "const c = clamp(adx * CURVE_FACTOR, CURVE_MIN, CURVE_MAX)" in js
    # Vertical-dominant branch should include both offsets.
    assert "C ${x1 + offsetX} ${y1 + c + offsetY}" in js
    assert "${x2 + offsetX} ${y2 - c + offsetY}" in js
    # Horizontal-dominant branch should include both offsets.
    assert "C ${x1 + c + offsetX} ${y1 + offsetY}" in js
    assert "${x2 - c + offsetX} ${y2 + offsetY}" in js
