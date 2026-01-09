"""
Contract tests for the global H5P theme stylesheet (Option B).

Why:
    H5P editor/player ship with fixed light colors. In GUSTAV we want the UI
    to follow the active Light/Dark theme via the existing design tokens
    (`--color-*`, `--font-*`). This file guards the most important invariants:

    - The stylesheet must exist in the repo at the expected location.
    - It must *not* introduce hard-coded colors that would break dark mode.
    - It must include baseline editor overrides for surfaces and form controls.
"""

from __future__ import annotations

import re
from pathlib import Path


def test_h5p_theme_css_exists_and_uses_tokens() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    css_path = repo_root / "h5p-service" / "vendor" / "theme" / "h5p-gustav.css"
    assert css_path.is_file(), f"Missing theme CSS: {css_path}"

    css = css_path.read_text(encoding="utf-8")

    # The theme must be token-based; hard-coded colors make Dark Mode brittle.
    # (Allow '#' inside comments/URLs by only matching typical hex color patterns.)
    hex_colors = re.findall(r"#[0-9a-fA-F]{3,8}", css)
    assert not hex_colors, f"Theme CSS must not contain hard-coded hex colors: {hex_colors[:3]}"

    # Baseline editor surface + control theming is required for Dark Mode.
    assert ".h5peditor" in css
    assert re.search(r"\.h5peditor-form\s*\{", css), "Theme must override .h5peditor-form wrapper"
    assert "var(--color-bg-surface)" in css
    assert "var(--color-bg-base)" in css
    assert "var(--color-border)" in css
    assert "var(--color-text)" in css

    # H5P Hub is part of the editor "new content" flow and must be themed too.
    assert ".h5p-hub" in css
    assert ".h5p-hub .panel" in css

    # Ensure we actually override form controls; otherwise the editor stays bright in Dark Mode.
    assert ".h5peditor input" in css or ".h5peditor input," in css
    assert ".h5peditor textarea" in css
    assert ".h5peditor select" in css
