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


def test_graph_default_fit_does_not_auto_zoom_in() -> None:
    """Default-fit should not auto-zoom in on small graphs.

    Why:
        On iPads the overview should show more context by default. Students can
        zoom in manually; auto-zooming in makes the graph feel "cropped".
    """
    js = _read_js()
    assert "fitMaxZoom: 0.9" in js


def test_workspace_state_version_drops_legacy_graph_pose() -> None:
    """Workspace state must be versioned to avoid persisting bad defaults.

    Why:
        The modular workspace persists `graphPose` (zoom/pan) in localStorage.
        If we change defaults (e.g. default fit zoom), old stored poses would
        make the UI appear unchanged until the student manually resets the
        state. A simple version bump allows us to keep open tabs but drop the
        legacy pose.
    """
    js = _read_js()
    assert "const STATE_VERSION = 2;" in js
    assert "const version = Number(st.version || 0);" in js
    assert "const graphPose = version === STATE_VERSION ? graphPoseRaw : null;" in js
