"""
Contract test: H5P player model must be fail-closed for student access denials.

Why:
    Students load H5P content via the sidecar `GET /h5p/player/model`. The sidecar
    performs an access-check against the Learning API to ensure the content_id is
    part of a released H5P task in the given course.

    If access cannot be proven, the sidecar must respond in a fail-closed way
    that does not leak whether a given `content_id` exists in storage.

Note:
    This is a source-level contract guard. It does not execute Node.
"""

from __future__ import annotations

from pathlib import Path


def _extract_block(src: str, *, start_token: str, end_token: str) -> str:
    start = src.find(start_token)
    assert start != -1, f"Missing start token: {start_token}"
    end = src.find(end_token, start + len(start_token))
    assert end != -1, f"Missing end token: {end_token}"
    return src[start:end]


def test_h5p_player_model_denies_student_access_with_404_not_found() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    server_path = repo_root / "h5p-service" / "server.mjs"
    assert server_path.is_file(), f"Missing H5P service file: {server_path}"

    js = server_path.read_text(encoding="utf-8")

    block = _extract_block(
        js,
        start_token='app.get("/player/model"',
        end_token='app.get("/player/review"',
    )

    idx = block.find("if (!allowed) {")
    assert idx != -1, "Expected a denied-access branch `if (!allowed)` in /player/model"

    window = block[idx : idx + 220]
    assert 'sendJson(res, 404, { error: "not_found" });' in window
    assert 'sendJson(res, 403, { error: "forbidden" });' not in window


def test_h5p_player_model_treats_access_check_errors_as_not_found_in_student_scope() -> None:
    """Fail-closed: upstream errors must not introduce distinguishable signals."""

    repo_root = Path(__file__).resolve().parents[2]
    server_path = repo_root / "h5p-service" / "server.mjs"
    assert server_path.is_file(), f"Missing H5P service file: {server_path}"

    js = server_path.read_text(encoding="utf-8")

    block = _extract_block(
        js,
        start_token='app.get("/player/model"',
        end_token='app.get("/player/review"',
    )

    student_check = _extract_block(
        block,
        start_token="if (allowed === null) {",
        end_token="if (!allowed) {",
    )
    assert 'sendJson(res, 403, { error: "forbidden" });' not in student_check
    assert 'sendJson(res, 404, { error: "not_found" });' in student_check
