"""
Contract test: H5P service must guard H5P_REVIEW_TOKEN_SECRET in prod-like envs.

Why:
    Teacher review tokens are capability tokens consumed by the H5P sidecar.
    In production/staging we must fail fast if the signing secret is unset or
    still a placeholder (e.g. CHANGE_ME_DEV), otherwise review tokens become
    forgeable.

    This is a source-level contract guard (no Node runtime needed).
"""

from __future__ import annotations

from pathlib import Path


def _extract_block(src: str, *, start_token: str, end_token: str) -> str:
    start = src.find(start_token)
    assert start != -1, f"Missing start token: {start_token}"
    end = src.find(end_token, start + len(start_token))
    assert end != -1, f"Missing end token: {end_token}"
    return src[start:end]


def test_h5p_service_guards_review_token_secret_in_prod_like_envs() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    server_path = repo_root / "h5p-service" / "server.mjs"
    assert server_path.is_file(), f"Missing H5P service file: {server_path}"

    js = server_path.read_text(encoding="utf-8")
    block = _extract_block(js, start_token="const reviewTokenSecret", end_token="const storageDirs")

    assert "GUSTAV_ENV" in block, "Guard must be keyed off GUSTAV_ENV (prod/stage detection)"
    assert "CHANGE_ME" in block, "Guard must reject placeholder secrets"
    assert "process.exit" in block or "throw" in block, "Guard must fail fast on misconfiguration"

