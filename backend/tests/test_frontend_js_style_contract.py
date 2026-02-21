from __future__ import annotations

from pathlib import Path


def test_gustav_js_contains_no_tab_characters() -> None:
    """Keep frontend code review-friendly and consistent (FOSS/teaching project)."""
    js = Path("backend/web/static/js/gustav.js").read_text(encoding="utf-8")
    assert "\t" not in js

