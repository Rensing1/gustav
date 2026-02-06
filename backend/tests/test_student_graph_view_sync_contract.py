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
