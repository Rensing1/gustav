from __future__ import annotations

from pathlib import Path

import yaml


def test_openapi_documents_bearer_auth_for_bff_endpoints() -> None:
    spec = yaml.safe_load(Path("api/openapi.yml").read_text(encoding="utf-8"))

    bearer_scheme = spec["components"]["securitySchemes"]["bearerAuth"]
    assert bearer_scheme["type"] == "http"
    assert bearer_scheme["scheme"] == "bearer"
    assert bearer_scheme["bearerFormat"] == "JWT"

    security = spec["paths"]["/api/me"]["get"]["security"]
    assert {"cookieAuth": []} in security
    assert {"bearerAuth": []} in security

    for path, verb in (
        ("/api/app/session-bootstrap", "get"),
        ("/api/learning/views/learner-home", "get"),
        ("/api/teaching/views/teacher-home", "get"),
        ("/api/teaching/views/courses/{course_id}/context", "get"),
        ("/api/diagnostics/views/courses/{course_id}/matrix", "get"),
    ):
        security = spec["paths"][path][verb]["security"]
        assert security == [{"bearerAuth": []}]
