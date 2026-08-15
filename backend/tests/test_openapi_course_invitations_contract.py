"""Contract tests for QR and email course invitations.

Why:
    Invitation links combine public capabilities, authenticated membership
    writes and owner-only email delivery. These tests keep those permission
    boundaries explicit before adapters or database code are implemented.
"""

from __future__ import annotations

from pathlib import Path

import yaml


def _spec() -> dict:
    root = Path(__file__).resolve().parents[2]
    return yaml.safe_load((root / "api" / "openapi.yml").read_text(encoding="utf-8"))


def test_course_invitation_contract_exposes_owner_and_learner_paths() -> None:
    spec = _spec()
    paths = spec["paths"]

    owner_paths = {
        "/api/teaching/courses/{course_id}/invitations": "post",
        "/api/teaching/courses/{course_id}/invitations/active": "get",
        "/api/teaching/courses/{course_id}/invitations/{invitation_id}": "delete",
        "/api/teaching/courses/{course_id}/invitations/{invitation_id}/email-deliveries": "post",
        "/api/teaching/courses/{course_id}/invitations/{invitation_id}/email-deliveries/status": "get",
        "/api/teaching/courses/{course_id}/invitations/{invitation_id}/email-deliveries/retry": "post",
    }
    for path, method in owner_paths.items():
        operation = paths[path][method]
        assert operation["x-permissions"] == {"requiredRole": "teacher", "ownerOnly": True}

    assert paths["/api/course-invitations/preview"]["post"]["security"] == []
    assert paths["/api/course-invitations/redeem"]["post"]["x-permissions"] == {
        "requiredRole": "student"
    }


def test_invitation_tokens_are_body_only_and_responses_are_no_store() -> None:
    spec = _spec()
    paths = spec["paths"]

    for path in ["/api/course-invitations/preview", "/api/course-invitations/redeem"]:
        operation = paths[path]["post"]
        assert not operation.get("parameters"), "Capability tokens must never be URL parameters"
        schema = operation["requestBody"]["content"]["application/json"]["schema"]
        assert schema["$ref"] == "#/components/schemas/CourseInvitationTokenRequest"

    preview_headers = paths["/api/course-invitations/preview"]["post"]["responses"]["200"]["headers"]
    assert preview_headers["Cache-Control"]["example"] == "private, no-store"
    assert preview_headers["Referrer-Policy"]["example"] == "no-referrer"


def test_invitation_contract_locks_duration_recipient_limit_and_redemption_semantics() -> None:
    spec = _spec()
    schemas = spec["components"]["schemas"]
    create = spec["paths"]["/api/teaching/courses/{course_id}/invitations"]["post"]

    assert "24 hours" in create["description"]
    recipients = schemas["CourseInvitationEmailRequest"]["properties"]["recipients"]
    assert recipients["maxItems"] == 100
    assert recipients["uniqueItems"] is True

    redeem_responses = spec["paths"]["/api/course-invitations/redeem"]["post"]["responses"]
    assert {"200", "201", "403", "404", "409"}.issubset(redeem_responses)
    result = schemas["CourseInvitationRedemption"]["properties"]["result"]
    assert result["enum"] == ["joined", "already_member"]


def test_invitation_status_exposes_only_failed_recipient_addresses() -> None:
    spec = _spec()
    schemas = spec["components"]["schemas"]
    invitation = schemas["CourseInvitation"]
    counts = schemas["CourseInvitationEmailCounts"]
    status = schemas["CourseInvitationEmailStatus"]

    assert invitation["properties"]["email_status"]["$ref"] == (
        "#/components/schemas/CourseInvitationEmailCounts"
    )
    assert counts["additionalProperties"] is False
    assert set(counts["properties"]) == {"pending", "sent", "failed"}
    assert status["additionalProperties"] is False
    assert set(status["properties"]) == {"pending", "sent", "failed", "failed_recipients"}
    assert status["properties"]["failed_recipients"]["items"]["format"] == "email"


def test_invitation_email_operations_reference_their_actual_response_shapes() -> None:
    spec = _spec()
    paths = spec["paths"]
    schemas = spec["components"]["schemas"]

    status_path = (
        "/api/teaching/courses/{course_id}/invitations/{invitation_id}"
        "/email-deliveries/status"
    )
    retry_path = (
        "/api/teaching/courses/{course_id}/invitations/{invitation_id}"
        "/email-deliveries/retry"
    )
    status_schema = paths[status_path]["get"]["responses"]["200"]["content"]
    retry_schema = paths[retry_path]["post"]["responses"]["202"]["content"]

    assert status_schema["application/json"]["schema"]["$ref"] == (
        "#/components/schemas/CourseInvitationEmailStatus"
    )
    assert retry_schema["application/json"]["schema"]["$ref"] == (
        "#/components/schemas/CourseInvitationEmailRetryQueued"
    )
    assert set(schemas["CourseInvitationEmailRetryQueued"]["properties"]) == {"queued"}


def test_invitation_error_contract_is_fail_closed_and_matches_domain_conflicts() -> None:
    spec = _spec()
    paths = spec["paths"]
    create_responses = paths[
        "/api/teaching/courses/{course_id}/invitations"
    ]["post"]["responses"]

    assert "409" in create_responses
    assert "400" not in create_responses

    for path in ["/api/course-invitations/preview", "/api/course-invitations/redeem"]:
        responses = paths[path]["post"]["responses"]
        assert "400" not in responses
        assert "malformed" in responses["404"]["description"].lower()
