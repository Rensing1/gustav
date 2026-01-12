"""
Contract test: H5P service CSP hardening + debug access control.

Why:
    The H5P Node service is reverse-proxied under `/h5p/*` (same-origin) and
    historically shipped a very permissive CSP (`*`, `unsafe-inline`,
    `unsafe-eval`) for all routes. This increases the XSS and data exfiltration
    surface for a component that executes a lot of third-party JavaScript
    (trusted-content model).

    We want defense-in-depth:
    - Default CSP for `/h5p/*` must be strict (no `*`, no `unsafe-eval`).
    - Only the standalone debug HTML pages (`/h5p/editor`, `/h5p/player`) may
      allow inline scripts, because they currently contain inline `<script>` and
      an inline import map.
    - Debug HTML pages are admin-only (teacher/student must get 403).

Note:
    This is a source-level contract guard. It does not execute the Node service.
"""

from __future__ import annotations

import re
from pathlib import Path


def _extract_csp_directives(js: str, const_name: str) -> list[str]:
    """
    Extract directives from a JS constant defined as:

        const CSP_FOO = [
          "...",
          "...",
        ].join("; ");
    """

    pattern = rf"const\s+{re.escape(const_name)}\s*=\s*\[(?P<body>.*?)\]\.join\(\"; \"\);"
    match = re.search(pattern, js, flags=re.DOTALL)
    assert match, f"Missing CSP constant {const_name} in h5p-service/server.mjs"

    body = match.group("body")
    # We intentionally use double-quoted literals in server.mjs so we can keep
    # CSP tokens like `'self'` readable without escaping.
    directives = re.findall(r"\"([^\"]+)\"", body)
    assert directives, f"Could not parse directives for {const_name}"
    return [d.strip() for d in directives if d.strip()]


def _get_directive(directives: list[str], name: str) -> str:
    for d in directives:
        if d.startswith(name + " "):
            return d
    raise AssertionError(f"Missing directive {name} in CSP: {directives}")


def test_h5p_csp_policy_matrix_and_debug_access_control() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    server_path = repo_root / "h5p-service" / "server.mjs"
    assert server_path.is_file(), f"Missing H5P service file: {server_path}"

    js = server_path.read_text(encoding="utf-8")

    # Debug HTML pages must be admin-only.
    assert 'app.get("/editor",' in js and "requireAdmin" in js
    assert re.search(r'app\.get\(\"/editor\",\s*.*?requireAdmin', js), "editor debug page must be admin-only"
    assert re.search(r'app\.get\(\"/player\",\s*.*?requireAdmin', js), "player debug page must be admin-only"

    # Default CSP is strict (no wildcards, no unsafe-eval).
    default_directives = _extract_csp_directives(js, "CSP_DEFAULT")
    assert not any("*" in d for d in default_directives), default_directives
    assert not any("unsafe-eval" in d for d in default_directives), default_directives

    assert "default-src 'self'" in default_directives
    assert "base-uri 'none'" in default_directives
    assert "object-src 'none'" in default_directives
    assert "frame-ancestors 'self'" in default_directives

    assert _get_directive(default_directives, "script-src") == "script-src 'self'"
    assert _get_directive(default_directives, "style-src") == "style-src 'self' 'unsafe-inline'"

    # Debug HTML CSP is a scoped exception: inline scripts allowed, still no unsafe-eval.
    debug_directives = _extract_csp_directives(js, "CSP_DEBUG_HTML")
    assert not any("*" in d for d in debug_directives), debug_directives
    assert not any("unsafe-eval" in d for d in debug_directives), debug_directives

    assert _get_directive(debug_directives, "script-src") == "script-src 'self' 'unsafe-inline'"

    # The default security header must use CSP_DEFAULT.
    assert '"Content-Security-Policy": CSP_DEFAULT' in js

    # Only debug HTML routes may override the header to CSP_DEBUG_HTML.
    # Guard this by requiring exactly two uses of CSP_DEBUG_HTML in sendHtml calls
    # (editor + player pages).
    send_html_uses = re.findall(r"sendHtml\([\s\S]*?CSP_DEBUG_HTML", js)
    assert len(send_html_uses) == 2, f"Expected 2 CSP_DEBUG_HTML overrides, got {len(send_html_uses)}"
