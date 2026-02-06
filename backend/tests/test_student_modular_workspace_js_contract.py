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
