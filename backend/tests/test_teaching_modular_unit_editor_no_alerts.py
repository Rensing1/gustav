from pathlib import Path


def test_modular_editor_js_does_not_use_blocking_alerts() -> None:
    """The modular editor should not rely on blocking browser dialogs.

    Why:
        `window.alert()` blocks the UI thread and is a poor UX in a teaching
        workflow. The editor should surface errors inline (status bar / panel).
    """
    repo_root = Path(__file__).resolve().parents[2]
    js_path = repo_root / "backend/web/static/js/teaching_modular_unit_editor.js"
    src = js_path.read_text(encoding="utf-8")
    assert "window.alert" not in src

