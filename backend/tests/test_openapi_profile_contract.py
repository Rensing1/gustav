from __future__ import annotations

from pathlib import Path

import yaml


def test_openapi_documents_profile_endpoints() -> None:
    spec = yaml.safe_load(Path("api/openapi.yml").read_text(encoding="utf-8"))

    assert "/api/app/profile" in spec["paths"]
    assert "/api/app/profile/display-name" in spec["paths"]
    assert "/api/app/profile/name" in spec["paths"]
    assert "/auth/password" in spec["paths"]

    profile_schema = spec["components"]["schemas"]["AppProfileView"]
    assert profile_schema["required"] == [
        "user",
        "display_name",
        "email",
        "first_name",
        "last_name",
        "name_locked_until",
        "name_can_edit",
        "password_change_href",
    ]


def test_openapi_documents_cli_token_profile_endpoints() -> None:
    spec = yaml.safe_load(Path("api/openapi.yml").read_text(encoding="utf-8"))

    scheme = spec["components"]["securitySchemes"]["cliTokenAuth"]
    assert scheme == {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "opaque-cli-token",
    }

    for path, method in (
        ("/api/app/profile/cli-tokens", "get"),
        ("/api/app/profile/cli-tokens", "post"),
        ("/api/app/profile/cli-tokens/{token_id}", "delete"),
    ):
        op = spec["paths"][path][method]
        assert op["security"] == [{"bearerAuth": []}]
        assert {"cliTokenAuth": []} not in op["security"]
        assert "CLI bearer tokens are rejected" in " ".join(op["x-security-notes"])


def test_openapi_documents_cli_read_scope_for_units_list() -> None:
    spec = yaml.safe_load(Path("api/openapi.yml").read_text(encoding="utf-8"))

    op = spec["paths"]["/api/teaching/units"]["get"]
    assert {"cookieAuth": []} in op["security"]
    assert {"cliTokenAuth": []} in op["security"]
    assert op["x-required-cli-scopes"] == ["read"]


def test_openapi_documents_cli_scopes_for_units_writes() -> None:
    spec = yaml.safe_load(Path("api/openapi.yml").read_text(encoding="utf-8"))

    expectations = [
        ("/api/teaching/units", "post", ["write"]),
        ("/api/teaching/units/{unit_id}", "patch", ["write"]),
        ("/api/teaching/units/{unit_id}", "delete", ["delete"]),
    ]
    for path, method, scopes in expectations:
        op = spec["paths"][path][method]
        assert {"cookieAuth": []} in op["security"]
        assert {"cliTokenAuth": []} in op["security"]
        assert op["x-required-cli-scopes"] == scopes


def test_openapi_documents_module_content_target() -> None:
    spec = yaml.safe_load(Path("api/openapi.yml").read_text(encoding="utf-8"))

    path = "/api/teaching/units/{unit_id}/modules/{module_id}/content-target"
    op = spec["paths"][path]["get"]
    assert op["operationId"] == "getUnitModuleContentTarget"
    assert {"cookieAuth": []} in op["security"]
    assert {"cliTokenAuth": []} in op["security"]
    assert op["x-required-cli-scopes"] == ["read"]


def test_openapi_documents_cli_scopes_for_authoring_resources() -> None:
    spec = yaml.safe_load(Path("api/openapi.yml").read_text(encoding="utf-8"))

    expectations = [
        ("/api/teaching/units/{unit_id}/phases", "get", ["read"]),
        ("/api/teaching/units/{unit_id}/phases", "post", ["write"]),
        ("/api/teaching/units/{unit_id}/phases/{phase_id}", "patch", ["write"]),
        ("/api/teaching/units/{unit_id}/phases/{phase_id}", "delete", ["delete"]),
        ("/api/teaching/units/{unit_id}/phases/reorder", "post", ["write"]),
        ("/api/teaching/units/{unit_id}/modules/graph", "get", ["read"]),
        ("/api/teaching/units/{unit_id}/modules", "post", ["write"]),
        ("/api/teaching/units/{unit_id}/modules/{module_id}", "patch", ["write"]),
        ("/api/teaching/units/{unit_id}/modules/{module_id}", "delete", ["delete"]),
        ("/api/teaching/units/{unit_id}/phases/{phase_id}/modules/reorder", "post", ["write"]),
        ("/api/teaching/units/{unit_id}/modules/edges", "post", ["write"]),
        ("/api/teaching/units/{unit_id}/modules/{from_module_id}/edges/{to_module_id}", "delete", ["delete"]),
        ("/api/teaching/units/{unit_id}/sections", "get", ["read"]),
        ("/api/teaching/units/{unit_id}/sections", "post", ["write"]),
        ("/api/teaching/units/{unit_id}/sections/{section_id}", "patch", ["write"]),
        ("/api/teaching/units/{unit_id}/sections/{section_id}", "delete", ["delete"]),
        ("/api/teaching/units/{unit_id}/sections/reorder", "post", ["write"]),
        ("/api/teaching/units/{unit_id}/sections/{section_id}/tasks", "get", ["read"]),
        ("/api/teaching/units/{unit_id}/sections/{section_id}/tasks", "post", ["write"]),
        ("/api/teaching/units/{unit_id}/sections/{section_id}/tasks/{task_id}", "patch", ["write"]),
        ("/api/teaching/units/{unit_id}/sections/{section_id}/tasks/{task_id}", "delete", ["delete"]),
        ("/api/teaching/units/{unit_id}/sections/{section_id}/tasks/reorder", "post", ["write"]),
        ("/api/teaching/units/{unit_id}/sections/{section_id}/materials", "get", ["read"]),
        ("/api/teaching/units/{unit_id}/sections/{section_id}/materials", "post", ["write"]),
        ("/api/teaching/units/{unit_id}/sections/{section_id}/materials/{material_id}", "patch", ["write"]),
        ("/api/teaching/units/{unit_id}/sections/{section_id}/materials/{material_id}", "delete", ["delete"]),
        ("/api/teaching/units/{unit_id}/sections/{section_id}/materials/reorder", "post", ["write"]),
    ]
    for path, method, scopes in expectations:
        op = spec["paths"][path][method]
        assert {"cookieAuth": []} in op["security"], f"{method.upper()} {path}"
        assert {"cliTokenAuth": []} in op["security"], f"{method.upper()} {path}"
        assert op["x-required-cli-scopes"] == scopes, f"{method.upper()} {path}"
