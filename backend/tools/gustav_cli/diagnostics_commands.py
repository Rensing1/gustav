"""Read-only diagnostics commands for the GUSTAV Teaching CLI.

Why:
    Teachers and automation need the same owner-scoped diagnostics projections
    as the web application. This adapter handles navigation, pagination and
    terminal rendering only; authorization and learning rules stay in the API.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
import unicodedata
from pathlib import Path
from typing import Any, Callable, TextIO
from urllib.parse import quote, urlencode

from .config import GustavCLIConfig, load_config
from .operations import diagnostics_operation

JsonRequest = Callable[..., tuple[int, Any]]
BytesRequest = Callable[..., tuple[int, bytes]]

_COURSE_PAGE_SIZE = 50
_UNIT_PAGE_SIZE = 100
_PROFILE_PAGE_SIZE = 50
_MAX_SUBMISSION_DOWNLOAD_BYTES = 10 * 1024 * 1024
_DIALOG_INTERNAL_FIELDS = {"role_md", "learning_goal_md", "teacher_context_md"}
_PUBLIC_API_ERRORS = {
    "api_error",
    "bad_request",
    "forbidden",
    "internal_error",
    "not_found",
    "service_unavailable",
    "unauthenticated",
}
_PUBLIC_API_DETAILS = {
    "invalid_disposition",
    "invalid_pagination",
    "invalid_uuid",
    "summary_cursor_unavailable",
    "too_many_unit_ids",
}


def register_diagnostics_parsers(sub: Any) -> None:
    """Register the public read-only diagnostics command group."""

    diagnostics = sub.add_parser("diagnostics")
    commands = diagnostics.add_subparsers(dest="command", required=True)

    course = commands.add_parser("course")
    course.add_argument("--course-id", required=True)
    course.add_argument("--json", action="store_true")

    unit = commands.add_parser("unit")
    unit.add_argument("--course-id", required=True)
    unit.add_argument("--unit-id", required=True)
    unit.add_argument("--task-id")
    unit.add_argument("--json", action="store_true")

    student = commands.add_parser("student")
    student.add_argument("--student-sub", required=True)
    student.add_argument("--course-id")
    student.add_argument("--unit-id", action="append", default=[])
    student.add_argument("--json", action="store_true")

    for name in ("submission", "download"):
        command = commands.add_parser(name)
        command.add_argument("--course-id", required=True)
        command.add_argument("--unit-id", required=True)
        command.add_argument("--task-id", required=True)
        command.add_argument("--student-sub", required=True)
        if name == "submission":
            command.add_argument("--json", action="store_true")
        else:
            command.add_argument("--output", required=True)
            command.add_argument("--force", action="store_true")


def _config_or_error(stderr: TextIO) -> GustavCLIConfig | None:
    try:
        return load_config()
    except FileNotFoundError:
        stderr.write("GUSTAV CLI ist noch nicht konfiguriert.\n")
        return None


def _headers(config: GustavCLIConfig) -> dict[str, str]:
    return {"Authorization": f"Bearer {config.token}"}


def _safe_api_error(status: int, body: object, *, stderr: TextIO) -> None:
    """Print only the API's normalized error classification, never content."""

    error = "api_error"
    detail = ""
    if isinstance(body, dict):
        candidate_error = str(body.get("error") or "")
        candidate_detail = str(body.get("detail") or "")
        if candidate_error in _PUBLIC_API_ERRORS:
            error = candidate_error
        if candidate_detail in _PUBLIC_API_DETAILS:
            detail = candidate_detail
    suffix = f" ({detail})" if detail else ""
    stderr.write(f"API-Fehler ({status}): {error}{suffix}\n")


def _terminal_text(value: object, *, multiline: bool = False) -> str:
    """Render untrusted text without terminal controls or forged table cells."""

    normalized = str("" if value is None else value).replace("\r\n", "\n").replace("\r", "\n")
    rendered: list[str] = []
    for character in normalized:
        if character == "\n" and multiline:
            rendered.append(character)
        elif character in {"\n", "\t"} or unicodedata.category(character) in {"Cc", "Cf", "Cs"}:
            rendered.append(" ")
        else:
            rendered.append(character)
    return "".join(rendered)


def _write_table_row(values: list[object], *, stdout: TextIO) -> None:
    """Write one tabular row after reducing every value to one safe line."""

    stdout.write("\t".join(_terminal_text(value) for value in values) + "\n")


def _get_json(
    config: GustavCLIConfig,
    path: str,
    *,
    http_json: JsonRequest,
) -> tuple[int, Any]:
    return http_json(
        "GET",
        f"{config.base_url}{path}",
        headers=_headers(config),
        json_body=None,
    )


def _page_signature(items: list[object]) -> str:
    return json.dumps(items, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _load_all_pages(
    config: GustavCLIConfig,
    *,
    operation_name: str,
    path_parameters: dict[str, str],
    collection_key: str,
    page_size: int,
    http_json: JsonRequest,
    stderr: TextIO,
) -> dict[str, Any] | None:
    operation = diagnostics_operation(operation_name, **path_parameters)
    offset = 0
    merged: dict[str, Any] | None = None
    collected: list[object] = []
    seen_pages: set[str] = set()

    while True:
        query = urlencode({"limit": page_size, "offset": offset})
        status, body = _get_json(
            config,
            f"{operation.path_template}?{query}",
            http_json=http_json,
        )
        if status != 200:
            _safe_api_error(status, body, stderr=stderr)
            return None
        if not isinstance(body, dict) or not isinstance(body.get(collection_key), list):
            stderr.write("API-Fehler: ungültige Diagnostikantwort.\n")
            return None

        page = list(body[collection_key])
        if merged is None:
            merged = dict(body)
        if not page:
            break

        signature = _page_signature(page)
        if signature in seen_pages:
            stderr.write("API-Fehler: Diagnostik-Paginierung macht keinen Fortschritt.\n")
            return None
        seen_pages.add(signature)
        collected.extend(page)

        if len(page) < page_size:
            break
        offset += len(page)

    if merged is None:
        return None
    merged[collection_key] = collected
    return merged


def _write_json(body: object, *, stdout: TextIO) -> None:
    stdout.write(json.dumps(body, ensure_ascii=False))
    stdout.write("\n")


def _render_course(body: dict[str, Any], *, stdout: TextIO) -> None:
    stdout.write(
        "student_sub\tstudent_name\tunit_id\tunit_name\tstatus\t"
        "submitted_tasks\ttotal_tasks\n"
    )
    units = {
        str(unit.get("id") or ""): str(unit.get("title") or "")
        for unit in body.get("units", [])
        if isinstance(unit, dict)
    }
    for row in body.get("rows", []):
        if not isinstance(row, dict):
            continue
        student = row.get("student") if isinstance(row.get("student"), dict) else {}
        for cell in row.get("cells", []):
            if not isinstance(cell, dict):
                continue
            unit_id = str(cell.get("unit_id") or "")
            submitted = int(cell.get("submitted_tasks") or 0)
            total = int(cell.get("total_tasks") or 0)
            _write_table_row(
                [
                    student.get("sub"),
                    student.get("name"),
                    unit_id,
                    units.get(unit_id, ""),
                    _progress_status(submitted, total),
                    submitted,
                    total,
                ],
                stdout=stdout,
            )


def _score_text(value: object) -> str:
    return "" if value is None else _terminal_text(value)


def _progress_status(submitted: int, total: int) -> str:
    if total > 0 and submitted >= total:
        return "vollständig"
    if submitted > 0:
        return "begonnen"
    return "offen"


def _render_unit(body: dict[str, Any], *, stdout: TextIO) -> None:
    stdout.write(
        "student_sub\tstudent_name\ttask_id\ttask_position\ttask_type\tstatus\t"
        "formativer_kriterienwert\th5p_punkte\th5p_abschluss\tlatest_submission_at\n"
    )
    tasks = {
        str(task.get("id") or ""): task
        for task in body.get("tasks", [])
        if isinstance(task, dict)
    }
    for row in body.get("rows", []):
        if not isinstance(row, dict):
            continue
        student = row.get("student") if isinstance(row.get("student"), dict) else {}
        for cell in row.get("tasks", []):
            if not isinstance(cell, dict):
                continue
            task_id = str(cell.get("task_id") or "")
            task = tasks.get(task_id, {})
            score_raw = cell.get("score_raw")
            score_max = cell.get("score_max")
            h5p_points = (
                f"{_score_text(score_raw)}/{_score_text(score_max)}"
                if score_raw is not None and score_max is not None
                else ""
            )
            h5p_completed = cell.get("h5p_completed")
            _write_table_row(
                [
                    student.get("sub"),
                    student.get("name"),
                    task_id,
                    task.get("position"),
                    task.get("kind"),
                    "abgegeben" if bool(cell.get("has_submission")) else "offen",
                    _score_text(cell.get("average_score")),
                    h5p_points,
                    (
                        "ja"
                        if h5p_completed is True
                        else ("nein" if h5p_completed is False else "")
                    ),
                    cell.get("created_at"),
                ],
                stdout=stdout,
            )


def _render_student_profile(body: dict[str, Any], *, stdout: TextIO) -> None:
    learner = body.get("learner") if isinstance(body.get("learner"), dict) else {}
    stdout.write(
        "student_sub\tstudent_name\tcourse_id\tcourse_name\tunit_id\tunit_name\t"
        "status\tsubmitted_tasks\ttotal_tasks\n"
    )
    for course in body.get("courses", []):
        if not isinstance(course, dict):
            continue
        for unit in course.get("units", []):
            if not isinstance(unit, dict):
                continue
            submitted = int(unit.get("submitted_tasks") or 0)
            total = int(unit.get("total_tasks") or 0)
            _write_table_row(
                [
                    learner.get("sub"),
                    learner.get("name"),
                    course.get("id"),
                    course.get("title"),
                    unit.get("id"),
                    unit.get("title"),
                    _progress_status(submitted, total),
                    submitted,
                    total,
                ],
                stdout=stdout,
            )


def _render_student_course(body: dict[str, Any], course_id: str, *, stdout: TextIO) -> None:
    student = body.get("student") if isinstance(body.get("student"), dict) else {}
    stdout.write(
        "student_sub\tstudent_name\tcourse_id\tunit_id\tunit_name\ttask_id\t"
        "task_position\ttask_type\tstatus\tformativer_kriterienwert\th5p_punkte\t"
        "h5p_abschluss\n"
    )
    for unit in body.get("units", []):
        if not isinstance(unit, dict):
            continue
        for task in unit.get("tasks", []):
            if not isinstance(task, dict):
                continue
            score_raw = task.get("score_raw")
            score_max = task.get("score_max")
            h5p_points = (
                f"{_score_text(score_raw)}/{_score_text(score_max)}"
                if score_raw is not None and score_max is not None
                else ""
            )
            _write_table_row(
                [
                    student.get("sub"),
                    student.get("name"),
                    course_id,
                    unit.get("id"),
                    unit.get("title"),
                    task.get("id"),
                    task.get("position"),
                    task.get("kind"),
                    "abgegeben" if bool(task.get("has_submission")) else "offen",
                    _score_text(task.get("average_score")),
                    h5p_points,
                    (
                        "ja"
                        if task.get("h5p_completed") is True
                        else ("nein" if task.get("h5p_completed") is False else "")
                    ),
                ],
                stdout=stdout,
            )


def _filter_task(body: dict[str, Any], task_id: str, *, stderr: TextIO) -> dict[str, Any] | None:
    selected = [
        task
        for task in body.get("tasks", [])
        if isinstance(task, dict) and str(task.get("id") or "") == task_id
    ]
    if not selected:
        stderr.write("Die Aufgabe gehört nicht zur gewählten Lerneinheit.\n")
        return None
    filtered = dict(body)
    filtered["tasks"] = selected
    rows: list[dict[str, Any]] = []
    for raw_row in body.get("rows", []):
        if not isinstance(raw_row, dict):
            continue
        row = dict(raw_row)
        row["tasks"] = [
            cell
            for cell in raw_row.get("tasks", [])
            if isinstance(cell, dict) and str(cell.get("task_id") or "") == task_id
        ]
        rows.append(row)
    filtered["rows"] = rows
    return filtered


def _sanitize_dialog(value: object) -> object:
    if isinstance(value, dict):
        return {
            str(key): _sanitize_dialog(item)
            for key, item in value.items()
            if str(key) not in _DIALOG_INTERNAL_FIELDS
        }
    if isinstance(value, list):
        return [_sanitize_dialog(item) for item in value]
    return value


def _render_submission(
    submission: dict[str, Any],
    dialog: dict[str, Any] | None,
    *,
    stdout: TextIO,
) -> None:
    stdout.write(f"Abgabe: {_terminal_text(submission.get('id'))}\n")
    stdout.write(f"Zeitpunkt: {_terminal_text(submission.get('created_at'))}\n")
    stdout.write(f"Typ: {_terminal_text(submission.get('kind'))}\n\n")
    stdout.write("Aufgabenstellung\n")
    stdout.write(f"{_terminal_text(submission.get('instruction_md'), multiline=True)}\n")

    text_body = submission.get("text_body")
    if isinstance(text_body, str) and text_body:
        stdout.write("\nAbgabeinhalt\n")
        stdout.write(f"{_terminal_text(text_body, multiline=True)}\n")

    if str(submission.get("kind") or "") == "h5p":
        raw = submission.get("score_raw")
        maximum = submission.get("score_max")
        stdout.write(f"\nH5P-Punkte: {_score_text(raw)}/{_score_text(maximum)}\n")
        completed = raw is not None and maximum is not None and raw == maximum
        stdout.write(f"H5P-Abschluss: {'ja' if completed else 'nein'}\n")

    analysis = submission.get("analysis_json")
    if isinstance(analysis, dict):
        stdout.write("\nAuswertung\n")
        if analysis.get("score") is not None:
            stdout.write(f"Formativer Gesamtscore: {_score_text(analysis['score'])}/5\n")
        for result in analysis.get("criteria_results", []):
            if not isinstance(result, dict):
                continue
            maximum = result.get("max_score") or 10
            stdout.write(
                f"{_terminal_text(result.get('criterion') or 'Kriterium')}: "
                f"{_score_text(result.get('score'))}/{_score_text(maximum)}\n"
            )
            explanation = result.get("explanation_md")
            if isinstance(explanation, str) and explanation:
                stdout.write(f"{_terminal_text(explanation, multiline=True)}\n")

    feedback = submission.get("feedback_md")
    if isinstance(feedback, str) and feedback:
        stdout.write("\nRückmeldung\n")
        stdout.write(f"{_terminal_text(feedback, multiline=True)}\n")

    if isinstance(dialog, dict):
        stdout.write("\nDialogtranskript\n")
        for turn in dialog.get("turns", []):
            if not isinstance(turn, dict):
                continue
            student_message = _terminal_text(turn.get("student_message_md"), multiline=True)
            stdout.write(f"Schüler: {student_message}\n")
            reply = turn.get("assistant_reply_md")
            if isinstance(reply, str) and reply:
                stdout.write(f"Lernpartner: {_terminal_text(reply, multiline=True)}\n")
        closing = dialog.get("closing_answer_md")
        if isinstance(closing, str) and closing:
            stdout.write(f"Abschluss: {_terminal_text(closing, multiline=True)}\n")


def _run_course(
    args: argparse.Namespace,
    config: GustavCLIConfig,
    *,
    http_json: JsonRequest,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    body = _load_all_pages(
        config,
        operation_name="course",
        path_parameters={"course_id": quote(args.course_id, safe="")},
        collection_key="rows",
        page_size=_COURSE_PAGE_SIZE,
        http_json=http_json,
        stderr=stderr,
    )
    if body is None:
        return 1
    if args.json:
        _write_json(body, stdout=stdout)
    else:
        _render_course(body, stdout=stdout)
    return 0


def _run_unit(
    args: argparse.Namespace,
    config: GustavCLIConfig,
    *,
    http_json: JsonRequest,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    body = _load_all_pages(
        config,
        operation_name="unit",
        path_parameters={
            "course_id": quote(args.course_id, safe=""),
            "unit_id": quote(args.unit_id, safe=""),
        },
        collection_key="rows",
        page_size=_UNIT_PAGE_SIZE,
        http_json=http_json,
        stderr=stderr,
    )
    if body is None:
        return 1
    if args.task_id:
        body = _filter_task(body, args.task_id, stderr=stderr)
        if body is None:
            return 1
    if args.json:
        _write_json(body, stdout=stdout)
    else:
        _render_unit(body, stdout=stdout)
    return 0


def _recompute_profile_summary(body: dict[str, Any]) -> None:
    courses = [course for course in body.get("courses", []) if isinstance(course, dict)]
    body["summary"] = {
        "courses_count": len(courses),
        "submitted_tasks": sum(int(course.get("submitted_tasks") or 0) for course in courses),
        "total_tasks": sum(int(course.get("total_tasks") or 0) for course in courses),
    }


def _run_student(
    args: argparse.Namespace,
    config: GustavCLIConfig,
    *,
    http_json: JsonRequest,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    if args.unit_id and not args.course_id:
        stderr.write("--unit-id erfordert --course-id.\n")
        return 2
    student_sub = quote(args.student_sub, safe="")
    if args.course_id:
        operation = diagnostics_operation(
            "student_course",
            course_id=quote(args.course_id, safe=""),
            student_sub=student_sub,
        )
        path = operation.path_template
        if args.unit_id:
            path = f"{path}?{urlencode([('unit_ids', value) for value in args.unit_id])}"
        status, body = _get_json(config, path, http_json=http_json)
        if status != 200:
            _safe_api_error(status, body, stderr=stderr)
            return 1
        if not isinstance(body, dict):
            stderr.write("API-Fehler: ungültige Diagnostikantwort.\n")
            return 1
        if args.json:
            _write_json(body, stdout=stdout)
        else:
            _render_student_course(body, args.course_id, stdout=stdout)
        return 0

    body = _load_all_pages(
        config,
        operation_name="student_profile",
        path_parameters={"student_sub": student_sub},
        collection_key="courses",
        page_size=_PROFILE_PAGE_SIZE,
        http_json=http_json,
        stderr=stderr,
    )
    if body is None:
        return 1
    _recompute_profile_summary(body)
    if args.json:
        _write_json(body, stdout=stdout)
    else:
        _render_student_profile(body, stdout=stdout)
    return 0


def _detail_parameters(args: argparse.Namespace) -> dict[str, str]:
    return {
        "course_id": quote(args.course_id, safe=""),
        "unit_id": quote(args.unit_id, safe=""),
        "task_id": quote(args.task_id, safe=""),
        "student_sub": quote(args.student_sub, safe=""),
    }


def _run_submission(
    args: argparse.Namespace,
    config: GustavCLIConfig,
    *,
    http_json: JsonRequest,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    parameters = _detail_parameters(args)
    operation = diagnostics_operation("submission", **parameters)
    status, body = _get_json(config, operation.path_template, http_json=http_json)
    if status == 204:
        result = {"submission": None, "dialog": None}
        if args.json:
            _write_json(result, stdout=stdout)
        else:
            stdout.write("Keine Abgabe vorhanden.\n")
        return 0
    if status != 200:
        _safe_api_error(status, body, stderr=stderr)
        return 1
    if not isinstance(body, dict):
        stderr.write("API-Fehler: ungültige Abgabeantwort.\n")
        return 1

    dialog: dict[str, Any] | None = None
    if str(body.get("kind") or "") == "dialog":
        submission_id = str(body.get("id") or "")
        if not submission_id:
            stderr.write("API-Fehler: Dialogabgabe ohne ID.\n")
            return 1
        dialog_operation = diagnostics_operation(
            "dialog",
            **parameters,
            submission_id=quote(submission_id, safe=""),
        )
        dialog_status, dialog_body = _get_json(
            config,
            dialog_operation.path_template,
            http_json=http_json,
        )
        if dialog_status != 200:
            _safe_api_error(dialog_status, dialog_body, stderr=stderr)
            return 1
        sanitized = _sanitize_dialog(dialog_body)
        if not isinstance(sanitized, dict):
            stderr.write("API-Fehler: ungültiges Dialogtranskript.\n")
            return 1
        dialog = sanitized

    result = {"submission": body, "dialog": dialog}
    if args.json:
        _write_json(result, stdout=stdout)
    else:
        _render_submission(body, dialog, stdout=stdout)
    return 0


def _target_exists(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def _write_private_download(path: Path, payload: bytes, *, force: bool) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        if force:
            os.replace(temporary, path)
        else:
            os.link(temporary, path)
            temporary.unlink()
        os.chmod(path, 0o600)
    finally:
        if temporary.exists():
            temporary.unlink()


def _run_download(
    args: argparse.Namespace,
    config: GustavCLIConfig,
    *,
    http_bytes: BytesRequest,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    target = Path(args.output).expanduser()
    if _target_exists(target) and not args.force:
        stderr.write("Die Zieldatei existiert bereits; nutze --force zum Ersetzen.\n")
        return 1
    if not target.parent.is_dir():
        stderr.write("Das Zielverzeichnis existiert nicht.\n")
        return 1

    operation = diagnostics_operation("download", **_detail_parameters(args))
    url = f"{config.base_url}{operation.path_template}?disposition=attachment"
    try:
        status, payload = http_bytes(
            "GET",
            url,
            headers=_headers(config),
            max_bytes=_MAX_SUBMISSION_DOWNLOAD_BYTES,
        )
    except ValueError:
        stderr.write("API-Fehler: Die Abgabedatei überschreitet das sichere Größenlimit.\n")
        return 1
    if status != 200:
        stderr.write(f"API-Fehler ({status}): Dateidownload fehlgeschlagen.\n")
        return 1
    try:
        _write_private_download(target, payload, force=bool(args.force))
    except FileExistsError:
        stderr.write("Die Zieldatei existiert bereits; nutze --force zum Ersetzen.\n")
        return 1
    except OSError as exc:
        stderr.write(f"Datei konnte nicht sicher gespeichert werden ({exc.__class__.__name__}).\n")
        return 1
    stdout.write(f"Gespeichert: {_terminal_text(target)} ({len(payload)} Bytes)\n")
    return 0


def run_diagnostics_command(
    args: argparse.Namespace,
    *,
    http_json: JsonRequest,
    http_bytes: BytesRequest,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    """Execute one parsed diagnostics command against configured HTTPS APIs."""

    config = _config_or_error(stderr)
    if config is None:
        return 1
    if args.command == "course":
        return _run_course(args, config, http_json=http_json, stdout=stdout, stderr=stderr)
    if args.command == "unit":
        return _run_unit(args, config, http_json=http_json, stdout=stdout, stderr=stderr)
    if args.command == "student":
        return _run_student(args, config, http_json=http_json, stdout=stdout, stderr=stderr)
    if args.command == "submission":
        return _run_submission(args, config, http_json=http_json, stdout=stdout, stderr=stderr)
    if args.command == "download":
        return _run_download(args, config, http_bytes=http_bytes, stdout=stdout, stderr=stderr)
    return 2
