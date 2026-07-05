"""Scan selected architecture boundaries against a committed baseline."""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
import sys
from typing import Any


CATEGORIES = (
    "usecase_fastapi_imports",
    "service_fastapi_imports",
    "web_direct_db_connects",
    "web_direct_supabase_client_creates",
)

ZERO_LIMIT_CATEGORIES = {
    "usecase_fastapi_imports",
    "service_fastapi_imports",
}

APPROVED_WEB_INFRASTRUCTURE = {
    ("backend", "web", "db_cursor.py"),
    ("backend", "web", "storage_wiring.py"),
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _iter_python_files(root: Path) -> list[Path]:
    return sorted(path for path in (root / "backend").rglob("*.py") if "__pycache__" not in path.parts)


def _relative_parts(path: Path) -> tuple[str, ...]:
    return path.relative_to(_repo_root()).parts


def _record(findings: dict[str, list[str]], category: str, path: Path, node: ast.AST) -> None:
    rel = path.relative_to(_repo_root()).as_posix()
    line = getattr(node, "lineno", 0)
    findings[category].append(f"{rel}:{line}")


def _attribute_chain(node: ast.AST) -> list[str]:
    parts: list[str] = []
    current: ast.AST | None = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
    return list(reversed(parts))


def _is_fastapi_module(name: str | None) -> bool:
    return bool(name == "fastapi" or (name and name.startswith("fastapi.")))


def _is_usecase(path: Path) -> bool:
    return "usecases" in _relative_parts(path)


def _is_service(path: Path) -> bool:
    return "services" in _relative_parts(path)


def _is_web_adapter(path: Path) -> bool:
    return _relative_parts(path)[:2] == ("backend", "web")


def _is_approved_web_infrastructure(path: Path) -> bool:
    return _relative_parts(path) in APPROVED_WEB_INFRASTRUCTURE


def _scan_file(path: Path, findings: dict[str, list[str]]) -> None:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:
        rel = path.relative_to(_repo_root()).as_posix()
        findings.setdefault("parse_errors", []).append(f"{rel}:{exc.lineno or 0}")
        return

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(_is_fastapi_module(alias.name) for alias in node.names):
                if _is_usecase(path):
                    _record(findings, "usecase_fastapi_imports", path, node)
                if _is_service(path):
                    _record(findings, "service_fastapi_imports", path, node)
        elif isinstance(node, ast.ImportFrom):
            if _is_fastapi_module(node.module):
                if _is_usecase(path):
                    _record(findings, "usecase_fastapi_imports", path, node)
                if _is_service(path):
                    _record(findings, "service_fastapi_imports", path, node)
        elif isinstance(node, ast.Call) and _is_web_adapter(path) and not _is_approved_web_infrastructure(path):
            func = node.func
            if isinstance(func, ast.Attribute) and _attribute_chain(func) == ["psycopg", "connect"]:
                _record(findings, "web_direct_db_connects", path, node)
            elif isinstance(func, ast.Name) and func.id == "create_client":
                _record(findings, "web_direct_supabase_client_creates", path, node)


def scan() -> dict[str, Any]:
    findings: dict[str, list[str]] = {category: [] for category in CATEGORIES}
    for path in _iter_python_files(_repo_root()):
        _scan_file(path, findings)
    return {
        "categories": {category: len(findings.get(category, [])) for category in CATEGORIES},
        "examples": {category: findings.get(category, [])[:25] for category in CATEGORIES},
        "parse_errors": findings.get("parse_errors", []),
    }


def _load_baseline(path: Path) -> dict[str, int]:
    data = json.loads(path.read_text(encoding="utf-8"))
    categories = data.get("categories", {})
    return {category: int(categories.get(category, 0)) for category in CATEGORIES}


def _check_baseline(current: dict[str, Any], baseline_path: Path) -> int:
    baseline = _load_baseline(baseline_path)
    current_categories = current["categories"]
    regressions: dict[str, tuple[int, int]] = {}

    for category in CATEGORIES:
        current_value = int(current_categories[category])
        limit = 0 if category in ZERO_LIMIT_CATEGORIES else baseline[category]
        if current_value > limit:
            regressions[category] = (limit, current_value)

    if not regressions:
        print("architecture-boundary-scan-ok")
        return 0

    print("Architecture boundary debt increased:", file=sys.stderr)
    for category, (old, new) in regressions.items():
        print(f"- {category}: limit={old}, current={new}", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--json", action="store_true", help="Print scan result as JSON.")
    args = parser.parse_args(argv)

    current = scan()
    if args.json or not args.baseline:
        print(json.dumps(current, indent=2, sort_keys=True))
    if args.baseline:
        return _check_baseline(current, args.baseline)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
