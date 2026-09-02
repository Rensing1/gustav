from __future__ import annotations

from pathlib import Path

import yaml


def test_openapi_documents_diagnostics_learner_profile_view() -> None:
    spec = yaml.safe_load(Path("api/openapi.yml").read_text(encoding="utf-8"))

    path = "/api/diagnostics/views/learners/{student_sub}/profile"
    assert path in spec["paths"]

    schema = spec["components"]["schemas"]["DiagnosticsLearnerProfileView"]
    assert schema["required"] == ["user", "learner", "summary", "courses"]

    operation = spec["paths"][path]["get"]
    assert {"cliTokenAuth": []} in operation["security"]
    assert operation["x-required-cli-scopes"] == ["read"]
    parameters = {item["name"]: item for item in operation["parameters"]}
    assert parameters["limit"]["schema"]["maximum"] == 50
    assert parameters["offset"]["schema"]["minimum"] == 0
    assert "slash-containing" in parameters["student_sub"]["description"]
    assert "non-integer" in operation["responses"]["400"]["description"]
    assert operation["responses"]["400"]["headers"]["Cache-Control"]["schema"] == {
        "type": "string"
    }
    assert "empty `courses` array" in operation["responses"]["200"]["description"]
