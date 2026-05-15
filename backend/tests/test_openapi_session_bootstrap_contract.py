from __future__ import annotations

from pathlib import Path

import yaml


def test_openapi_documents_session_bootstrap() -> None:
    spec = yaml.safe_load(Path("api/openapi.yml").read_text(encoding="utf-8"))

    assert "/api/app/session-bootstrap" in spec["paths"]
    operation = spec["paths"]["/api/app/session-bootstrap"]["get"]
    assert operation["summary"] == "Return shell bootstrap data for the current session"
    assert operation["responses"]["401"]["x-gustav-auth-failure-reason-codes"] == [
        "missing_bearer",
        "invalid_bearer",
        "bff_session_missing",
    ]

    schema = spec["components"]["schemas"]["SessionBootstrap"]
    assert schema["required"] == ["user", "start_target", "spaces"]
    assert schema["properties"]["start_target"]["enum"] == ["/learning", "/teaching"]
    assert schema["properties"]["spaces"]["items"]["type"] == "string"
