"""
Privacy/logging contract tests (source-level).

Why:
    - Session IDs are bearer tokens and must not end up in CI/test logs.
    - `print()` statements in request code paths are hard to filter and can
      leak sensitive context to stdout.
    - Debug logs should not emit raw student pseudonyms (`student_sub`).

Note:
    These are cheap source-level guardrails; they do not execute the web app.
"""

from __future__ import annotations

import ast
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_ssr_does_not_log_raw_session_id_marker() -> None:
    src = (_repo_root() / "backend" / "web" / "main.py").read_text(encoding="utf-8")
    assert "__SSR_DEBUG_SID__" not in src


def _logging_calls(tree: ast.AST) -> list[ast.Call]:
    calls: list[ast.Call] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute):
            continue
        if func.attr not in {"debug", "info", "warning", "error", "exception", "critical"}:
            continue
        if isinstance(func.value, ast.Name) and func.value.id == "logger":
            calls.append(node)
    return calls


def _contains_raw_student_sub(node: ast.AST) -> bool:
    return any(isinstance(child, ast.Name) and child.id == "student_sub" for child in ast.walk(node))


def test_teaching_routes_do_not_log_raw_student_sub() -> None:
    route_paths = [
        _repo_root() / "backend" / "web" / "routes" / "teaching.py",
        _repo_root() / "backend" / "web" / "routes" / "teaching_live.py",
    ]

    offenders: list[str] = []
    for path in route_paths:
        src = path.read_text(encoding="utf-8")
        assert "print(" not in src

        tree = ast.parse(src, filename=str(path))
        for call in _logging_calls(tree):
            if _contains_raw_student_sub(call):
                offenders.append(f"{path.relative_to(_repo_root())}:{call.lineno}")

    assert offenders == []
