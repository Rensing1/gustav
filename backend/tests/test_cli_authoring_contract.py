"""Contracts for CLI authoring capability routing."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MAIN_SOURCE = PROJECT_ROOT / "backend" / "web" / "main.py"


@pytest.mark.parametrize(
    ("template", "path", "expected"),
    [
        ("/api/teaching/units/{unit_id}", "/api/teaching/units/unit-1", True),
        ("/api/teaching/units/{unit_id}", "/api/teaching/units", False),
        ("/api/teaching/units/{unit_id}", "/api/teaching/units/unit-1/sections", False),
        ("/api/teaching/units/{unit_id}", "/api/teaching/units/", False),
        ("/api/teaching/units", "/api/teaching/units", True),
    ],
)
def test_path_matches_template_requires_exact_shape(template: str, path: str, expected: bool) -> None:
    from backend.web.cli_authoring import path_matches_template

    assert path_matches_template(template, path) is expected


@pytest.mark.parametrize(
    ("method", "path", "expected_scope"),
    [
        ("GET", "/api/me", "read"),
        ("GET", "/api/teaching/units", "read"),
        ("post", "/api/teaching/units", "write"),
        ("DELETE", "/api/teaching/units/unit-1", "delete"),
        (
            "POST",
            "/api/teaching/units/unit-1/sections/section-1/tasks/task-1/h5p/import",
            "write",
        ),
        (
            "GET",
            "/api/teaching/units/unit-1/materials/material-1/simulation",
            "read",
        ),
        ("GET", "/api/teaching/views/teacher-home", None),
    ],
)
def test_cli_capability_for_request_resolves_required_scope(
    method: str,
    path: str,
    expected_scope: str | None,
) -> None:
    from backend.web.cli_authoring import cli_capability_for_request

    capability = cli_capability_for_request(method, path)

    assert (capability.required_scope if capability else None) == expected_scope


def test_cli_authoring_capability_table_matches_openapi_cli_surface() -> None:
    from backend.web.cli_capabilities import CLI_CAPABILITIES

    spec = yaml.safe_load((PROJECT_ROOT / "api/openapi.yml").read_text(encoding="utf-8"))
    documented = set()
    for path, methods in spec["paths"].items():
        for method, op in methods.items():
            if not isinstance(op, dict):
                continue
            if {"cliTokenAuth": []} not in op.get("security", []):
                continue
            documented.add((method.upper(), path, tuple(op["x-required-cli-scopes"])))

    runtime = {
        (capability.method, capability.path_template, (capability.required_scope,))
        for capability in CLI_CAPABILITIES
    }

    assert runtime == documented


def test_main_delegates_cli_authoring_capabilities_to_dedicated_module() -> None:
    source = MAIN_SOURCE.read_text(encoding="utf-8")
    auth_middleware_source = (PROJECT_ROOT / "backend/web/auth_middleware.py").read_text(encoding="utf-8")

    assert "from backend.web.cli_capabilities import cli_capability_for_request" in auth_middleware_source
    assert "class CLIAuthoringCapability" not in source
    assert "CLI_AUTHORING_CAPABILITIES" not in source
    assert "def _path_matches_template" not in source
    assert "def _cli_capability_for_request" not in source


def test_registered_course_cli_operations_are_documented_and_authorized() -> None:
    from backend.tools.gustav_cli.operations import COURSE_AUTHORING_OPERATIONS
    from backend.web.cli_capabilities import CLI_CAPABILITIES

    spec = yaml.safe_load((PROJECT_ROOT / "api/openapi.yml").read_text(encoding="utf-8"))
    documented = {
        (method.upper(), path)
        for path, methods in spec["paths"].items()
        for method, operation in methods.items()
        if isinstance(operation, dict) and {"cliTokenAuth": []} in operation.get("security", [])
    }
    authorized = {
        (capability.method, capability.path_template)
        for capability in CLI_CAPABILITIES
    }
    registered = {
        (operation.method, operation.path_template)
        for operation in COURSE_AUTHORING_OPERATIONS.values()
    }

    assert registered <= documented
    assert registered <= authorized


def test_registered_diagnostics_cli_operations_are_documented_and_authorized() -> None:
    from backend.tools.gustav_cli.operations import DIAGNOSTICS_OPERATIONS
    from backend.web.cli_capabilities import CLI_CAPABILITIES

    spec = yaml.safe_load((PROJECT_ROOT / "api/openapi.yml").read_text(encoding="utf-8"))
    documented = {
        (method.upper(), path)
        for path, methods in spec["paths"].items()
        for method, operation in methods.items()
        if isinstance(operation, dict) and {"cliTokenAuth": []} in operation.get("security", [])
    }
    authorized = {
        (capability.method, capability.path_template)
        for capability in CLI_CAPABILITIES
    }
    registered = {
        (operation.method, operation.path_template)
        for operation in DIAGNOSTICS_OPERATIONS.values()
    }

    assert registered <= documented
    assert registered <= authorized
