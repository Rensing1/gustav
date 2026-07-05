"""Contracts for pytest import-path bootstrap.

Why:
    PR 9 centralizes pytest import-path setup. Scattered local path mutations
    made tests see a different package layout from Docker and production.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
CONFTEST = REPO_ROOT / "backend" / "tests" / "conftest.py"
IMPORT_PATHS = REPO_ROOT / "backend" / "tests" / "import_paths.py"
BASELINE = REPO_ROOT / "docs" / "harness" / "IMPORT_BOUNDARY_BASELINE.json"


def _sys_path_mutations(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    findings: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in {"append", "insert"}:
            continue
        value = node.func.value
        if isinstance(value, ast.Attribute) and value.attr == "path" and isinstance(value.value, ast.Name):
            if value.value.id in {"sys", "os.sys"}:
                findings.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno}")
        if (
            isinstance(value, ast.Attribute)
            and value.attr == "path"
            and isinstance(value.value, ast.Attribute)
            and value.value.attr == "sys"
            and isinstance(value.value.value, ast.Name)
            and value.value.value.id == "os"
        ):
            findings.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno}")
    return findings


def test_conftest_does_not_mutate_sys_path() -> None:
    text = CONFTEST.read_text(encoding="utf-8")

    assert _sys_path_mutations(CONFTEST) == []


def test_central_import_path_helper_no_longer_mutates_sys_path() -> None:
    assert IMPORT_PATHS.exists(), "Missing central pytest import-path helper"
    text = IMPORT_PATHS.read_text(encoding="utf-8")

    assert "sys.path.insert" not in text
    assert "sys.path.append" not in text


def test_import_boundary_baseline_has_no_test_path_crutches() -> None:
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))

    assert isinstance(baseline["categories"]["sys_path_mutations"], int)
    assert baseline["categories"]["sys_path_mutations"] == 0


def test_tests_use_backend_namespace_for_app_and_bounded_contexts() -> None:
    """Tests should use the same package namespace as Docker and production."""

    forbidden_roots = {"identity_access", "main", "teaching"}
    offenders: list[str] = []
    for path in sorted((REPO_ROOT / "backend" / "tests").rglob("*.py")):
        if path == IMPORT_PATHS:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".", 1)[0] in forbidden_roots:
                        offenders.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                if node.module.split(".", 1)[0] in forbidden_roots:
                    offenders.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno}: from {node.module} import ...")

    assert offenders == []


def test_tests_do_not_manage_flat_main_module_alias() -> None:
    """Test helpers should not keep the removed `main` alias alive indirectly."""

    offenders: list[str] = []
    for path in sorted((REPO_ROOT / "backend" / "tests").rglob("*.py")):
        if path.parent == Path(__file__).resolve().parent:
            continue
        text = path.read_text(encoding="utf-8")
        if 'sys.modules, "main"' in text or '"main", "backend.web.main"' in text:
            offenders.append(str(path.relative_to(REPO_ROOT)))

    assert offenders == []
