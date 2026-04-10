from __future__ import annotations

from pathlib import Path

import yaml


def test_openapi_documents_concern_box_mutation_uuid_validation() -> None:
    spec = yaml.safe_load(Path("api/openapi.yml").read_text(encoding="utf-8"))

    for path in (
        "/api/teaching/concern-box/entries/{entry_id}/archive",
        "/api/teaching/concern-box/entries/{entry_id}/restore",
    ):
        operation = spec["paths"][path]["post"]
        entry_id = next(param for param in operation["parameters"] if param["name"] == "entry_id")

        assert entry_id["schema"]["type"] == "string"
        assert entry_id["schema"]["format"] == "uuid"

        bad_request = operation["responses"]["400"]
        assert "invalid_entry_id" in bad_request["description"]
        assert bad_request["content"]["application/json"]["schema"]["$ref"] == "#/components/schemas/Error"
