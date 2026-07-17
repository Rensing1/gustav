"""Architecture boundary gate contracts.

Why:
    PR 12 turns selected Clean Architecture rules into executable checks:
    use cases/services must not import FastAPI, and direct DB/client access from
    web adapters must be inventoried so it cannot grow unnoticed.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import sys

import pytest

from backend.tools import architecture_boundary_scan


REPO_ROOT = Path(__file__).resolve().parents[2]
MAKEFILE = REPO_ROOT / "Makefile"
SCAN_SCRIPT = REPO_ROOT / "backend" / "tools" / "architecture_boundary_scan.py"
BASELINE = REPO_ROOT / "docs" / "harness" / "ARCHITECTURE_BOUNDARY_BASELINE.json"
RULES = REPO_ROOT / "docs" / "harness" / "ARCHITECTURE_RULES.md"


def _target_body(target: str) -> str:
    text = MAKEFILE.read_text(encoding="utf-8")
    match = re.search(
        rf"(?ms)^\.PHONY: {re.escape(target)}\n{re.escape(target)}:\n(?P<body>.*?)(?=^\.PHONY: |\Z)",
        text,
    )
    assert match is not None, f"Makefile target {target!r} not found"
    return match.group("body")


def test_makefile_exposes_architecture_boundary_gate() -> None:
    body = _target_body("test-architecture-boundaries")

    assert "python -m backend.tools.architecture_boundary_scan" in body
    assert "--baseline docs/harness/ARCHITECTURE_BOUNDARY_BASELINE.json" in body


def test_verify_runs_architecture_boundary_gate() -> None:
    body = _target_body("verify")

    assert "$(MAKE) test-architecture-boundaries" in body


def test_architecture_scanner_and_baseline_cover_required_categories() -> None:
    assert SCAN_SCRIPT.exists(), "Missing architecture boundary scanner"
    assert BASELINE.exists(), "Missing architecture boundary baseline"

    script = SCAN_SCRIPT.read_text(encoding="utf-8")
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    categories = baseline.get("categories", {})

    for category in (
        "usecase_fastapi_imports",
        "service_fastapi_imports",
        "web_direct_db_connects",
        "web_direct_supabase_client_creates",
    ):
        assert category in script
        assert category in categories
        assert isinstance(categories[category], int)


def test_architecture_boundary_baseline_has_no_web_adapter_exceptions() -> None:
    """Approved boundary helpers should not leave accepted debt in the baseline."""

    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    categories = baseline.get("categories", {})

    assert categories["web_direct_db_connects"] == 0
    assert categories["web_direct_supabase_client_creates"] == 0


def test_architecture_scan_excludes_approved_boundary_infrastructure() -> None:
    """DB/storage boundary modules are infrastructure, not route-level debt."""

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "backend.tools.architecture_boundary_scan",
            "--json",
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)

    assert payload["categories"]["web_direct_db_connects"] == 0
    assert payload["categories"]["web_direct_supabase_client_creates"] == 0
    assert "backend/web/db_cursor.py" not in "\n".join(payload["examples"]["web_direct_db_connects"])
    assert "backend/web/storage_wiring.py" not in "\n".join(payload["examples"]["web_direct_supabase_client_creates"])


def test_architecture_boundary_scan_matches_current_baseline() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "backend.tools.architecture_boundary_scan",
            "--baseline",
            "docs/harness/ARCHITECTURE_BOUNDARY_BASELINE.json",
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "architecture-boundary-scan-ok" in result.stdout


@pytest.mark.parametrize(
    ("source", "category"),
    (
        ("import psycopg as pg\npg.connect('dsn')\n", "web_direct_db_connects"),
        ("from psycopg import connect as db_connect\ndb_connect('dsn')\n", "web_direct_db_connects"),
        ("import supabase as sb\nsb.create_client('url', 'key')\n", "web_direct_supabase_client_creates"),
        (
            "from supabase import create_client as make_client\nmake_client('url', 'key')\n",
            "web_direct_supabase_client_creates",
        ),
    ),
)
def test_architecture_scan_resolves_forbidden_import_aliases(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source: str,
    category: str,
) -> None:
    web_file = tmp_path / "backend/web/routes/example.py"
    web_file.parent.mkdir(parents=True)
    web_file.write_text(source, encoding="utf-8")
    monkeypatch.setattr(architecture_boundary_scan, "_repo_root", lambda: tmp_path)
    findings = {name: [] for name in architecture_boundary_scan.CATEGORIES}

    architecture_boundary_scan._scan_file(web_file, findings)

    assert findings[category] == ["backend/web/routes/example.py:2"]


def test_architecture_scan_ignores_unrelated_create_client_symbol(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    web_file = tmp_path / "backend/web/routes/example.py"
    web_file.parent.mkdir(parents=True)
    web_file.write_text("from example_factory import create_client\ncreate_client()\n", encoding="utf-8")
    monkeypatch.setattr(architecture_boundary_scan, "_repo_root", lambda: tmp_path)
    findings = {name: [] for name in architecture_boundary_scan.CATEGORIES}

    architecture_boundary_scan._scan_file(web_file, findings)

    assert findings["web_direct_supabase_client_creates"] == []


def test_architecture_rules_document_executable_boundaries() -> None:
    text = RULES.read_text(encoding="utf-8")

    for phrase in (
        "make test-architecture-boundaries",
        "Use Cases und Services dürfen FastAPI nicht importieren",
        "Direkte DB-Zugriffe aus Web-Adaptern",
        "ARCHITECTURE_BOUNDARY_BASELINE.json",
        "Security Guards",
        "Serialisierung",
    ):
        assert phrase in text
