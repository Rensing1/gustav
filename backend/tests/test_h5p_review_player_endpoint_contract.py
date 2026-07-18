"""
Contract test: H5P service exposes a teacher-only review player endpoint.

Why:
    Teacher Live (matrix detail pane) should embed a read-only H5P player that
    loads the *student's* latest userState. We explicitly avoid a generic
    impersonation query parameter (see `as_user_id` removal guard) and instead
    require a short-lived encrypted Bearer credential that never enters a URL.

Note:
    This is a source-level contract guard. It does not execute the Node service.
"""

from __future__ import annotations

from pathlib import Path


def test_h5p_service_has_review_player_route() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    server_path = repo_root / "h5p-service" / "server.mjs"
    assert server_path.is_file(), f"Missing H5P service file: {server_path}"

    js = server_path.read_text(encoding="utf-8")

    # Route must exist (reverse-proxy strips `/h5p`, so the service uses `/player/...`).
    assert '"/player/review"' in js or "'/player/review'" in js

    # Review mode must use a Bearer credential, not a credential query parameter.
    assert "authorization" in js.lower()
    assert "req.query.review_token" not in js
    assert 'searchParams.set("review_token"' not in js
    assert 'searchParams.set("review_mode"' in js
    assert "Referrer-Policy" in js
    assert "httpOnly: true" in js
    assert "secure: true" in js
    assert 'sameSite: "strict"' in js
    assert 'path: "/h5p"' in js
