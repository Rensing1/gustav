"""Source contract for Teaching repository outage propagation.

Why:
    DBTeachingRepo owns translation of PostgreSQL connection failures. Web
    adapters may retain legacy fallbacks for unrelated errors, but a translated
    TeachingRepositoryUnavailable must always reach the central HTTP handler.
"""

from __future__ import annotations

import ast
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _calls_repo_directly(node: ast.Try) -> bool:
    body = ast.Module(body=node.body, type_ignores=[])
    for call in (item for item in ast.walk(body) if isinstance(item, ast.Call)):
        function = call.func
        if isinstance(function, ast.Name) and function.id == "_get_repo":
            return True
        if (
            isinstance(function, ast.Attribute)
            and isinstance(function.value, ast.Name)
            and function.value.id == "repo"
        ):
            return True
    return False


def _caught_name(handler: ast.ExceptHandler) -> str | None:
    return handler.type.id if isinstance(handler.type, ast.Name) else None


def test_generic_repo_catches_preserve_teaching_repository_unavailable() -> None:
    """Every direct repo catch must pass the context-owned outage through."""

    offenders: list[str] = []
    route_dir = _repo_root() / "backend" / "web" / "routes"
    for path in sorted(route_dir.glob("teaching*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in (item for item in ast.walk(tree) if isinstance(item, ast.Try)):
            caught = [_caught_name(handler) for handler in node.handlers]
            if "Exception" not in caught or not _calls_repo_directly(node):
                continue
            generic_index = caught.index("Exception")
            if "TeachingRepositoryUnavailable" not in caught[:generic_index]:
                offenders.append(f"{path.relative_to(_repo_root())}:{node.lineno}")

    assert offenders == []


def test_teaching_live_route_does_not_open_database_cursors() -> None:
    """SQL belongs to the Teaching adapter so driver errors are translated once."""

    path = _repo_root() / "backend" / "web" / "routes" / "teaching_live.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    offenders = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "open_repo_cursor"
    ]

    assert offenders == []
