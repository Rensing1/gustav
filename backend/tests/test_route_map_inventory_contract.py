"""Route map inventory contracts.

Why:
    PR 13 needs a route-by-route map with surface, role, data access, response
    model, test coverage signal, risk, legacy status, decision, and target
    layer. The map should be generated from the runtime/OpenAPI surface so it
    stays reviewable during legacy strangulation.
"""

from __future__ import annotations

from pathlib import Path
import re
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
MAKEFILE = REPO_ROOT / "Makefile"
ROUTE_MAP = REPO_ROOT / "docs" / "harness" / "ROUTE_MAP.md"
TOOL = REPO_ROOT / "backend" / "tools" / "route_map_inventory.py"


def _target_body(target: str) -> str:
    text = MAKEFILE.read_text(encoding="utf-8")
    match = re.search(
        rf"(?ms)^\.PHONY: {re.escape(target)}\n{re.escape(target)}:\n(?P<body>.*?)(?=^\.PHONY: |\Z)",
        text,
    )
    assert match is not None, f"Makefile target {target!r} not found"
    return match.group("body")


def test_makefile_exposes_route_map_gate() -> None:
    body = _target_body("test-route-map")

    assert "python -m backend.tools.route_map_inventory" in body
    assert "--check docs/harness/ROUTE_MAP.md" in body


def test_verify_runs_route_map_gate() -> None:
    body = _target_body("verify")

    assert "$(MAKE) test-route-map" in body


def test_route_map_document_has_required_inventory_columns() -> None:
    assert TOOL.exists(), "Missing route map inventory tool"
    text = ROUTE_MAP.read_text(encoding="utf-8")

    for column in (
        "Route/Endpoint",
        "Surface",
        "Role",
        "Data Access",
        "Response Model",
        "Existing Tests",
        "Risk",
        "Legacy Status",
        "Decision",
        "Target Layer",
    ):
        assert column in text

    for required_route in (
        "GET /api/learning/courses",
        "POST /api/teaching/courses",
        "GET /h5p/healthz",
        "GET /auth/login",
        "GET /api/live/views/courses/{course_id}/units/{unit_id}/dashboard",
    ):
        assert required_route in text


def test_route_map_no_longer_lists_removed_deep_teaching_live_routes() -> None:
    text = ROUTE_MAP.read_text(encoding="utf-8")

    for removed_route in (
        "GET /teaching/courses/{course_id}/students/{student_sub}/live",
        "GET /teaching/courses/{course_id}/units/{unit_id}/live",
        "GET /teaching/courses/{course_id}/units/{unit_id}/live/detail",
        "GET /teaching/courses/{course_id}/units/{unit_id}/live/matrix",
        "GET /teaching/courses/{course_id}/units/{unit_id}/live/matrix/delta",
        "GET /teaching/courses/{course_id}/units/{unit_id}/live/sections-panel",
        "POST /teaching/courses/{course_id}/modules/{module_id}/sections/{section_id}/visibility",
    ):
        assert removed_route not in text


def test_route_map_is_synchronized_with_generator() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "backend.tools.route_map_inventory",
            "--check",
            "docs/harness/ROUTE_MAP.md",
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "route-map-inventory-ok" in result.stdout
    assert result.stderr == ""
