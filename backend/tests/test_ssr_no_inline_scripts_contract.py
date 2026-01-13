"""
Contract test: SSR pages must not emit inline <script> blocks.

Why:
    The main app CSP is intentionally strict for scripts:
      - `script-src 'self'` (no `unsafe-inline`)
    Therefore SSR templates must not include any inline `<script>...</script>`
    blocks. All JavaScript must be served as static files and loaded via `src=`.

Note:
    This is a source-level contract guard. It does not execute the web app.
"""

from __future__ import annotations

import re
from pathlib import Path


def test_backend_web_main_has_no_inline_script_tags() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    main_py = repo_root / "backend" / "web" / "main.py"
    assert main_py.is_file(), f"Missing file: {main_py}"

    src = main_py.read_text(encoding="utf-8")
    script_tags = re.findall(r"<script\b[^>]*>", src, flags=re.IGNORECASE)
    assert script_tags, "Expected at least one <script src=...> tag in main.py"

    inline = [tag for tag in script_tags if "src=" not in tag.lower()]
    assert not inline, f"Inline <script> tags found (must use src=): {inline}"
