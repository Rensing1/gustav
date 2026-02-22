"""Contract-ish tests for the student modular workspace JS.

Why these tests exist:
  The student modular workspace is a fairly JS-heavy page, but we don't run a
  browser/E2E suite in CI for every change. Small regressions can slip in when
  state is cached in-memory and the DOM lifecycle changes.

  These tests therefore assert a few *implementation contracts* that are
  critical for UX correctness.

Note:
  These are intentionally lightweight and string-based. They are not meant to
  replace real browser tests, but they do prevent accidental regressions.
"""

from __future__ import annotations

from pathlib import Path


def _read_js() -> str:
    return Path("backend/web/static/js/student_modular_workspace.js").read_text(encoding="utf-8")


def test_close_module_resets_loaded_cache() -> None:
    """Closing a module must reset its loaded flags.

    Otherwise reopening the module builds fresh DOM but the loader refuses to
    fetch content again, leaving the student with an empty module body.
    """
    js = _read_js()

    # Ensure the close handler removes the module from both caches.
    assert "loadedModules.delete(mid)" in js
    assert "loadingModules.delete(mid)" in js


def test_error_overlay_uses_text_content_not_html_interpolation() -> None:
    """Error text must not be interpolated into innerHTML templates."""
    js = _read_js()

    # Avoid HTML interpolation of dynamic error messages.
    assert "${String(err" not in js
    assert "graphLayer.replaceChildren(" in js
    assert "msg.textContent = String(err && err.message ? err.message : err)" in js


def test_graph_default_fit_uses_adaptive_viewport_caps() -> None:
    """Default-fit should adapt zoom caps by viewport width.

    Why:
        A single global cap makes desktop too small or tablet too large.
        A simple breakpoint-based cap keeps first render usable on both.
    """
    js = _read_js()
    assert "function computeFitMaxZoom()" in js
    assert "if (viewportW < 900) return 0.9;" in js
    assert "if (viewportW < 1280) return 1.05;" in js
    assert "return 1.2;" in js
    assert "fitMaxZoom: computeFitMaxZoom()," in js


def test_workspace_state_normalization_always_resets_graph_pose() -> None:
    """Persisted graph pose must not survive page reloads.

    Why:
        Zoom/pan from a previous session can make new fit defaults appear
        ineffective and create inconsistent cross-device first impressions.
    """
    js = _read_js()
    assert "graphPose: null" in js
    assert "return { version: STATE_VERSION, view, openTabs, activeTab, expanded, graphPose: null };" in js


def test_open_module_from_graph_forces_expanded_card_after_view_switch() -> None:
    """Opening from graph must end with an expanded module card.

    Why:
        On slower layout transitions (or when content view is hidden), an
        immediate open attempt can be lost. A second pass after the view switch
        keeps behavior deterministic for students.
    """
    js = _read_js()
    assert "function openModuleCard(mid, { jump } = { jump: false })" in js
    assert "state.expanded[mid] = true;" in js
    assert "card.details.open = true;" in js
    assert "const switchedToContent = state.view !== 'content';" in js
    assert "openModuleCard(mid, { jump: true });" in js
    assert "if (switchedToContent) {" in js
    assert "window.requestAnimationFrame(() => {" in js
    assert "openModuleCard(mid, { jump: false });" in js


def test_build_graph_model_centers_nodes_per_phase_instead_of_left_anchor() -> None:
    """Node X positions should be centered per phase, not left-anchored.

    Why:
        With a fixed left anchor, phases with few modules appear visually
        shifted to the left. Per-phase centering keeps the overview balanced.
    """
    js = _read_js()

    assert "const phaseCenterX = BASE_X + GAP_X * 1.5;" in js
    assert "const modulesByPhaseId = new Map();" in js
    assert "const phaseXByModuleId = new Map();" in js
    assert "const startX = phaseCenterX - ((phaseModules.length - 1) * GAP_X) / 2;" in js
    assert "const x = phaseXByModuleId.get(id) ?? phaseCenterX;" in js

    # Old left-anchored formula must not be used anymore.
    assert "const x = BASE_X + (pos - 1) * GAP_X;" not in js


def test_phase_sublevels_activate_only_for_degree_three_conflicts() -> None:
    """Vertical sublevels should start at degree >= 3 (in or out).

    Why:
        For degree 2 conflicts, lane-routed edges are usually enough and avoid
        unnecessary node movement. Dense conflicts (>=3) need extra vertical
        structure.
    """
    js = _read_js()
    assert "const CONFLICT_DEGREE_THRESHOLD = 3;" in js
    assert "if (indeg >= CONFLICT_DEGREE_THRESHOLD || outdeg >= CONFLICT_DEGREE_THRESHOLD)" in js


def test_build_graph_model_applies_local_phase_sublevels_with_bounded_offsets() -> None:
    """Graph model should switch to strict two levels for dense conflicts.

    Why:
        The student view should remain stable and readable:
        - degree 2: stay on one row + lane-routed edges
        - degree >= 3: move to two clear rows (source/target)
    """
    js = _read_js()
    assert "const TWO_LEVEL_GAP_Y = 132;" in js
    assert "const displayYByModuleId = computePhaseTwoLevelDisplayYByModuleId({ modules, edgesRaw });" in js
    assert "const yTop = baseY - TWO_LEVEL_GAP_Y / 2;" in js
    assert "const yBottom = baseY + TWO_LEVEL_GAP_Y / 2;" in js
    assert "if (outdeg >= CONFLICT_DEGREE_THRESHOLD)" in js
    assert "if (indeg >= CONFLICT_DEGREE_THRESHOLD)" in js
    assert "const y = displayYByModuleId.get(id) ?? baseY;" in js


def test_two_level_assignment_uses_named_score_weights() -> None:
    """Two-level scoring should use named constants instead of raw +3/+2 values."""
    js = _read_js()
    assert "const TOP_SEED_WEIGHT = 3;" in js
    assert "const BOTTOM_SEED_WEIGHT = 3;" in js
    assert "const TOP_NEIGHBOR_WEIGHT = 2;" in js
    assert "const BOTTOM_NEIGHBOR_WEIGHT = 2;" in js
