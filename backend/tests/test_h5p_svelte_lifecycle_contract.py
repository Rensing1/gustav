"""
Contract tests for the Svelte-owned H5P lifecycle.

Why:
    The teacher H5P editor is mounted and unmounted by Svelte when teachers
    switch between tasks. A global HTMX-style bootstrap is too brittle for this
    setup and caused editors to stop rendering after switching tasks.

    We therefore require an explicit runtime mount API for the editor asset and
    remove the synthetic `htmx:afterSwap` bridge from the Svelte component.
"""

from __future__ import annotations

from pathlib import Path


def test_teacher_h5p_editor_uses_explicit_runtime_mount_api() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    component_path = repo_root / "frontend" / "src" / "lib" / "components" / "TeacherH5PTaskEditor.svelte"
    runtime_path = repo_root / "frontend" / "static" / "js" / "h5p_task_editor.js"

    component_src = component_path.read_text(encoding="utf-8")
    runtime_src = runtime_path.read_text(encoding="utf-8")

    assert "loadH5PTaskEditorModule" in component_src
    assert "htmx:afterSwap" not in component_src
    assert "mountH5PTaskEditor" in runtime_src
    assert "return {" in runtime_src
    assert "destroy()" in runtime_src


def test_shipped_h5p_editor_runtime_no_longer_depends_on_htmx_swaps() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    runtime_path = repo_root / "backend" / "web" / "static" / "js" / "h5p_task_editor.js"
    runtime_src = runtime_path.read_text(encoding="utf-8")

    assert "htmx:afterSwap" not in runtime_src
    assert "htmx:restored" not in runtime_src
    assert "mountH5PTaskEditor" in runtime_src
