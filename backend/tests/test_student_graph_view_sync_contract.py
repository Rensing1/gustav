"""Contract test to keep graph renderer copies in sync.

Why this exists:
  The student graph renderer currently exists in two locations:
  - backend/web/static/js/student_graph_view.js (production asset)
  - ui-dummies/shared/graph-view.js (prototype/demo asset)

  We keep the backend file as the source of truth. This test enforces that the
  demo copy stays byte-identical so bug fixes do not drift apart.
"""

from __future__ import annotations

from pathlib import Path


def test_ui_dummy_graph_renderer_matches_backend_source_of_truth() -> None:
    """The UI dummy renderer must stay in lockstep with the backend asset."""
    backend_graph = Path("backend/web/static/js/student_graph_view.js").read_text(encoding="utf-8")
    ui_dummy_graph = Path("ui-dummies/shared/graph-view.js").read_text(encoding="utf-8")

    assert ui_dummy_graph == backend_graph
