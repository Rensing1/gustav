"""
Contract test: H5P task editor buttons must not trigger accidental form submits.

Why:
    The H5P task editor UI lives inside server-rendered pages which may contain
    forms. Buttons without an explicit `type="button"` can submit a surrounding
    form by default. We defensively call `event.preventDefault()` in click
    handlers to avoid unexpected navigation/state loss.
"""

from __future__ import annotations

from pathlib import Path


def test_h5p_task_editor_buttons_prevent_default_submit() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    js_path = repo_root / "backend" / "web" / "static" / "js" / "h5p_task_editor.js"
    assert js_path.is_file(), f"Missing JS file: {js_path}"
    src = js_path.read_text(encoding="utf-8")

    assert "btnImport" in src
    assert "btnExport" in src
    assert "btnReset" in src
    assert "btnSave" in src
    assert src.count("preventDefault") >= 4
