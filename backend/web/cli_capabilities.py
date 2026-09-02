"""Capability routing for every explicitly CLI-enabled API operation.

Why:
    CLI tokens are accepted only on an allowlist that mirrors the OpenAPI
    contract. Authoring and diagnostics share the same authentication
    mechanism, while each operation still declares its minimum scope.
"""

from __future__ import annotations

from backend.web.cli_authoring import (
    CLI_AUTHORING_CAPABILITIES,
    CLICapability,
    path_matches_template,
)

CLI_DIAGNOSTICS_CAPABILITIES: tuple[CLICapability, ...] = (
    CLICapability("GET", "/api/diagnostics/views/courses/{course_id}/matrix", "read"),
    CLICapability("GET", "/api/diagnostics/views/learners/{student_sub}/profile", "read"),
    CLICapability(
        "GET",
        "/api/teaching/courses/{course_id}/units/{unit_id}/submissions/summary",
        "read",
    ),
    CLICapability(
        "GET",
        "/api/teaching/courses/{course_id}/students/{student_sub}/submissions/overview",
        "read",
    ),
    CLICapability(
        "GET",
        (
            "/api/teaching/courses/{course_id}/units/{unit_id}/tasks/{task_id}/"
            "students/{student_sub}/submissions/latest"
        ),
        "read",
    ),
    CLICapability(
        "GET",
        (
            "/api/teaching/courses/{course_id}/units/{unit_id}/tasks/{task_id}/"
            "students/{student_sub}/submissions/latest/file"
        ),
        "read",
    ),
    CLICapability(
        "GET",
        (
            "/api/teaching/courses/{course_id}/units/{unit_id}/tasks/{task_id}/"
            "students/{student_sub}/submissions/{submission_id}/dialog"
        ),
        "read",
    ),
)


CLI_CAPABILITIES: tuple[CLICapability, ...] = (
    *CLI_AUTHORING_CAPABILITIES,
    *CLI_DIAGNOSTICS_CAPABILITIES,
)


def cli_capability_for_request(method: str, path: str) -> CLICapability | None:
    """Return the exact CLI capability for one HTTP request, if enabled."""

    normalized_method = method.upper()
    for capability in CLI_CAPABILITIES:
        if capability.method == normalized_method and path_matches_template(
            capability.path_template, path
        ):
            return capability
    return None
