"""
Contract test: H5P service `/ajax` endpoint must be CSRF-hardened and non-cacheable.

Why:
    The H5P Node service is reverse-proxied under `/h5p/*` (same-origin) and
    serves browser-facing endpoints. The Lumi webcomponents use `POST /ajax`
    for various actions (including user state / translations).

    Because this is a cookie-authenticated browser POST endpoint, we enforce:
    - strict same-origin checks (Origin/Referer) for *all* `/ajax` requests
    - `Cache-Control: no-store` (defense-in-depth for sensitive responses)
    - `Vary: Origin` for CSRF-aware caches

Note:
    This is a source-level contract guard. It does not execute the Node service.
"""

from __future__ import annotations

from pathlib import Path


def _extract_block(src: str, *, start_token: str, end_token: str) -> str:
    start = src.find(start_token)
    assert start != -1, f"Missing start token: {start_token}"
    end = src.find(end_token, start + len(start_token))
    assert end != -1, f"Missing end token: {end_token}"
    return src[start:end]


def test_h5p_ajax_requires_same_origin_and_sets_no_store_headers() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    server_path = repo_root / "h5p-service" / "server.mjs"
    assert server_path.is_file(), f"Missing H5P service file: {server_path}"

    js = server_path.read_text(encoding="utf-8")

    ajax_block = _extract_block(
        js,
        start_token='app.post("/ajax"',
        end_token='app.post("/finishedData"',
    )

    # Same-origin must be enforced for all browser POSTs.
    assert "requireSameOrigin(req, res" in ajax_block

    # The CSRF check should happen unconditionally (not only for teacher-only actions).
    assert "const writeActions" in ajax_block
    assert ajax_block.find("requireSameOrigin") < ajax_block.find("const writeActions")

    # Responses must be non-cacheable and vary by origin for CSRF-aware caches.
    assert 'res.setHeader("Cache-Control", "no-store")' in ajax_block
    assert 'res.setHeader("Vary", "Origin")' in ajax_block

