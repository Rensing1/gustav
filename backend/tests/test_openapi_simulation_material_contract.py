"""Contract tests for interactive simulation materials."""

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]


def _spec() -> dict:
    return yaml.safe_load((ROOT / "api" / "openapi.yml").read_text(encoding="utf-8"))


def test_material_schemas_expose_simulations_without_breaking_file_uploads() -> None:
    spec = _spec()
    schemas = spec["components"]["schemas"]

    assert schemas["Material"]["properties"]["kind"]["enum"] == [
        "markdown",
        "file",
        "simulation",
    ]
    assert schemas["LearningMaterial"]["properties"]["kind"]["enum"] == [
        "markdown",
        "file",
        "simulation",
    ]
    assert schemas["LearningMaterial"]["properties"]["simulation_url"]["nullable"] is True

    intent = schemas["MaterialUploadIntentRequest"]
    assert "kind" not in intent["required"]
    assert intent["properties"]["kind"] == {
        "type": "string",
        "enum": ["file", "simulation"],
        "default": "file",
        "description": "Uploaded material kind. Omitted values remain compatible with file uploads.",
    }
    assert schemas["MaterialFileFinalizeRequest"]["properties"]["body_md"]["type"] == "string"


def test_simulation_player_paths_are_authenticated_html_streams() -> None:
    spec = _spec()

    for path, operation_id, security in (
        (
            "/api/teaching/units/{unit_id}/materials/{material_id}/simulation",
            "streamTeachingMaterialSimulation",
            [{"cookieAuth": []}, {"cliTokenAuth": []}],
        ),
        (
            "/api/learning/courses/{course_id}/materials/{material_id}/simulation",
            "streamLearningMaterialSimulation",
            [{"cookieAuth": []}],
        ),
    ):
        operation = spec["paths"][path]["get"]
        assert operation["operationId"] == operation_id
        assert operation["security"] == security
        response = operation["responses"]["200"]
        assert "text/html" in response["content"]
        assert "Content-Security-Policy" in response["headers"]
        assert "401" in operation["responses"]
        assert "404" in operation["responses"]
