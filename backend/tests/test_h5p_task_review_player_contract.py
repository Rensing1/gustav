"""
Contract test: Teacher H5P review player JS must be read-only and token-based.

Why:
    The student H5P player listens to xAPI and persists attempts. In the teacher
    review UI (live matrix detail pane) we must be strictly read-only:
    - load the player model via `/h5p/player/review`
    - pass the server-issued `review_token`
    - never post learning submissions or finished data

Note:
    This is a source-level contract guard. It does not execute JavaScript.
"""

from __future__ import annotations

from pathlib import Path


def test_h5p_task_review_player_js_contract() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    js_path = repo_root / "backend" / "web" / "static" / "js" / "h5p_task_review_player.js"
    assert js_path.is_file(), f"Missing JS file: {js_path}"

    js = js_path.read_text(encoding="utf-8")

    assert "/h5p/player/review" in js
    assert "review_token" in js
    assert "read_only_state" in js

    # Must not persist attempts like the student player.
    assert "/api/learning" not in js
    assert "Idempotency-Key" not in js
    assert "xAPI" not in js
