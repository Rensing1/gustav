"""OpenAPI contract tests for Teaching Tasks endpoints.

Why:
    Ensure the OpenAPI spec already documents the planned tasks CRUD/reorder
    endpoints before we implement them. This keeps us aligned with the
    Contract-First requirement and prevents accidental omissions (e.g., missing
    authorOnly permissions or wrong response codes).
"""

from __future__ import annotations

import yaml


def load_spec() -> dict:
    with open("api/openapi.yml", "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def test_tasks_paths_and_permissions_defined():
    spec = load_spec()
    paths = spec.get("paths", {})

    list_path = "/api/teaching/units/{unit_id}/sections/{section_id}/tasks"
    detail_path = f"{list_path}/{{task_id}}"
    reorder_path = f"{list_path}/reorder"

    assert list_path in paths, "tasks collection path missing from OpenAPI"
    assert detail_path in paths, "task detail path missing from OpenAPI"
    assert reorder_path in paths, "tasks reorder path missing from OpenAPI"

    list_ops = paths[list_path]
    assert "get" in list_ops, "GET /tasks must be documented"
    assert "post" in list_ops, "POST /tasks must be documented"

    for verb in ("get", "post"):
        op = list_ops[verb]
        assert op.get("security") == [{"cookieAuth": []}], f"{verb.upper()} /tasks must require cookieAuth"
        perms = op.get("x-permissions") or {}
        assert perms.get("requiredRole") == "teacher", f"{verb.upper()} /tasks must be teacher-only"
        assert perms.get("authorOnly") is True, f"{verb.upper()} /tasks must enforce authorOnly"

    post_op = list_ops["post"]
    request_ref = post_op.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema", {})
    assert request_ref.get("$ref") == "#/components/schemas/TaskCreate", "POST /tasks must reference TaskCreate"
    responses = post_op.get("responses", {})
    assert "201" in responses, "POST /tasks must return 201"
    post_schema = responses["201"].get("content", {}).get("application/json", {}).get("schema", {})
    assert post_schema.get("$ref") == "#/components/schemas/Task", "POST /tasks 201 must return Task schema"

    get_op = list_ops["get"]
    get_schema = get_op.get("responses", {}).get("200", {}).get("content", {}).get("application/json", {}).get("schema", {})
    assert get_schema.get("type") == "array", "GET /tasks 200 must return array"
    items_ref = get_schema.get("items", {}).get("$ref")
    assert items_ref == "#/components/schemas/Task", "GET /tasks items must be Task"

    detail_ops = paths[detail_path]
    assert "patch" in detail_ops, "PATCH /tasks/{task_id} must be documented"
    assert "delete" in detail_ops, "DELETE /tasks/{task_id} must be documented"

    patch_op = detail_ops["patch"]
    assert patch_op.get("security") == [{"cookieAuth": []}], "PATCH /tasks/{task_id} must require cookieAuth"
    perms = patch_op.get("x-permissions") or {}
    assert perms.get("requiredRole") == "teacher", "PATCH /tasks/{task_id} must be teacher-only"
    assert perms.get("authorOnly") is True, "PATCH /tasks/{task_id} must enforce authorOnly"
    patch_body_ref = patch_op.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema", {}).get("$ref")
    assert patch_body_ref == "#/components/schemas/TaskUpdate", "PATCH /tasks/{task_id} must reference TaskUpdate"
    patch_resp_ref = patch_op.get("responses", {}).get("200", {}).get("content", {}).get("application/json", {}).get("schema", {}).get("$ref")
    assert patch_resp_ref == "#/components/schemas/Task", "PATCH /tasks/{task_id} 200 must return Task"

    delete_op = detail_ops["delete"]
    assert delete_op.get("security") == [{"cookieAuth": []}], "DELETE /tasks/{task_id} must require cookieAuth"
    perms = delete_op.get("x-permissions") or {}
    assert perms.get("requiredRole") == "teacher", "DELETE /tasks/{task_id} must be teacher-only"
    assert perms.get("authorOnly") is True, "DELETE /tasks/{task_id} must enforce authorOnly"
    assert "204" in (delete_op.get("responses") or {}), "DELETE /tasks/{task_id} must declare 204 response"

    reorder_op = paths[reorder_path].get("post")
    assert reorder_op is not None, "POST /tasks/reorder must be documented"
    assert reorder_op.get("security") == [{"cookieAuth": []}], "POST /tasks/reorder must require cookieAuth"
    perms = reorder_op.get("x-permissions") or {}
    assert perms.get("requiredRole") == "teacher", "POST /tasks/reorder must be teacher-only"
    assert perms.get("authorOnly") is True, "POST /tasks/reorder must enforce authorOnly"
    reorder_body_ref = reorder_op.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema", {}).get("$ref")
    assert reorder_body_ref == "#/components/schemas/TaskReorder", "POST /tasks/reorder must reference TaskReorder"
    reorder_resp_ref = reorder_op.get("responses", {}).get("200", {}).get("content", {}).get("application/json", {}).get("schema", {}).get("items", {}).get("$ref")
    assert reorder_resp_ref == "#/components/schemas/Task", "POST /tasks/reorder 200 items must be Task"
