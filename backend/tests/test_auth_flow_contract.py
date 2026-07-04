"""Contracts for web auth-flow classification helpers."""

from __future__ import annotations

from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MAIN_SOURCE = PROJECT_ROOT / "backend" / "web" / "main.py"


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("/api/app/session-bootstrap", True),
        ("/api/app/session-sync", True),
        ("/api/app/profile", True),
        ("/api/learning/views/course-1", True),
        ("/api/teaching/views/course-1", True),
        ("/api/diagnostics/views/course-1", True),
        ("/api/live/views/course-1", True),
        ("/api/teaching/courses", False),
        ("/api/me", False),
    ],
)
def test_requires_bff_bearer_auth_classifies_new_read_model_surface(path: str, expected: bool) -> None:
    from backend.web.auth_flow import requires_bff_bearer_auth

    assert requires_bff_bearer_auth(path) is expected


@pytest.mark.parametrize(
    ("auth_source", "expected"),
    [
        ("missing_bearer", "session_bootstrap_missing_bearer"),
        ("bearer", "session_bootstrap_invalid_bearer"),
        ("session", "bff_session_missing"),
    ],
)
def test_auth_failure_reason_is_low_cardinality(auth_source: str, expected: str) -> None:
    from backend.web.auth_flow import auth_failure_reason

    assert auth_failure_reason(auth_source) == expected


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("/api/app/session-bootstrap", "api.app"),
        ("/api/learning/views/course-1", "api.learning"),
        ("/api/teaching/courses/course-1/students/student@example.com", "api.teaching"),
        ("/api/diagnostics/views/course-1", "api.diagnostics"),
        ("/api/other/value", "api.other"),
        ("/internal/health/openai", "internal"),
        ("/backend-internal/session", "backend_internal"),
        ("/learning", "other"),
    ],
)
def test_auth_failure_path_class_never_exposes_dynamic_identifiers(path: str, expected: str) -> None:
    from backend.web.auth_flow import auth_failure_path_class

    assert auth_failure_path_class(path) == expected


def test_main_delegates_auth_flow_classification_to_dedicated_module() -> None:
    source = MAIN_SOURCE.read_text(encoding="utf-8")
    auth_middleware_source = (PROJECT_ROOT / "backend/web/auth_middleware.py").read_text(encoding="utf-8")

    assert "requires_bff_bearer_auth(" in auth_middleware_source
    assert "auth_failure_reason(" in auth_middleware_source
    assert "auth_failure_path_class(" in auth_middleware_source
    assert "def _requires_bff_bearer_auth" not in source
    assert "def _auth_failure_reason" not in source
    assert "def _auth_failure_path_class" not in source
