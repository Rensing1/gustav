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


def test_conftest_delegates_import_path_bootstrap_to_central_helper() -> None:
    text = CONFTEST.read_text(encoding="utf-8")

    assert "from backend.tests.import_paths import configure_test_import_paths" in text
    assert "configure_test_import_paths()" in text
    assert _sys_path_mutations(CONFTEST) == []


def test_central_import_path_helper_documents_legacy_compatibility_paths() -> None:
    assert IMPORT_PATHS.exists(), "Missing central pytest import-path helper"
    text = IMPORT_PATHS.read_text(encoding="utf-8")

    assert "LEGACY_TEST_IMPORT_PATHS" in text
    assert "backend/web" in text
    assert "PR 9" in text
    assert "configure_test_import_paths" in text


def test_import_boundary_baseline_blocks_new_scattered_test_path_crutches() -> None:
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))

    assert isinstance(baseline["categories"]["sys_path_mutations"], int)
    assert baseline["categories"]["sys_path_mutations"] >= 1
