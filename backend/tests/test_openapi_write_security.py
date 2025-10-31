"""
OpenAPI guards for write endpoints.

Why:
- Ensure every state-changing endpoint documents CSRF expectations.
- Enforce cache-control headers (no-store) for 204 responses so intermediaries
  do not cache mutation acknowledgements.
"""
from __future__ import annotations

from pathlib import Path
import yaml


def _load_spec() -> dict:
    root = Path(__file__).resolve().parents[2]
    return yaml.safe_load((root / "api" / "openapi.yml").read_text(encoding="utf-8"))


def _iter_write_operations(spec: dict):
    paths = spec.get("paths", {})
    for path, path_item in paths.items():
        for method, operation in (path_item or {}).items():
            if method.lower() in {"post", "put", "patch", "delete"}:
                yield path, method.lower(), operation or {}


def test_write_operations_document_csrf_expectations():
    spec = _load_spec()
    missing = []
    for path, method, operation in _iter_write_operations(spec):
        notes = operation.get("x-security-notes")
        if isinstance(notes, str):
            notes = [notes]
        if not notes:
            missing.append(f"{method.upper()} {path}")
            continue
        if not any("CSRF" in str(note).upper() for note in notes):
            missing.append(f"{method.upper()} {path}")
    assert not missing, (
        "Missing CSRF documentation for write endpoints: " + ", ".join(missing)
    )


def test_write_operations_204_responses_set_cache_control():
    spec = _load_spec()
    missing = []
    for path, method, operation in _iter_write_operations(spec):
        responses = operation.get("responses", {}) or {}
        resp_204 = responses.get("204")
        if not resp_204:
            continue
        headers = resp_204.get("headers") or {}
        cache = headers.get("Cache-Control") if isinstance(headers, dict) else None
        if not cache or "schema" not in cache:
            missing.append(f"{method.upper()} {path}")
    assert not missing, (
        "Write endpoints with 204 responses must define Cache-Control header: "
        + ", ".join(missing)
    )
