"""Teaching Tasks — OpenAPI contract (kind field)

Why:
    We want forward-compatibility for H5P by exposing an optional, read-only
    `kind` field on Task responses. Clients must not send `kind` in create/update
    payloads. This test drives the contract-first change.

Behaviour under test:
    - components.schemas.Task has a `kind` property
      - type: string
      - readOnly: true
      - default: "native" (MVP)
    - TaskCreate and TaskUpdate do NOT define a `kind` property.
"""

from __future__ import annotations

import yaml


def load_spec() -> dict:
    with open("api/openapi.yml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_task_kind_contract_present_and_readonly():
    spec = load_spec()
    schemas = spec.get("components", {}).get("schemas", {})

    assert "Task" in schemas, "Task schema missing in OpenAPI components"
    task = schemas["Task"]
    props = (task.get("properties") or {})
    assert "kind" in props, "Task.kind property must exist for forward-compatibility"
    kind = props["kind"]
    assert kind.get("type") == "string", "Task.kind must be a string"
    assert kind.get("readOnly") is True, "Task.kind must be readOnly in MVP"
    assert kind.get("default") == "native", "Task.kind default should be 'native' in MVP"


def test_task_create_update_do_not_accept_kind():
    spec = load_spec()
    schemas = spec.get("components", {}).get("schemas", {})

    # Create: must not define kind
    assert "TaskCreate" in schemas, "TaskCreate schema missing"
    create_props = (schemas["TaskCreate"].get("properties") or {})
    assert "kind" not in create_props, "TaskCreate must not accept kind"

    # Update: must not define kind
    assert "TaskUpdate" in schemas, "TaskUpdate schema missing"
    update_props = (schemas["TaskUpdate"].get("properties") or {})
    assert "kind" not in update_props, "TaskUpdate must not accept kind"

