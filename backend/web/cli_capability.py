"""Shared value type and exact path matching for CLI capabilities.

Why:
    Authoring and diagnostics use the same fail-closed CLI token allowlist.
    Keeping their common primitives neutral prevents either feature area from
    becoming the accidental owner of authentication infrastructure.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CLICapability:
    """Describe one explicitly allowed HTTP operation and its minimum scope."""

    method: str
    path_template: str
    required_scope: str


def path_matches_template(path_template: str, path: str) -> bool:
    """Return whether a concrete path matches a route template exactly."""

    template_parts = path_template.strip("/").split("/")
    path_parts = path.strip("/").split("/")
    if len(template_parts) != len(path_parts):
        return False
    for template_part, path_part in zip(template_parts, path_parts):
        if template_part.startswith("{") and template_part.endswith("}"):
            if not path_part:
                return False
            continue
        if template_part != path_part:
            return False
    return True
