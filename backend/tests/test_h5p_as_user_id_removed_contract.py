"""
Contract test: remove `as_user_id` from the H5P player model surface.

Why:
    `as_user_id` expands the impersonation / state-leak surface of the H5P
    integration. We do not have a product use-case for it and therefore remove
    it entirely:
    - the embedded student player must not send it
    - the H5P service must not accept/forward it

Note:
    This is a source-level contract guard. It does not execute the Node service.
"""

from __future__ import annotations

from pathlib import Path


def test_h5p_player_model_does_not_use_as_user_id() -> None:
    repo_root = Path(__file__).resolve().parents[2]

    server_path = repo_root / "h5p-service" / "server.mjs"
    assert server_path.is_file(), f"Missing H5P service file: {server_path}"
    server_js = server_path.read_text(encoding="utf-8")
    assert "as_user_id" not in server_js
    assert "asUserId" not in server_js

    player_path = repo_root / "backend" / "web" / "static" / "js" / "h5p_task_player.js"
    assert player_path.is_file(), f"Missing JS file: {player_path}"
    player_js = player_path.read_text(encoding="utf-8")
    assert "as_user_id" not in player_js
    assert "asUserId" not in player_js

