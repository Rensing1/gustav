"""CLI authoring capability routing for FastAPI bearer authentication."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CLICapability:
    method: str
    path_template: str
    required_scope: str


# Compatibility name for integrations that still import the former type.
CLIAuthoringCapability = CLICapability


CLI_AUTHORING_CAPABILITIES: tuple[CLIAuthoringCapability, ...] = (
    CLIAuthoringCapability("GET", "/api/me", "read"),
    CLIAuthoringCapability("GET", "/api/teaching/units", "read"),
    CLIAuthoringCapability("POST", "/api/teaching/units", "write"),
    CLIAuthoringCapability("PATCH", "/api/teaching/units/{unit_id}", "write"),
    CLIAuthoringCapability("DELETE", "/api/teaching/units/{unit_id}", "delete"),
    CLIAuthoringCapability("GET", "/api/teaching/units/{unit_id}/phases", "read"),
    CLIAuthoringCapability("POST", "/api/teaching/units/{unit_id}/phases", "write"),
    CLIAuthoringCapability("PATCH", "/api/teaching/units/{unit_id}/phases/{phase_id}", "write"),
    CLIAuthoringCapability("DELETE", "/api/teaching/units/{unit_id}/phases/{phase_id}", "delete"),
    CLIAuthoringCapability("POST", "/api/teaching/units/{unit_id}/phases/reorder", "write"),
    CLIAuthoringCapability("GET", "/api/teaching/units/{unit_id}/modules/graph", "read"),
    CLIAuthoringCapability("GET", "/api/teaching/units/{unit_id}/modules/{module_id}/content-target", "read"),
    CLIAuthoringCapability("POST", "/api/teaching/units/{unit_id}/modules", "write"),
    CLIAuthoringCapability("PATCH", "/api/teaching/units/{unit_id}/modules/{module_id}", "write"),
    CLIAuthoringCapability("DELETE", "/api/teaching/units/{unit_id}/modules/{module_id}", "delete"),
    CLIAuthoringCapability("POST", "/api/teaching/units/{unit_id}/phases/{phase_id}/modules/reorder", "write"),
    CLIAuthoringCapability("POST", "/api/teaching/units/{unit_id}/modules/edges", "write"),
    CLIAuthoringCapability(
        "DELETE",
        "/api/teaching/units/{unit_id}/modules/{from_module_id}/edges/{to_module_id}",
        "delete",
    ),
    CLIAuthoringCapability("GET", "/api/teaching/units/{unit_id}/sections", "read"),
    CLIAuthoringCapability("POST", "/api/teaching/units/{unit_id}/sections", "write"),
    CLIAuthoringCapability("PATCH", "/api/teaching/units/{unit_id}/sections/{section_id}", "write"),
    CLIAuthoringCapability("DELETE", "/api/teaching/units/{unit_id}/sections/{section_id}", "delete"),
    CLIAuthoringCapability("POST", "/api/teaching/units/{unit_id}/sections/reorder", "write"),
    CLIAuthoringCapability("GET", "/api/teaching/units/{unit_id}/sections/{section_id}/tasks", "read"),
    CLIAuthoringCapability("POST", "/api/teaching/units/{unit_id}/sections/{section_id}/tasks", "write"),
    CLIAuthoringCapability(
        "PATCH",
        "/api/teaching/units/{unit_id}/sections/{section_id}/tasks/{task_id}",
        "write",
    ),
    CLIAuthoringCapability(
        "DELETE",
        "/api/teaching/units/{unit_id}/sections/{section_id}/tasks/{task_id}",
        "delete",
    ),
    CLIAuthoringCapability("POST", "/api/teaching/units/{unit_id}/sections/{section_id}/tasks/reorder", "write"),
    CLIAuthoringCapability("GET", "/api/teaching/units/{unit_id}/sections/{section_id}/materials", "read"),
    CLIAuthoringCapability("POST", "/api/teaching/units/{unit_id}/sections/{section_id}/materials", "write"),
    CLIAuthoringCapability(
        "PATCH",
        "/api/teaching/units/{unit_id}/sections/{section_id}/materials/{material_id}",
        "write",
    ),
    CLIAuthoringCapability(
        "DELETE",
        "/api/teaching/units/{unit_id}/sections/{section_id}/materials/{material_id}",
        "delete",
    ),
    CLIAuthoringCapability(
        "POST",
        "/api/teaching/units/{unit_id}/sections/{section_id}/materials/reorder",
        "write",
    ),
    CLIAuthoringCapability(
        "POST",
        "/api/teaching/units/{unit_id}/sections/{section_id}/materials/upload-intents",
        "write",
    ),
    CLIAuthoringCapability(
        "POST",
        "/api/teaching/units/{unit_id}/sections/{section_id}/materials/finalize",
        "write",
    ),
    CLIAuthoringCapability(
        "GET",
        "/api/teaching/units/{unit_id}/sections/{section_id}/materials/{material_id}/download-url",
        "read",
    ),
    CLIAuthoringCapability(
        "GET",
        "/api/teaching/units/{unit_id}/materials/{material_id}/simulation",
        "read",
    ),
    CLIAuthoringCapability("POST", "/api/teaching/units/{unit_id}/modules/{module_id}/materials", "write"),
    CLIAuthoringCapability(
        "PATCH",
        "/api/teaching/units/{unit_id}/modules/{module_id}/materials/{material_id}",
        "write",
    ),
    CLIAuthoringCapability(
        "DELETE",
        "/api/teaching/units/{unit_id}/modules/{module_id}/materials/{material_id}",
        "delete",
    ),
    CLIAuthoringCapability(
        "POST",
        "/api/teaching/units/{unit_id}/modules/{module_id}/materials/reorder",
        "write",
    ),
    CLIAuthoringCapability(
        "POST",
        "/api/teaching/units/{unit_id}/modules/{module_id}/materials/upload-intents",
        "write",
    ),
    CLIAuthoringCapability(
        "POST",
        "/api/teaching/units/{unit_id}/modules/{module_id}/materials/finalize",
        "write",
    ),
    CLIAuthoringCapability("GET", "/api/teaching/units/{unit_id}/modules/{module_id}/tasks", "read"),
    CLIAuthoringCapability("POST", "/api/teaching/units/{unit_id}/modules/{module_id}/tasks", "write"),
    CLIAuthoringCapability(
        "PATCH",
        "/api/teaching/units/{unit_id}/modules/{module_id}/tasks/{task_id}",
        "write",
    ),
    CLIAuthoringCapability(
        "DELETE",
        "/api/teaching/units/{unit_id}/modules/{module_id}/tasks/{task_id}",
        "delete",
    ),
    CLIAuthoringCapability(
        "POST",
        "/api/teaching/units/{unit_id}/modules/{module_id}/tasks/reorder",
        "write",
    ),
    CLIAuthoringCapability(
        "POST",
        "/api/teaching/units/{unit_id}/sections/{section_id}/tasks/{task_id}/h5p/import",
        "write",
    ),
    CLIAuthoringCapability(
        "GET",
        "/api/teaching/units/{unit_id}/sections/{section_id}/tasks/{task_id}/h5p/export",
        "read",
    ),
    CLIAuthoringCapability(
        "POST",
        "/api/teaching/units/{unit_id}/sections/{section_id}/tasks/{task_id}/h5p/reset",
        "write",
    ),
    CLIAuthoringCapability(
        "POST",
        "/api/teaching/units/{unit_id}/modules/{module_id}/tasks/{task_id}/h5p/import",
        "write",
    ),
    CLIAuthoringCapability(
        "POST",
        "/api/teaching/units/{unit_id}/modules/{module_id}/tasks/{task_id}/h5p/reset",
        "write",
    ),
    CLIAuthoringCapability("GET", "/api/teaching/courses", "read"),
    CLIAuthoringCapability("POST", "/api/teaching/courses", "write"),
    CLIAuthoringCapability("GET", "/api/teaching/courses/{course_id}", "read"),
    CLIAuthoringCapability("PATCH", "/api/teaching/courses/{course_id}", "write"),
    CLIAuthoringCapability("POST", "/api/teaching/courses/{course_id}/archive", "write"),
    CLIAuthoringCapability("POST", "/api/teaching/courses/{course_id}/restore", "write"),
    CLIAuthoringCapability("POST", "/api/teaching/courses/archive-batch", "write"),
    CLIAuthoringCapability("GET", "/api/teaching/courses/{course_id}/deletion-impact", "read"),
    CLIAuthoringCapability("POST", "/api/teaching/courses/{course_id}/deletion-jobs", "delete"),
    CLIAuthoringCapability("GET", "/api/teaching/course-deletion-jobs", "read"),
    CLIAuthoringCapability("GET", "/api/teaching/course-deletion-jobs/{job_id}", "read"),
    CLIAuthoringCapability("GET", "/api/teaching/courses/{course_id}/members", "read"),
    CLIAuthoringCapability("POST", "/api/teaching/courses/{course_id}/members", "write"),
    CLIAuthoringCapability(
        "DELETE",
        "/api/teaching/courses/{course_id}/members/{student_sub}",
        "delete",
    ),
    CLIAuthoringCapability("GET", "/api/teaching/courses/{course_id}/modules", "read"),
    CLIAuthoringCapability("POST", "/api/teaching/courses/{course_id}/modules", "write"),
    CLIAuthoringCapability(
        "POST",
        "/api/teaching/courses/{course_id}/modules/reorder",
        "write",
    ),
    CLIAuthoringCapability(
        "DELETE",
        "/api/teaching/courses/{course_id}/modules/{module_id}",
        "delete",
    ),
    CLIAuthoringCapability(
        "GET",
        "/api/teaching/courses/{course_id}/modules/{module_id}/sections",
        "read",
    ),
    CLIAuthoringCapability(
        "PATCH",
        "/api/teaching/courses/{course_id}/modules/{module_id}/sections/{section_id}/visibility",
        "write",
    ),
    CLIAuthoringCapability("GET", "/api/users/search", "read"),
)


def path_matches_template(path_template: str, path: str) -> bool:
    """Return whether a concrete path matches a route template exactly."""

    template_parts = path_template.strip("/").split("/")
    path_parts = path.strip("/").split("/")
    if len(template_parts) != len(path_parts):
        return False
    for template_part, path_part in zip(template_parts, path_parts):
        if template_part.startswith("{") and template_part.endswith("}"):
            if not path_part:
                return False
            continue
        if template_part != path_part:
            return False
    return True


def cli_capability_for_request(method: str, path: str) -> CLIAuthoringCapability | None:
    """Find the documented CLI authoring capability for an HTTP request."""

    normalized_method = method.upper()
    for capability in CLI_AUTHORING_CAPABILITIES:
        if capability.method == normalized_method and path_matches_template(capability.path_template, path):
            return capability
    return None
