"""Scan import-boundary debt against a committed baseline."""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
import sys
from typing import Any


CATEGORIES = (
    "flat_routes_imports",
    "flat_components_imports",
    "backend_web_routes_imports",
    "sys_path_mutations",
)

DEFAULT_EXCLUDES = {
    "__pycache__",
    ".pytest_cache",
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _iter_python_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted((root / "backend").rglob("*.py")):
        if any(part in DEFAULT_EXCLUDES for part in path.parts):
            continue
        files.append(path)
    return files


def _record(findings: dict[str, list[str]], category: str, path: Path, node: ast.AST) -> None:
    rel = path.relative_to(_repo_root()).as_posix()
    line = getattr(node, "lineno", 0)
    findings[category].append(f"{rel}:{line}")


def _is_module(name: str | None, prefix: str) -> bool:
    return bool(name == prefix or (name and name.startswith(f"{prefix}.")))


def _attribute_chain(node: ast.AST) -> list[str]:
    parts: list[str] = []
    current: ast.AST | None = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
    return list(reversed(parts))


def _scan_file(path: Path, findings: dict[str, list[str]]) -> None:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:
        rel = path.relative_to(_repo_root()).as_posix()
        findings.setdefault("parse_errors", []).append(f"{rel}:{exc.lineno or 0}")
        return

    is_web_adapter = path.relative_to(_repo_root()).parts[:2] == ("backend", "web")

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _is_module(alias.name, "routes"):
                    _record(findings, "flat_routes_imports", path, node)
                if _is_module(alias.name, "components"):
                    _record(findings, "flat_components_imports", path, node)
                if (not is_web_adapter) and _is_module(alias.name, "backend.web.routes"):
                    _record(findings, "backend_web_routes_imports", path, node)
        elif isinstance(node, ast.ImportFrom):
            if _is_module(node.module, "routes"):
                _record(findings, "flat_routes_imports", path, node)
            if _is_module(node.module, "components"):
                _record(findings, "flat_components_imports", path, node)
            if (not is_web_adapter) and _is_module(node.module, "backend.web.routes"):
                _record(findings, "backend_web_routes_imports", path, node)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr not in {"append", "insert"}:
                continue
            chain = _attribute_chain(node.func.value)
            if chain in (["sys", "path"], ["os", "sys", "path"]):
                _record(findings, "sys_path_mutations", path, node)


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
    regressions = {
        category: (baseline[category], int(current_categories[category]))
        for category in CATEGORIES
        if int(current_categories[category]) > baseline[category]
    }
    if not regressions:
        print("import-boundary-scan-ok")
        return 0

    print("Import boundary debt increased:", file=sys.stderr)
    for category, (old, new) in regressions.items():
        print(f"- {category}: baseline={old}, current={new}", file=sys.stderr)
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
