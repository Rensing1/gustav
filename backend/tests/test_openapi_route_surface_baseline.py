"""OpenAPI route-surface baseline contracts.

Why:
    PR 10 makes `api/openapi.yml` the checked baseline for runtime `/api/*`
    routes. Non-OpenAPI surfaces must be classified instead of silently
    ignored, so agents can see whether a route is public API, BFF/internal,
    H5P service, auth bridge, health/ops, active legacy UI, or retired UI.
"""

from __future__ import annotations

from pathlib import Path
import re
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
MAKEFILE = REPO_ROOT / "Makefile"
CHECK_SCRIPT = REPO_ROOT / "backend" / "tools" / "openapi_contract_check.py"
API_CONTRACTS = REPO_ROOT / "docs" / "harness" / "API_CONTRACTS.md"
ROUTE_MAP = REPO_ROOT / "docs" / "harness" / "ROUTE_MAP.md"


def _target_body(target: str) -> str:
    text = MAKEFILE.read_text(encoding="utf-8")
    match = re.search(
        rf"(?ms)^\.PHONY: {re.escape(target)}\n{re.escape(target)}:\n(?P<body>.*?)(?=^\.PHONY: |\Z)",
        text,
    )
    assert match is not None, f"Makefile target {target!r} not found"
    return match.group("body")


def test_makefile_exposes_openapi_baseline_gate() -> None:
    body = _target_body("test-api-contract-baseline")

    assert "python -m backend.tools.openapi_contract_check" in body
    assert "--spec api/openapi.yml" in body


def test_verify_runs_openapi_baseline_gate() -> None:
    body = _target_body("verify")

    assert "$(MAKE) test-api-contract-baseline" in body


def test_openapi_contract_check_passes_for_current_runtime_api_surface() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "backend.tools.openapi_contract_check",
            "--spec",
            "api/openapi.yml",
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "openapi-contract-check-ok" in result.stdout


def test_api_contract_docs_define_route_surface_baseline_rules() -> None:
    assert CHECK_SCRIPT.exists(), "Missing OpenAPI contract checker"
    assert ROUTE_MAP.exists(), "Missing route-surface map"
    text = API_CONTRACTS.read_text(encoding="utf-8") + "\n" + ROUTE_MAP.read_text(encoding="utf-8")

    for phrase in (
        "public API",
        "BFF/internal",
        "H5P service",
        "auth bridge",
        "health/ops",
        "active legacy UI",
        "retired legacy UI",
        "undocumented `/api/*`",
        "make test-api-contract-baseline",
    ):
        assert phrase in text
