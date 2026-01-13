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


def _extract_block(src: str, *, start_token: str, end_token: str) -> str:
    start = src.find(start_token)
    assert start != -1, f"Missing start token: {start_token}"
    end = src.find(end_token, start + len(start_token))
    assert end != -1, f"Missing end token: {end_token}"
    return src[start:end]


def test_h5p_task_editor_buttons_prevent_default_submit() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    js_path = repo_root / "backend" / "web" / "static" / "js" / "h5p_task_editor.js"
    assert js_path.is_file(), f"Missing JS file: {js_path}"
    src = js_path.read_text(encoding="utf-8")

    new_block = _extract_block(
        src,
        start_token="btnNew.addEventListener('click'",
        end_token="btnLoad.addEventListener('click'",
    )
    assert "preventDefault" in new_block

    load_block = _extract_block(
        src,
        start_token="btnLoad.addEventListener('click'",
        end_token="btnSave.addEventListener('click'",
    )
    assert "preventDefault" in load_block

    save_block = _extract_block(
        src,
        start_token="btnSave.addEventListener('click'",
        end_token="setStatus('Ready.')",
    )
    assert "preventDefault" in save_block

