"""
Contract test: H5P submit must dispatch modular graph refresh.

Why:
    The modular workspace only refreshes unlock state after a
    `modularGraphRefresh` event. H5P submissions use `fetch` and must emit
    this event explicitly so newly unlocked modules become visible without
    a full page reload.

Note:
    This is a source-level contract guard. It does not execute JavaScript.
"""

from __future__ import annotations

from pathlib import Path


def _read_js() -> str:
    return Path("backend/web/static/js/h5p_task_player.js").read_text(encoding="utf-8")


def test_h5p_task_player_dispatches_modular_graph_refresh_event() -> None:
    js = _read_js()

    assert "modularGraphRefresh" in js
    assert "CustomEvent" in js
    assert "bubbles: true" in js
    assert "composed: true" in js
    assert "detail: { courseId:" in js
    assert "unitId }" in js or "unitId}" in js
