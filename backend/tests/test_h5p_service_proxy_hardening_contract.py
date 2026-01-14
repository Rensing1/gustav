"""
Contract tests: H5P service proxy / same-origin invariants.

Why:
    The H5P sidecar is reverse-proxied under `/h5p/*` and relies on forwarded
    headers for CSRF same-origin checks. Two hardening rules we want to keep:
    - `trust proxy` must be bounded (defense-in-depth; do not trust arbitrary hops)
    - Same-origin expected origin must consider `X-Forwarded-Port` and normalize
      default ports (avoid false-negative CSRF rejects in non-standard setups)

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


def test_h5p_service_trust_proxy_is_bounded() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    server_path = repo_root / "h5p-service" / "server.mjs"
    assert server_path.is_file(), f"Missing H5P service file: {server_path}"
    js = server_path.read_text(encoding="utf-8")

    assert 'app.set("trust proxy", true);' not in js
    # Default should be "off" (Express default), but deployments behind a
    # reverse-proxy can enable bounded proxy trust explicitly.
    block = _extract_block(
        js,
        start_token="const app = express();",
        end_token="// Security headers for all responses",
    )
    assert "process.env.H5P_TRUST_PROXY" in block
    assert 'app.set("trust proxy", 1);' in block


def test_h5p_same_origin_expected_origin_considers_forwarded_port() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    server_path = repo_root / "h5p-service" / "server.mjs"
    assert server_path.is_file(), f"Missing H5P service file: {server_path}"
    js = server_path.read_text(encoding="utf-8")

    block = _extract_block(
        js,
        start_token="function getPublicOrigin(req) {",
        end_token="function requireSameOrigin(req, res, next) {",
    )

    assert "x-forwarded-port" in block
    assert "defaultPort" in block
