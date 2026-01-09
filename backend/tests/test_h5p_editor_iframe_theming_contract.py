"""
Contract test: H5P editor iframe theming hook.

Why:
    Lumi's `<h5p-editor>` renders the actual editor inside an iframe.
    Styles from the parent document (including GUSTAV design tokens) do not
    automatically apply inside that iframe.

    Therefore we must explicitly inject the theme stylesheet and copy the
    relevant CSS variables into the iframe document from the parent document.

Note:
    This test does not execute JavaScript. It guards the presence of the
    theming hook in the shipped JS file so future refactors don't silently
    remove it.
"""

from __future__ import annotations

from pathlib import Path


def test_h5p_task_editor_js_contains_iframe_theme_hook() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    js_path = repo_root / "backend" / "web" / "static" / "js" / "h5p_task_editor.js"
    assert js_path.is_file(), f"Missing JS file: {js_path}"

    js = js_path.read_text(encoding="utf-8")

    # The hook must target the editor iframe.
    assert ".h5p-editor-iframe" in js
    # The hook must inject the shared theme stylesheet (served by the H5P service).
    assert "/h5p/theme/h5p-gustav.css" in js

    # The hook must keep the theme stylesheet last inside the iframe <head>,
    # because the H5P editor can append additional styles dynamically.
    assert "childList" in js, "Expected a MutationObserver on the iframe <head> (childList)"

    # The hook should copy *all* CSS variables from the parent document so the
    # iframe can use the same GUSTAV token set (spacing, typography, colors).
    assert "startsWith(\"--\")" in js or "startsWith('--')" in js

    # The iframe document must not apply upstream layout constraints (e.g. max-width: 960px).
    assert "maxWidth" in js

    # Rich-text fields in the H5P editor use CKEditor, which renders its editable
    # surface in a nested iframe. We theme that nested iframe too, otherwise
    # focusing a text field reintroduces white backgrounds in Dark Mode.
    assert "cke_wysiwyg_frame" in js
