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
        ("/api/app/profile", "get"),
        ("/api/app/profile/display-name", "patch"),
        ("/api/app/profile/name", "patch"),
        ("/api/learning/views/learner-home", "get"),
        ("/api/learning/views/concern-box", "get"),
        ("/api/learning/concern-box/entries", "post"),
        ("/api/teaching/views/teacher-home", "get"),
        ("/api/teaching/views/concern-box", "get"),
        ("/api/teaching/concern-box/entries/{entry_id}/archive", "post"),
        ("/api/teaching/concern-box/entries/{entry_id}/restore", "post"),
        ("/api/teaching/views/courses/{course_id}/context", "get"),
        ("/api/diagnostics/views/courses/{course_id}/matrix", "get"),
        ("/api/diagnostics/views/learners/{student_sub}/profile", "get"),
        ("/api/live/views/courses/{course_id}/units", "get"),
        ("/api/live/views/courses/{course_id}/units/{unit_id}/matrix", "get"),
        ("/api/live/views/courses/{course_id}/units/{unit_id}/detail-sheet", "get"),
        ("/api/live/views/courses/{course_id}/units/{unit_id}/dashboard", "get"),
    ):
        security = spec["paths"][path][verb]["security"]
        assert security == [{"bearerAuth": []}]
