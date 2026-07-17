"""OpenAPI contract for Teaching repository unavailability."""

from __future__ import annotations

from pathlib import Path

import yaml


OPENAPI = Path(__file__).resolve().parents[2] / "api" / "openapi.yml"
HTTP_METHODS = {"get", "post", "put", "patch", "delete"}
REPOSITORY_PREFIXES = ("/api/teaching/", "/api/live/", "/api/diagnostics/")


def _contract() -> dict:
    return yaml.safe_load(OPENAPI.read_text(encoding="utf-8"))


def test_health_contract_documents_database_readiness() -> None:
    contract = _contract()
    operation = contract["paths"]["/health"]["get"]

    assert set(operation["responses"]) >= {"200", "503"}
    for status in ("200", "503"):
        schema = operation["responses"][status]["content"]["application/json"]["schema"]
        assert schema == {"$ref": "#/components/schemas/HealthStatus"}


def test_all_teaching_repository_operations_document_503() -> None:
    """Every repository-dependent operation must describe fail-closed startup."""

    missing: list[str] = []
    for path, path_item in _contract()["paths"].items():
        if not path.startswith(REPOSITORY_PREFIXES):
            continue
        for method, operation in path_item.items():
            if method not in HTTP_METHODS:
                continue
            if "503" not in operation.get("responses", {}):
                missing.append(f"{method.upper()} {path}")

    assert not missing, "Missing Teaching repository 503 responses:\n" + "\n".join(missing)
