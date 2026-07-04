"""Contracts for pure authentication-claim mapping helpers."""

from __future__ import annotations

from pathlib import Path

from backend.web.auth_claims import (
    display_name_from_claims,
    primary_role,
    roles_from_claims,
    user_context_from_claims,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_primary_role_uses_admin_teacher_student_priority() -> None:
    """The highest privileged allowed role becomes the compatibility role."""

    assert primary_role(["student", "teacher"]) == "teacher"
    assert primary_role(["teacher", "admin"]) == "admin"
    assert primary_role(["unknown"]) == "student"


def test_roles_from_claims_filters_to_allowed_roles_and_defaults_to_student() -> None:
    """External realm roles must not leak into the app role model."""

    assert roles_from_claims({"realm_access": {"roles": ["teacher", "offline_access", "admin"]}}) == [
        "teacher",
        "admin",
    ]
    assert roles_from_claims({"realm_access": {"roles": ["offline_access"]}}) == ["student"]
    assert roles_from_claims({}) == ["student"]


def test_display_name_from_claims_keeps_existing_precedence() -> None:
    """Display names stay stable across bearer, session, and callback mapping."""

    assert (
        display_name_from_claims(
            {
                "gustav_display_name": "Custom Claim Name",
                "name": "Fallback Name",
                "email": "student@example.com",
            }
        )
        == "Custom Claim Name"
    )
    assert display_name_from_claims({"name": "Standard Name", "email": "student@example.com"}) == "Standard Name"
    assert display_name_from_claims({"email": "localpart@example.com"}) == "localpart"
    assert display_name_from_claims({}) == "Benutzer"


def test_user_context_from_claims_builds_runtime_auth_user() -> None:
    """FastAPI auth state receives the same compact user shape everywhere."""

    assert user_context_from_claims(
        {
            "sub": "user-123",
            "email": "learner@example.com",
            "realm_access": {"roles": ["student", "teacher", "external-role"]},
        }
    ) == {
        "sub": "user-123",
        "name": "learner",
        "role": "teacher",
        "roles": ["student", "teacher"],
    }


def test_main_delegates_pure_claim_mapping_to_auth_claims_module() -> None:
    """The app entry module should compose auth flows instead of owning claim mapping."""

    main_source = (REPO_ROOT / "backend/web/main.py").read_text(encoding="utf-8")
    auth_middleware_source = (REPO_ROOT / "backend/web/auth_middleware.py").read_text(encoding="utf-8")
    auth_bridge_source = (REPO_ROOT / "backend/web/auth_bridge.py").read_text(encoding="utf-8")

    for retired_helper in (
        "def _primary_role",
        "def _roles_from_claims",
        "def _display_name_from_claims",
        "def _user_context_from_claims",
    ):
        assert retired_helper not in main_source

    assert "from backend.web.auth_claims import" in auth_middleware_source
    assert "primary_role(" in auth_middleware_source
    assert "user_context_from_claims(" in auth_middleware_source
    assert "from backend.web.auth_claims import" in auth_bridge_source
