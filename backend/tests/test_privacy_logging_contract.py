"""
Privacy/logging contract tests (source-level).

Why:
    - Session IDs are bearer tokens and must not end up in CI/test logs.
    - `print()` statements in request code paths are hard to filter and can
      leak sensitive context to stdout.
    - Logs must not emit complete or truncated OIDC subject identifiers.

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


def _contains_subject_identifier(node: ast.AST) -> bool:
    subject_names = {"sub", "student_sub", "teacher_sub", "owner_sub", "author_sub"}
    return any(isinstance(child, ast.Name) and child.id in subject_names for child in ast.walk(node))


def _contains_raw_exception(node: ast.AST) -> bool:
    """Detect exception values that logging would stringify with sensitive details."""

    exception_names = {"exc", "legacy_exc", "err", "error"}
    if (
        isinstance(node, ast.Attribute)
        and node.attr == "__name__"
        and isinstance(node.value, ast.Attribute)
        and node.value.attr == "__class__"
    ):
        return False
    return any(
        isinstance(child, ast.Name) and child.id in exception_names
        for child in ast.walk(node)
    )


def test_teaching_routes_do_not_log_subject_identifiers() -> None:
    route_paths = sorted((_repo_root() / "backend" / "web" / "routes").glob("teaching*.py"))

    offenders: list[str] = []
    for path in route_paths:
        src = path.read_text(encoding="utf-8")
        assert "print(" not in src

        tree = ast.parse(src, filename=str(path))
        for call in _logging_calls(tree):
            if _contains_subject_identifier(call):
                offenders.append(f"{path.relative_to(_repo_root())}:{call.lineno}")

    assert offenders == []


def test_teaching_routes_do_not_log_raw_exception_values() -> None:
    """Driver messages can contain PII, hosts, SQL fragments or credentials."""

    offenders: list[str] = []
    route_paths = sorted((_repo_root() / "backend" / "web" / "routes").glob("teaching*.py"))
    for path in route_paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for call in _logging_calls(tree):
            if any(_contains_raw_exception(argument) for argument in call.args[1:]):
                offenders.append(f"{path.relative_to(_repo_root())}:{call.lineno}")

    assert offenders == []


def test_auth_middleware_does_not_log_subject_identifiers() -> None:
    """Even truncated OIDC subjects remain stable, correlatable identifiers."""

    path = _repo_root() / "backend" / "web" / "auth_middleware.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    offenders = [
        call.lineno
        for call in _logging_calls(tree)
        if any(isinstance(child, ast.Name) and child.id == "sub" for child in ast.walk(call))
    ]

    assert offenders == []
