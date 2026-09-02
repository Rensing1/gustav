from __future__ import annotations

from pathlib import Path

import yaml


def test_openapi_documents_diagnostics_course_matrix_view() -> None:
    spec = yaml.safe_load(Path("api/openapi.yml").read_text(encoding="utf-8"))

    path = "/api/diagnostics/views/courses/{course_id}/matrix"
    assert path in spec["paths"]

    schema = spec["components"]["schemas"]["DiagnosticsCourseMatrixView"]
    assert schema["required"] == ["user", "course", "units", "rows"]

    operation = spec["paths"][path]["get"]
    assert {"cliTokenAuth": []} in operation["security"]
    assert operation["x-required-cli-scopes"] == ["read"]
    parameters = {item["name"]: item for item in operation["parameters"]}
    assert parameters["limit"]["schema"] == {
        "type": "integer",
        "minimum": 1,
        "maximum": 50,
        "default": 25,
    }
    assert parameters["offset"]["schema"]["minimum"] == 0
    assert "non-integer" in operation["responses"]["400"]["description"]
    assert operation["responses"]["400"]["headers"]["Cache-Control"]["schema"] == {
        "type": "string"
    }
