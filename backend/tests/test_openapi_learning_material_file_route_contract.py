"""
OpenAPI contract tests for canonical and legacy learner material file routes.

Why:
    The public contract now distinguishes a canonical material-centred route
    from the legacy section-based alias. Both must stay documented while the
    frontend migrates to the canonical path.
"""

from __future__ import annotations

from pathlib import Path

import yaml


def _load_spec() -> dict:
    root = Path(__file__).resolve().parents[2]
    return yaml.safe_load((root / "api" / "openapi.yml").read_text(encoding="utf-8"))


def test_learning_material_schema_describes_canonical_file_url() -> None:
    spec = _load_spec()
    schema = spec["components"]["schemas"]["LearningMaterial"]
    description = str(schema["properties"]["file_url"]["description"])

    assert "canonical material route" in description
    assert "compatibility aliases" in description


def test_openapi_documents_canonical_learning_material_file_route() -> None:
    spec = _load_spec()
    path = "/api/learning/courses/{course_id}/materials/{material_id}/file"

    assert path in spec["paths"], "canonical learner material file route missing"
    op = spec["paths"][path]["get"]
    assert op["operationId"] == "streamLearningMaterialFileCanonical"
    assert "canonical student-facing route" in str(op.get("description") or "")


def test_openapi_documents_legacy_learning_material_file_alias_route() -> None:
    spec = _load_spec()
    path = "/api/learning/courses/{course_id}/sections/{section_id}/materials/{material_id}/file"

    assert path in spec["paths"], "legacy learner material file alias route missing"
    op = spec["paths"][path]["get"]
    assert op["operationId"] == "streamLearningMaterialFile"
    assert "Compatibility alias" in str(op.get("description") or "")


def test_openapi_documents_material_file_route_503_as_lookup_or_storage_unavailable() -> None:
    spec = _load_spec()
    canonical = spec["paths"]["/api/learning/courses/{course_id}/materials/{material_id}/file"]["get"]
    legacy = spec["paths"]["/api/learning/courses/{course_id}/sections/{section_id}/materials/{material_id}/file"]["get"]

    assert canonical["responses"]["503"]["description"] == "Visibility lookup or storage unavailable"
    assert legacy["responses"]["503"]["description"] == "Visibility lookup or storage unavailable"
