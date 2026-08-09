"""Course-authoring command definitions for the GUSTAV CLI.

Why:
    Course management is a coherent authoring surface with many commands. It
    lives outside the CLI entry module so argument parsing and request mapping
    stay readable while transport, authentication and output remain shared.
"""

from __future__ import annotations

import argparse
from typing import Any, Callable, TextIO
from urllib.parse import quote, urlencode

from .operations import course_operation


Request = Callable[..., int]


def _add_json(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true")


def register_course_parsers(sub: Any) -> None:
    """Register course, membership and release commands."""

    courses = sub.add_parser("courses")
    course_sub = courses.add_subparsers(dest="command", required=True)

    list_cmd = course_sub.add_parser("list")
    list_cmd.add_argument("--status", choices=("active", "archived"), default="active")
    list_cmd.add_argument("--limit", type=int, default=10)
    list_cmd.add_argument("--offset", type=int, default=0)
    _add_json(list_cmd)

    create = course_sub.add_parser("create")
    create.add_argument("--title", required=True)
    create.add_argument("--subject", required=True)
    create.add_argument("--grade-level", required=True)
    create.add_argument("--school-year-start", required=True, type=int)
    create.add_argument("--term")
    _add_json(create)

    for name in ("show", "archive", "restore", "deletion-impact"):
        command = course_sub.add_parser(name)
        command.add_argument("course_id")
        _add_json(command)

    edit = course_sub.add_parser("edit")
    edit.add_argument("course_id")
    edit.add_argument("--title")
    edit.add_argument("--subject")
    edit.add_argument("--grade-level")
    edit.add_argument("--school-year-start", type=int)
    term = edit.add_mutually_exclusive_group()
    term.add_argument("--term")
    term.add_argument("--clear-term", action="store_true")
    _add_json(edit)

    archive_batch = course_sub.add_parser("archive-batch")
    archive_batch.add_argument("--ids", nargs="+", required=True)
    _add_json(archive_batch)

    delete = course_sub.add_parser("delete")
    delete.add_argument("course_id")
    delete.add_argument("--confirmation-title", required=True)
    delete.add_argument("--confirm-student-data-loss", action="store_true")
    delete.add_argument("--yes", action="store_true")
    _add_json(delete)

    jobs = sub.add_parser("course-deletion-jobs")
    jobs_sub = jobs.add_subparsers(dest="command", required=True)
    jobs_list = jobs_sub.add_parser("list")
    jobs_list.add_argument("--include-completed", action="store_true")
    jobs_list.add_argument("--limit", type=int, default=50)
    jobs_list.add_argument("--offset", type=int, default=0)
    _add_json(jobs_list)
    jobs_show = jobs_sub.add_parser("show")
    jobs_show.add_argument("job_id")
    _add_json(jobs_show)

    members = sub.add_parser("course-members")
    members_sub = members.add_subparsers(dest="command", required=True)
    members_list = members_sub.add_parser("list")
    members_list.add_argument("--course-id", required=True)
    members_list.add_argument("--limit", type=int, default=10)
    members_list.add_argument("--offset", type=int, default=0)
    _add_json(members_list)
    members_add = members_sub.add_parser("add")
    members_add.add_argument("--course-id", required=True)
    members_add.add_argument("--student-sub", required=True)
    _add_json(members_add)
    members_remove = members_sub.add_parser("remove")
    members_remove.add_argument("--course-id", required=True)
    members_remove.add_argument("--student-sub", required=True)
    members_remove.add_argument("--yes", action="store_true")
    _add_json(members_remove)

    modules = sub.add_parser("course-modules")
    modules_sub = modules.add_subparsers(dest="command", required=True)
    modules_list = modules_sub.add_parser("list")
    modules_list.add_argument("--course-id", required=True)
    _add_json(modules_list)
    modules_add = modules_sub.add_parser("add")
    modules_add.add_argument("--course-id", required=True)
    modules_add.add_argument("--unit-id", required=True)
    modules_add.add_argument("--context-notes")
    _add_json(modules_add)
    modules_reorder = modules_sub.add_parser("reorder")
    modules_reorder.add_argument("--course-id", required=True)
    modules_reorder.add_argument("--ids", nargs="+", required=True)
    _add_json(modules_reorder)
    modules_remove = modules_sub.add_parser("remove")
    modules_remove.add_argument("--course-id", required=True)
    modules_remove.add_argument("--module-id", required=True)
    modules_remove.add_argument("--yes", action="store_true")
    _add_json(modules_remove)

    sections = sub.add_parser("course-sections")
    sections_sub = sections.add_subparsers(dest="command", required=True)
    for name in ("list", "release", "hide"):
        command = sections_sub.add_parser(name)
        command.add_argument("--course-id", required=True)
        command.add_argument("--module-id", required=True)
        if name != "list":
            command.add_argument("--section-id", required=True)
        _add_json(command)

    students = sub.add_parser("students")
    students_sub = students.add_subparsers(dest="command", required=True)
    search = students_sub.add_parser("search")
    search.add_argument("--query", required=True)
    search.add_argument("--limit", type=int, default=20)
    _add_json(search)


def _call(
    request: Request,
    *,
    method: str,
    path: str,
    body: object | None,
    success: set[int],
    args: argparse.Namespace,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    return request(
        method=method,
        path=path,
        json_body=body,
        success=success,
        stdout=stdout,
        stderr=stderr,
        as_json=args.json,
    )


def _call_operation(
    request: Request,
    operation_name: str,
    *,
    path_parameters: dict[str, str] | None = None,
    query: str | None = None,
    body: object | None,
    success: set[int],
    args: argparse.Namespace,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    operation = course_operation(operation_name, **(path_parameters or {}))
    path = operation.path_template if query is None else f"{operation.path_template}?{query}"
    return _call(
        request,
        method=operation.method,
        path=path,
        body=body,
        success=success,
        args=args,
        stdout=stdout,
        stderr=stderr,
    )


def run_course_command(
    args: argparse.Namespace,
    *,
    request: Request,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    """Map one parsed course command to its existing REST endpoint."""

    if args.group == "courses":
        return _run_courses(args, request=request, stdout=stdout, stderr=stderr)
    if args.group == "course-deletion-jobs":
        if args.command == "list":
            query = urlencode(
                {
                    "include_completed": str(args.include_completed).lower(),
                    "limit": args.limit,
                    "offset": args.offset,
                }
            )
            return _call_operation(
                request,
                "deletion_jobs.list",
                query=query,
                body=None,
                success={200},
                args=args,
                stdout=stdout,
                stderr=stderr,
            )
        return _call_operation(
            request,
            "deletion_jobs.show",
            path_parameters={"job_id": quote(args.job_id, safe="")},
            body=None,
            success={200},
            args=args,
            stdout=stdout,
            stderr=stderr,
        )
    if args.group == "course-members":
        return _run_members(args, request=request, stdout=stdout, stderr=stderr)
    if args.group == "course-modules":
        return _run_modules(args, request=request, stdout=stdout, stderr=stderr)
    if args.group == "course-sections":
        return _run_sections(args, request=request, stdout=stdout, stderr=stderr)
    if args.group == "students":
        query = urlencode({"q": args.query, "role": "student", "limit": args.limit})
        return _call_operation(
            request,
            "students.search",
            query=query,
            body=None,
            success={200},
            args=args,
            stdout=stdout,
            stderr=stderr,
        )
    return 2


def _run_courses(
    args: argparse.Namespace, *, request: Request, stdout: TextIO, stderr: TextIO
) -> int:
    if args.command == "list":
        query = urlencode({"status": args.status, "limit": args.limit, "offset": args.offset})
        return _call_operation(
            request,
            "courses.list",
            query=query,
            body=None,
            success={200},
            args=args,
            stdout=stdout,
            stderr=stderr,
        )
    if args.command == "create":
        body: dict[str, object] = {
            "title": args.title,
            "subject": args.subject,
            "grade_level": args.grade_level,
            "school_year_start": args.school_year_start,
        }
        if args.term is not None:
            body["term"] = args.term
        return _call_operation(
            request,
            "courses.create",
            body=body,
            success={201},
            args=args,
            stdout=stdout,
            stderr=stderr,
        )
    if args.command == "archive-batch":
        return _call_operation(
            request,
            "courses.archive_batch",
            body={"course_ids": args.ids},
            success={200},
            args=args,
            stdout=stdout,
            stderr=stderr,
        )
    course_id = quote(args.course_id, safe="")
    if args.command == "show":
        return _call_operation(
            request,
            "courses.show",
            path_parameters={"course_id": course_id},
            body=None,
            success={200},
            args=args,
            stdout=stdout,
            stderr=stderr,
        )
    if args.command == "edit":
        body = {}
        for argument, field in (
            (args.title, "title"),
            (args.subject, "subject"),
            (args.grade_level, "grade_level"),
            (args.school_year_start, "school_year_start"),
        ):
            if argument is not None:
                body[field] = argument
        if args.term is not None:
            body["term"] = args.term
        elif args.clear_term:
            body["term"] = None
        if not body:
            stderr.write("Mindestens ein Kursfeld ist erforderlich.\n")
            return 1
        return _call_operation(
            request,
            "courses.edit",
            path_parameters={"course_id": course_id},
            body=body,
            success={200},
            args=args,
            stdout=stdout,
            stderr=stderr,
        )
    if args.command in {"archive", "restore"}:
        return _call_operation(
            request,
            f"courses.{args.command}",
            path_parameters={"course_id": course_id},
            body=None,
            success={200},
            args=args,
            stdout=stdout,
            stderr=stderr,
        )
    if args.command == "deletion-impact":
        return _call_operation(
            request,
            "courses.deletion_impact",
            path_parameters={"course_id": course_id},
            body=None,
            success={200},
            args=args,
            stdout=stdout,
            stderr=stderr,
        )
    if args.command == "delete":
        if not args.yes:
            stderr.write("Löschen erfordert --yes.\n")
            return 1
        if not args.confirm_student_data_loss:
            stderr.write("Löschen erfordert --confirm-student-data-loss.\n")
            return 1
        body = {
            "confirmation_title": args.confirmation_title,
            "confirm_student_data_loss": True,
        }
        return _call_operation(
            request,
            "courses.delete",
            path_parameters={"course_id": course_id},
            body=body,
            success={202},
            args=args,
            stdout=stdout,
            stderr=stderr,
        )
    return 2


def _run_members(
    args: argparse.Namespace, *, request: Request, stdout: TextIO, stderr: TextIO
) -> int:
    course_id = quote(args.course_id, safe="")
    if args.command == "list":
        query = urlencode({"limit": args.limit, "offset": args.offset})
        return _call_operation(
            request,
            "course_members.list",
            path_parameters={"course_id": course_id},
            query=query,
            body=None,
            success={200},
            args=args,
            stdout=stdout,
            stderr=stderr,
        )
    if args.command == "add":
        return _call_operation(
            request,
            "course_members.add",
            path_parameters={"course_id": course_id},
            body={"student_sub": args.student_sub},
            success={201, 204},
            args=args,
            stdout=stdout,
            stderr=stderr,
        )
    if not args.yes:
        stderr.write("Löschen erfordert --yes.\n")
        return 1
    return _call_operation(
        request,
        "course_members.remove",
        path_parameters={"course_id": course_id, "student_sub": quote(args.student_sub, safe="")},
        body=None,
        success={204},
        args=args,
        stdout=stdout,
        stderr=stderr,
    )


def _run_modules(
    args: argparse.Namespace, *, request: Request, stdout: TextIO, stderr: TextIO
) -> int:
    course_id = quote(args.course_id, safe="")
    if args.command == "list":
        return _call_operation(
            request,
            "course_modules.list",
            path_parameters={"course_id": course_id},
            body=None,
            success={200},
            args=args,
            stdout=stdout,
            stderr=stderr,
        )
    if args.command == "add":
        body: dict[str, object] = {"unit_id": args.unit_id}
        if args.context_notes is not None:
            body["context_notes"] = args.context_notes
        return _call_operation(
            request,
            "course_modules.add",
            path_parameters={"course_id": course_id},
            body=body,
            success={201},
            args=args,
            stdout=stdout,
            stderr=stderr,
        )
    if args.command == "reorder":
        return _call_operation(
            request,
            "course_modules.reorder",
            path_parameters={"course_id": course_id},
            body={"module_ids": args.ids},
            success={200},
            args=args,
            stdout=stdout,
            stderr=stderr,
        )
    if not args.yes:
        stderr.write("Löschen erfordert --yes.\n")
        return 1
    return _call_operation(
        request,
        "course_modules.remove",
        path_parameters={"course_id": course_id, "module_id": quote(args.module_id, safe="")},
        body=None,
        success={204},
        args=args,
        stdout=stdout,
        stderr=stderr,
    )


def _run_sections(
    args: argparse.Namespace, *, request: Request, stdout: TextIO, stderr: TextIO
) -> int:
    path_parameters = {
        "course_id": quote(args.course_id, safe=""),
        "module_id": quote(args.module_id, safe=""),
    }
    if args.command == "list":
        return _call_operation(
            request,
            "course_sections.list",
            path_parameters=path_parameters,
            body=None,
            success={200},
            args=args,
            stdout=stdout,
            stderr=stderr,
        )
    path_parameters["section_id"] = quote(args.section_id, safe="")
    return _call_operation(
        request,
        "course_sections.visibility",
        path_parameters=path_parameters,
        body={"visible": args.command == "release"},
        success={200},
        args=args,
        stdout=stdout,
        stderr=stderr,
    )
