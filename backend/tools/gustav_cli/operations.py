"""Declarative REST operations used by the expanded CLI authoring surface."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CLIOperation:
    """Describe one GUSTAV API operation without duplicating server scopes."""

    method: str
    path_template: str


COURSE_AUTHORING_OPERATIONS: dict[str, CLIOperation] = {
    "courses.list": CLIOperation("GET", "/api/teaching/courses"),
    "courses.create": CLIOperation("POST", "/api/teaching/courses"),
    "courses.show": CLIOperation("GET", "/api/teaching/courses/{course_id}"),
    "courses.edit": CLIOperation("PATCH", "/api/teaching/courses/{course_id}"),
    "courses.archive": CLIOperation("POST", "/api/teaching/courses/{course_id}/archive"),
    "courses.restore": CLIOperation("POST", "/api/teaching/courses/{course_id}/restore"),
    "courses.archive_batch": CLIOperation("POST", "/api/teaching/courses/archive-batch"),
    "courses.deletion_impact": CLIOperation(
        "GET", "/api/teaching/courses/{course_id}/deletion-impact"
    ),
    "courses.delete": CLIOperation("POST", "/api/teaching/courses/{course_id}/deletion-jobs"),
    "deletion_jobs.list": CLIOperation("GET", "/api/teaching/course-deletion-jobs"),
    "deletion_jobs.show": CLIOperation("GET", "/api/teaching/course-deletion-jobs/{job_id}"),
    "course_members.list": CLIOperation("GET", "/api/teaching/courses/{course_id}/members"),
    "course_members.add": CLIOperation("POST", "/api/teaching/courses/{course_id}/members"),
    "course_members.remove": CLIOperation(
        "DELETE", "/api/teaching/courses/{course_id}/members/{student_sub}"
    ),
    "course_modules.list": CLIOperation("GET", "/api/teaching/courses/{course_id}/modules"),
    "course_modules.add": CLIOperation("POST", "/api/teaching/courses/{course_id}/modules"),
    "course_modules.reorder": CLIOperation(
        "POST", "/api/teaching/courses/{course_id}/modules/reorder"
    ),
    "course_modules.remove": CLIOperation(
        "DELETE", "/api/teaching/courses/{course_id}/modules/{module_id}"
    ),
    "course_sections.list": CLIOperation(
        "GET", "/api/teaching/courses/{course_id}/modules/{module_id}/sections"
    ),
    "course_sections.visibility": CLIOperation(
        "PATCH",
        "/api/teaching/courses/{course_id}/modules/{module_id}/sections/{section_id}/visibility",
    ),
    "students.search": CLIOperation("GET", "/api/users/search"),
}


def course_operation(name: str, **path_parameters: str) -> CLIOperation:
    """Resolve a registered operation and substitute already-escaped path values."""

    operation = COURSE_AUTHORING_OPERATIONS[name]
    return CLIOperation(
        method=operation.method,
        path_template=operation.path_template.format(**path_parameters),
    )
