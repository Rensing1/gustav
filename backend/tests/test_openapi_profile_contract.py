from __future__ import annotations

import importlib
from pathlib import Path

import yaml

from backend.web.cli_capabilities import CLI_CAPABILITIES

importlib.import_module("backend.web.main")


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
        assert op["x-permissions"] == {"requiredRole": "teacher"}
        assert "403" in op["responses"]
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
        ("/api/teaching/units/{unit_id}/sections/{section_id}/materials/upload-intents", "post", ["write"]),
        ("/api/teaching/units/{unit_id}/sections/{section_id}/materials/finalize", "post", ["write"]),
        ("/api/teaching/units/{unit_id}/sections/{section_id}/materials/{material_id}/download-url", "get", ["read"]),
        ("/api/teaching/units/{unit_id}/modules/{module_id}/materials", "post", ["write"]),
        ("/api/teaching/units/{unit_id}/modules/{module_id}/materials/{material_id}", "patch", ["write"]),
        ("/api/teaching/units/{unit_id}/modules/{module_id}/materials/{material_id}", "delete", ["delete"]),
        ("/api/teaching/units/{unit_id}/modules/{module_id}/materials/reorder", "post", ["write"]),
        ("/api/teaching/units/{unit_id}/modules/{module_id}/materials/upload-intents", "post", ["write"]),
        ("/api/teaching/units/{unit_id}/modules/{module_id}/materials/finalize", "post", ["write"]),
        ("/api/teaching/units/{unit_id}/modules/{module_id}/tasks", "get", ["read"]),
        ("/api/teaching/units/{unit_id}/modules/{module_id}/tasks", "post", ["write"]),
        ("/api/teaching/units/{unit_id}/modules/{module_id}/tasks/{task_id}", "patch", ["write"]),
        ("/api/teaching/units/{unit_id}/modules/{module_id}/tasks/{task_id}", "delete", ["delete"]),
        ("/api/teaching/units/{unit_id}/modules/{module_id}/tasks/reorder", "post", ["write"]),
        ("/api/teaching/units/{unit_id}/sections/{section_id}/tasks/{task_id}/h5p/import", "post", ["write"]),
        ("/api/teaching/units/{unit_id}/sections/{section_id}/tasks/{task_id}/h5p/export", "get", ["read"]),
        ("/api/teaching/units/{unit_id}/sections/{section_id}/tasks/{task_id}/h5p/reset", "post", ["write"]),
        ("/api/teaching/units/{unit_id}/modules/{module_id}/tasks/{task_id}/h5p/import", "post", ["write"]),
        ("/api/teaching/units/{unit_id}/modules/{module_id}/tasks/{task_id}/h5p/reset", "post", ["write"]),
    ]
    for path, method, scopes in expectations:
        op = spec["paths"][path][method]
        assert {"cookieAuth": []} in op["security"], f"{method.upper()} {path}"
        assert {"cliTokenAuth": []} in op["security"], f"{method.upper()} {path}"
        assert op["x-required-cli-scopes"] == scopes, f"{method.upper()} {path}"


def test_h5p_editor_json_endpoints_remain_cookie_only_for_cli_package_workflow() -> None:
    spec = yaml.safe_load(Path("api/openapi.yml").read_text(encoding="utf-8"))

    for path, method in (
        ("/api/teaching/units/{unit_id}/sections/{section_id}/tasks/{task_id}/h5p/editor-model", "get"),
        ("/api/teaching/units/{unit_id}/sections/{section_id}/tasks/{task_id}/h5p/save", "post"),
    ):
        op = spec["paths"][path][method]
        assert op["security"] == [{"cookieAuth": []}]
        assert "x-required-cli-scopes" not in op


def test_openapi_documents_cli_scopes_for_course_authoring() -> None:
    spec = yaml.safe_load(Path("api/openapi.yml").read_text(encoding="utf-8"))

    expectations = [
        ("/api/teaching/courses", "get", ["read"]),
        ("/api/teaching/courses", "post", ["write"]),
        ("/api/teaching/courses/{course_id}", "get", ["read"]),
        ("/api/teaching/courses/{course_id}", "patch", ["write"]),
        ("/api/teaching/courses/{course_id}/archive", "post", ["write"]),
        ("/api/teaching/courses/{course_id}/restore", "post", ["write"]),
        ("/api/teaching/courses/archive-batch", "post", ["write"]),
        ("/api/teaching/courses/{course_id}/deletion-impact", "get", ["read"]),
        ("/api/teaching/courses/{course_id}/deletion-jobs", "post", ["delete"]),
        ("/api/teaching/course-deletion-jobs", "get", ["read"]),
        ("/api/teaching/course-deletion-jobs/{job_id}", "get", ["read"]),
        ("/api/teaching/courses/{course_id}/members", "get", ["read"]),
        ("/api/teaching/courses/{course_id}/members", "post", ["write"]),
        ("/api/teaching/courses/{course_id}/members/{student_sub}", "delete", ["delete"]),
        ("/api/teaching/courses/{course_id}/modules", "get", ["read"]),
        ("/api/teaching/courses/{course_id}/modules", "post", ["write"]),
        ("/api/teaching/courses/{course_id}/modules/reorder", "post", ["write"]),
        ("/api/teaching/courses/{course_id}/modules/{module_id}", "delete", ["delete"]),
        ("/api/teaching/courses/{course_id}/modules/{module_id}/sections", "get", ["read"]),
        ("/api/teaching/courses/{course_id}/modules/{module_id}/sections/{section_id}/visibility", "patch", ["write"]),
        ("/api/users/search", "get", ["read"]),
    ]
    for path, method, scopes in expectations:
        operation = spec["paths"][path][method]
        assert {"cookieAuth": []} in operation["security"], f"{method.upper()} {path}"
        assert {"cliTokenAuth": []} in operation["security"], f"{method.upper()} {path}"
        assert operation["x-required-cli-scopes"] == scopes, f"{method.upper()} {path}"


def test_dialog_preview_and_full_user_list_remain_cookie_only() -> None:
    spec = yaml.safe_load(Path("api/openapi.yml").read_text(encoding="utf-8"))

    for path, method in (
        ("/api/teaching/units/{unit_id}/tasks/{task_id}/dialog-preview", "post"),
        ("/api/users/list", "get"),
    ):
        operation = spec["paths"][path][method]
        assert operation["security"] == [{"cookieAuth": []}]
        assert "x-required-cli-scopes" not in operation


def test_course_update_requires_non_null_subject_and_grade_level() -> None:
    spec = yaml.safe_load(Path("api/openapi.yml").read_text(encoding="utf-8"))
    properties = spec["components"]["schemas"]["CourseUpdate"]["properties"]

    assert properties["subject"].get("nullable") is not True
    assert properties["grade_level"].get("nullable") is not True
    assert properties["term"]["nullable"] is True


def test_openapi_documents_h5p_import_upload_limit_response() -> None:
    spec = yaml.safe_load(Path("api/openapi.yml").read_text(encoding="utf-8"))

    for path in (
        "/api/teaching/units/{unit_id}/sections/{section_id}/tasks/{task_id}/h5p/import",
        "/api/teaching/units/{unit_id}/modules/{module_id}/tasks/{task_id}/h5p/import",
    ):
        responses = spec["paths"][path]["post"]["responses"]
        assert "413" in responses, path
        assert "H5P_MAX_UPLOAD_BYTES" in responses["413"]["description"], path


def test_openapi_documents_module_authoring_repo_unavailable_responses() -> None:
    spec = yaml.safe_load(Path("api/openapi.yml").read_text(encoding="utf-8"))

    expectations = [
        ("/api/teaching/units/{unit_id}/modules/{module_id}/tasks", "get"),
        ("/api/teaching/units/{unit_id}/modules/{module_id}/tasks", "post"),
        ("/api/teaching/units/{unit_id}/modules/{module_id}/tasks/{task_id}", "patch"),
        ("/api/teaching/units/{unit_id}/modules/{module_id}/tasks/{task_id}", "delete"),
        ("/api/teaching/units/{unit_id}/modules/{module_id}/tasks/reorder", "post"),
        ("/api/teaching/units/{unit_id}/modules/{module_id}/tasks/{task_id}/h5p/import", "post"),
        ("/api/teaching/units/{unit_id}/modules/{module_id}/tasks/{task_id}/h5p/reset", "post"),
        ("/api/teaching/units/{unit_id}/modules/{module_id}/materials", "post"),
        ("/api/teaching/units/{unit_id}/modules/{module_id}/materials/{material_id}", "patch"),
        ("/api/teaching/units/{unit_id}/modules/{module_id}/materials/{material_id}", "delete"),
        ("/api/teaching/units/{unit_id}/modules/{module_id}/materials/reorder", "post"),
        ("/api/teaching/units/{unit_id}/modules/{module_id}/materials/upload-intents", "post"),
        ("/api/teaching/units/{unit_id}/modules/{module_id}/materials/finalize", "post"),
    ]
    for path, method in expectations:
        responses = spec["paths"][path][method]["responses"]
        assert "503" in responses, f"{method.upper()} {path}"
        assert "Service unavailable" in responses["503"]["description"], f"{method.upper()} {path}"


def test_openapi_cli_surface_matches_runtime_capability_table() -> None:
    spec = yaml.safe_load(Path("api/openapi.yml").read_text(encoding="utf-8"))
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
