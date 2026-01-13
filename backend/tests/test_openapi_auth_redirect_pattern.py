"""
OpenAPI auth redirect patterns (in-app return-to paths).

Why:
    The `redirect` query parameter on auth endpoints must be constrained to a
    safe in-app path to prevent open redirects and path traversal. This test
    ensures the contract rejects `//` and `..` consistently.
"""

from __future__ import annotations

from pathlib import Path
import re

import yaml


def _load_spec() -> dict:
    root = Path(__file__).resolve().parents[2]
    return yaml.safe_load((root / "api" / "openapi.yml").read_text(encoding="utf-8"))


def _redirect_pattern(spec: dict, *, path: str) -> str:
    params = spec["paths"][path]["get"].get("parameters") or []
    for param in params:
        if param.get("in") == "query" and param.get("name") == "redirect":
            return str(((param.get("schema") or {}) or {}).get("pattern") or "")
    raise AssertionError(f"Missing redirect query parameter for {path}")


def test_auth_login_redirect_pattern_rejects_double_slash_and_traversal() -> None:
    spec = _load_spec()
    pattern = _redirect_pattern(spec, path="/auth/login")
    rx = re.compile(pattern)

    assert rx.fullmatch("/") is not None
    assert rx.fullmatch("/courses") is not None

    assert rx.fullmatch("//") is None
    assert rx.fullmatch("/a//b") is None
    assert rx.fullmatch("/..") is None
    assert rx.fullmatch("/a/../b") is None


def test_auth_logout_redirect_pattern_rejects_double_slash_and_traversal() -> None:
    spec = _load_spec()
    pattern = _redirect_pattern(spec, path="/auth/logout")
    rx = re.compile(pattern)

    assert rx.fullmatch("/") is not None
    assert rx.fullmatch("/auth/logout/success") is not None

    assert rx.fullmatch("//") is None
    assert rx.fullmatch("/a//b") is None
    assert rx.fullmatch("/..") is None
    assert rx.fullmatch("/a/../b") is None

