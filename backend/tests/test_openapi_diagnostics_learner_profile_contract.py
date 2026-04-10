from __future__ import annotations

from pathlib import Path

import yaml


def test_openapi_documents_diagnostics_learner_profile_view() -> None:
    spec = yaml.safe_load(Path("api/openapi.yml").read_text(encoding="utf-8"))

    assert "/api/diagnostics/views/learners/{student_sub}/profile" in spec["paths"]

    schema = spec["components"]["schemas"]["DiagnosticsLearnerProfileView"]
    assert schema["required"] == ["user", "learner", "summary", "courses"]
