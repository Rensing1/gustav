from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import mimetypes
import sys
from pathlib import Path
from typing import Any, TextIO
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from uuid import uuid4

from backend.teaching.services.tasks import normalize_dialog_config

from .config import GustavCLIConfig, load_config, save_config
from .course_commands import register_course_parsers, run_course_command


def _parse_json_response(raw: str, *, non_json_body: dict[str, object]) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return non_json_body


def _body_preview(raw: str, *, limit: int = 200) -> str:
    return raw.strip().replace("\n", " ")[:limit]


def _http_json(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    json_body: object | None = None,
) -> tuple[int, Any]:
    body = None
    merged_headers = dict(headers or {})
    if json_body is not None:
        body = json.dumps(json_body).encode("utf-8")
        merged_headers["Content-Type"] = "application/json"
    req = urllib_request.Request(url, data=body, method=method, headers=merged_headers)
    try:
        with urllib_request.urlopen(req, timeout=20) as response:  # noqa: S310 - URL comes from local CLI config.
            raw = response.read().decode("utf-8", errors="replace")
            body = _parse_json_response(raw, non_json_body={"raw": _body_preview(raw)})
            return response.status, body
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        body = _parse_json_response(
            raw,
            non_json_body={
                "error": "http_error",
                "detail": str(exc.reason),
                "body_preview": _body_preview(raw),
            },
        )
        return exc.code, body
    except URLError as exc:
        return 0, {"error": "network_error", "detail": str(exc.reason)}


def _http_bytes(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    data: bytes | None = None,
) -> tuple[int, bytes]:
    req = urllib_request.Request(url, data=data, method=method, headers=dict(headers or {}))
    try:
        with urllib_request.urlopen(req, timeout=60) as response:  # noqa: S310 - URL comes from API/config.
            return response.status, response.read()
    except HTTPError as exc:
        return exc.code, exc.read()
    except URLError as exc:
        return 0, str(exc.reason).encode("utf-8", errors="replace")


def _safe_multipart_parameter(value: str) -> str:
    """Return a quoted multipart parameter value without header-breaking characters."""

    safe = (
        str(value or "")
        .replace("\r\n", "_")
        .replace("\r", "_")
        .replace("\n", "_")
        .replace("\\", "_")
        .replace('"', "_")
    )
    return safe.strip() or "upload"


def _http_multipart(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    field_name: str,
    filename: str,
    content: bytes,
    content_type: str,
) -> tuple[int, Any]:
    boundary = f"gustav-{uuid4().hex}"
    safe_field_name = _safe_multipart_parameter(field_name)
    safe_filename = _safe_multipart_parameter(filename)
    body = b"".join(
        [
            f"--{boundary}\r\n".encode("utf-8"),
            (
                f'Content-Disposition: form-data; name="{safe_field_name}"; '
                f'filename="{safe_filename}"\r\n'
            ).encode("utf-8"),
            f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"),
            content,
            f"\r\n--{boundary}--\r\n".encode("utf-8"),
        ]
    )
    merged_headers = dict(headers or {})
    merged_headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    status, raw = _http_bytes(method, url, headers=merged_headers, data=body)
    parsed = _parse_json_response(
        raw.decode("utf-8", errors="replace"),
        non_json_body={"raw": _body_preview(raw.decode("utf-8", errors="replace"))},
    )
    return status, parsed


def _redact_token(token: str) -> str:
    if len(token) <= 10:
        return "********"
    return f"{token[:6]}…{token[-4:]}"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gustav")
    sub = parser.add_subparsers(dest="group", required=True)

    auth = sub.add_parser("auth")
    auth_sub = auth.add_subparsers(dest="command", required=True)
    configure = auth_sub.add_parser("configure")
    configure.add_argument("--base-url", required=True)
    configure.add_argument("--token-stdin", action="store_true")
    auth_sub.add_parser("status")

    units = sub.add_parser("units")
    units_sub = units.add_subparsers(dest="command", required=True)
    units_list = units_sub.add_parser("list")
    units_list.add_argument("--json", action="store_true")
    units_create = units_sub.add_parser("create")
    units_create.add_argument("--title", required=True)
    units_create.add_argument("--description", default=None)
    units_create.add_argument("--unit-type", choices=("linear", "modular"))
    units_create.add_argument("--json", action="store_true")
    units_edit = units_sub.add_parser("edit")
    units_edit.add_argument("unit_id")
    units_edit.add_argument("--title")
    units_edit.add_argument("--description")
    units_edit.add_argument("--json", action="store_true")
    units_delete = units_sub.add_parser("delete")
    units_delete.add_argument("unit_id")
    units_delete.add_argument("--yes", action="store_true")

    sections = sub.add_parser("sections")
    sections_sub = sections.add_subparsers(dest="command", required=True)
    for name in ("list", "create", "edit", "delete", "reorder"):
        section_cmd = sections_sub.add_parser(name)
        if name in {"list", "create", "reorder"}:
            section_cmd.add_argument("--unit-id", required=True)
        if name in {"edit", "delete"}:
            section_cmd.add_argument("section_id")
            section_cmd.add_argument("--unit-id", required=True)
        if name in {"create", "edit"}:
            section_cmd.add_argument("--title", required=True)
        if name == "delete":
            section_cmd.add_argument("--yes", action="store_true")
        if name == "reorder":
            section_cmd.add_argument("--ids", nargs="+", required=True)
        if name == "list":
            section_cmd.add_argument("--json", action="store_true")

    phases = sub.add_parser("phases")
    phases_sub = phases.add_subparsers(dest="command", required=True)
    for name in ("list", "create", "edit", "delete", "reorder"):
        phase_cmd = phases_sub.add_parser(name)
        if name in {"list", "create", "reorder"}:
            phase_cmd.add_argument("--unit-id", required=True)
        if name in {"edit", "delete"}:
            phase_cmd.add_argument("phase_id")
            phase_cmd.add_argument("--unit-id", required=True)
        if name in {"create", "edit"}:
            phase_cmd.add_argument("--title", required=True)
        if name == "delete":
            phase_cmd.add_argument("--yes", action="store_true")
        if name == "reorder":
            phase_cmd.add_argument("--ids", nargs="+", required=True)
        if name == "list":
            phase_cmd.add_argument("--json", action="store_true")

    modules = sub.add_parser("modules")
    modules_sub = modules.add_subparsers(dest="command", required=True)
    modules_list = modules_sub.add_parser("list")
    modules_list.add_argument("--unit-id", required=True)
    modules_list.add_argument("--json", action="store_true")
    modules_create = modules_sub.add_parser("create")
    modules_create.add_argument("--unit-id", required=True)
    modules_create.add_argument("--phase-id", required=True)
    modules_create.add_argument("--title", required=True)
    modules_create.add_argument("--module-kind", choices=["learning", "practice"], default="learning")
    modules_edit = modules_sub.add_parser("edit")
    modules_edit.add_argument("module_id")
    modules_edit.add_argument("--unit-id", required=True)
    modules_edit.add_argument("--title")
    modules_edit.add_argument("--required-prereq-count", type=int)
    modules_delete = modules_sub.add_parser("delete")
    modules_delete.add_argument("module_id")
    modules_delete.add_argument("--unit-id", required=True)
    modules_delete.add_argument("--yes", action="store_true")
    modules_reorder = modules_sub.add_parser("reorder")
    modules_reorder.add_argument("--unit-id", required=True)
    modules_reorder.add_argument("--phase-id", required=True)
    modules_reorder.add_argument("--ids", nargs="+", required=True)

    module_edges = sub.add_parser("module-edges")
    module_edges_sub = module_edges.add_subparsers(dest="command", required=True)
    edge_create = module_edges_sub.add_parser("create")
    edge_create.add_argument("--unit-id", required=True)
    edge_create.add_argument("--from", dest="from_module_id", required=True)
    edge_create.add_argument("--to", dest="to_module_id", required=True)
    edge_delete = module_edges_sub.add_parser("delete")
    edge_delete.add_argument("--unit-id", required=True)
    edge_delete.add_argument("--from", dest="from_module_id", required=True)
    edge_delete.add_argument("--to", dest="to_module_id", required=True)
    edge_delete.add_argument("--yes", action="store_true")

    materials = sub.add_parser("materials")
    materials_sub = materials.add_subparsers(dest="command", required=True)
    for name in ("list", "create", "edit", "delete", "reorder", "upload", "download"):
        material_cmd = materials_sub.add_parser(name)
        material_cmd.add_argument("--unit-id", required=True)
        target = material_cmd.add_mutually_exclusive_group(required=True)
        target.add_argument("--section-id")
        target.add_argument("--module-id")
        if name in {"edit", "delete", "download"}:
            material_cmd.add_argument("material_id")
        if name == "create":
            material_cmd.add_argument("--title", required=True)
            material_cmd.add_argument("--body-md", required=True)
        if name == "upload":
            material_cmd.add_argument("--file", required=True)
            material_cmd.add_argument("--title", required=True)
            material_cmd.add_argument("--mime-type")
            material_cmd.add_argument("--alt-text")
            material_cmd.add_argument("--kind", choices=("file", "simulation"), default="file")
            material_cmd.add_argument("--body-md")
            material_cmd.add_argument("--json", action="store_true")
        if name == "edit":
            material_cmd.add_argument("--title")
            material_cmd.add_argument("--body-md")
            material_cmd.add_argument("--alt-text")
        if name == "download":
            material_cmd.add_argument("--output", required=True)
            material_cmd.add_argument("--force", action="store_true")
        if name == "delete":
            material_cmd.add_argument("--yes", action="store_true")
        if name == "reorder":
            material_cmd.add_argument("--ids", nargs="+", required=True)
        if name == "list":
            material_cmd.add_argument("--json", action="store_true")

    tasks = sub.add_parser("tasks")
    tasks_sub = tasks.add_subparsers(dest="command", required=True)
    for name in ("list", "create", "edit", "delete", "reorder"):
        task_cmd = tasks_sub.add_parser(name)
        task_cmd.add_argument("--unit-id", required=True)
        target = task_cmd.add_mutually_exclusive_group(required=True)
        target.add_argument("--section-id")
        target.add_argument("--module-id")
        if name in {"edit", "delete"}:
            task_cmd.add_argument("task_id")
        if name == "create":
            task_cmd.add_argument("--instruction-md", required=True)
        if name == "edit":
            task_cmd.add_argument("--instruction-md")
        if name in {"create", "edit"}:
            if name == "edit":
                criteria = task_cmd.add_mutually_exclusive_group()
                criteria.add_argument("--criterion", action="append", dest="criteria")
                criteria.add_argument("--clear-criteria", action="store_true")
                teacher_context = task_cmd.add_mutually_exclusive_group()
                teacher_context.add_argument("--teacher-context-md")
                teacher_context.add_argument("--clear-teacher-context", action="store_true")
                model_solution = task_cmd.add_mutually_exclusive_group()
                model_solution.add_argument("--model-solution-md")
                model_solution.add_argument("--clear-model-solution", action="store_true")
                due_at = task_cmd.add_mutually_exclusive_group()
                due_at.add_argument("--due-at")
                due_at.add_argument("--clear-due-at", action="store_true")
                max_attempts = task_cmd.add_mutually_exclusive_group()
                max_attempts.add_argument("--max-attempts", type=int)
                max_attempts.add_argument("--clear-max-attempts", action="store_true")
            else:
                task_cmd.add_argument("--criterion", action="append", dest="criteria")
                task_cmd.add_argument("--teacher-context-md")
                task_cmd.add_argument("--model-solution-md")
                task_cmd.add_argument("--due-at")
                task_cmd.add_argument("--max-attempts", type=int)
            task_cmd.add_argument(
                "--kind",
                choices=["native", "h5p", "visual", "scratch", "calliope", "filius", "dialog"],
                default="native" if name == "create" else None,
            )
            task_cmd.add_argument("--dialog-config")
        if name == "delete":
            task_cmd.add_argument("--yes", action="store_true")
        if name == "reorder":
            task_cmd.add_argument("--ids", nargs="+", required=True)
        if name == "list":
            task_cmd.add_argument("--json", action="store_true")

    h5p = sub.add_parser("h5p")
    h5p_sub = h5p.add_subparsers(dest="command", required=True)
    for name in ("import", "export", "reset"):
        h5p_cmd = h5p_sub.add_parser(name)
        h5p_cmd.add_argument("--unit-id", required=True)
        target = h5p_cmd.add_mutually_exclusive_group(required=True)
        target.add_argument("--section-id")
        target.add_argument("--module-id")
        h5p_cmd.add_argument("--task-id", required=True)
        if name == "import":
            h5p_cmd.add_argument("--file", required=True)
            h5p_cmd.add_argument("--json", action="store_true")
        if name == "export":
            h5p_cmd.add_argument("--output", required=True)
            h5p_cmd.add_argument("--force", action="store_true")
        if name == "reset":
            h5p_cmd.add_argument("--yes", action="store_true")
    register_course_parsers(sub)
    return parser


def _configure(args: argparse.Namespace, *, stdin: TextIO, stdout: TextIO, stderr: TextIO) -> int:
    parsed_base_url = urlparse(str(args.base_url or ""))
    if parsed_base_url.scheme != "https" or not parsed_base_url.netloc:
        stderr.write("Die Base-URL muss mit https:// beginnen.\n")
        return 2
    token = stdin.readline().strip() if args.token_stdin else getpass.getpass("CLI-Token: ")
    save_config(GustavCLIConfig(base_url=args.base_url, token=token))
    stdout.write("GUSTAV CLI konfiguriert.\n")
    return 0


def _status(*, stdout: TextIO, stderr: TextIO) -> int:
    try:
        cfg = load_config()
    except FileNotFoundError:
        stderr.write("GUSTAV CLI ist noch nicht konfiguriert.\n")
        return 1
    stdout.write(f"Base URL: {cfg.base_url}\n")
    stdout.write(f"Token: {_redact_token(cfg.token)}\n")
    return 0


def _units_list(args: argparse.Namespace, *, stdout: TextIO, stderr: TextIO) -> int:
    try:
        cfg = load_config()
    except FileNotFoundError:
        stderr.write("GUSTAV CLI ist noch nicht konfiguriert.\n")
        return 1
    status, body = _http_json(
        "GET",
        f"{cfg.base_url}/api/teaching/units",
        headers={"Authorization": f"Bearer {cfg.token}"},
    )
    if status != 200:
        stderr.write(f"API-Fehler ({status}): {body}\n")
        return 1
    if args.json:
        stdout.write(json.dumps(body, ensure_ascii=False))
        stdout.write("\n")
        return 0
    for item in body or []:
        stdout.write(f"{item.get('id', '')}\t{item.get('title', '')}\n")
    return 0


def _load_config_or_error(stderr: TextIO) -> GustavCLIConfig | None:
    try:
        return load_config()
    except FileNotFoundError:
        stderr.write("GUSTAV CLI ist noch nicht konfiguriert.\n")
        return None


def _print_body(body: object, *, as_json: bool, stdout: TextIO) -> None:
    if as_json:
        stdout.write(json.dumps(body, ensure_ascii=False))
        stdout.write("\n")
        return
    if isinstance(body, list):
        for item in body:
            if isinstance(item, dict):
                identity = item.get("id") or item.get("sub") or item.get("job_id") or ""
                label = (
                    item.get("title")
                    or item.get("instruction_md")
                    or item.get("name")
                    or item.get("label")
                    or item.get("status")
                    or ""
                )
                stdout.write(f"{identity}\t{label}\n")
        return
    if isinstance(body, dict):
        identity = body.get("id") or body.get("sub") or body.get("job_id") or ""
        label = body.get("title") or body.get("name") or body.get("status") or ""
        stdout.write(f"{identity}\t{label}\n")


def _auth_headers(cfg: GustavCLIConfig) -> dict[str, str]:
    return {"Authorization": f"Bearer {cfg.token}"}


def _request_configured(
    *,
    method: str,
    path: str,
    json_body: object | None,
    success: set[int],
    stdout: TextIO,
    stderr: TextIO,
    as_json: bool = False,
) -> int:
    cfg = _load_config_or_error(stderr)
    if cfg is None:
        return 1
    status, body = _http_json(
        method,
        f"{cfg.base_url}{path}",
        headers=_auth_headers(cfg),
        json_body=json_body,
    )
    if status not in success:
        stderr.write(f"API-Fehler ({status}): {body}\n")
        return 1
    if status == 204:
        stdout.write("null\n" if as_json else "Gelöscht.\n")
        return 0
    _print_body(body, as_json=as_json, stdout=stdout)
    return 0


def _units_create(args: argparse.Namespace, *, stdout: TextIO, stderr: TextIO) -> int:
    cfg = _load_config_or_error(stderr)
    if cfg is None:
        return 1
    payload: dict[str, object] = {"title": args.title}
    if args.unit_type is not None:
        payload["unit_type"] = args.unit_type
    if args.description is not None:
        payload["summary"] = args.description
    status, body = _http_json(
        "POST",
        f"{cfg.base_url}/api/teaching/units",
        headers={"Authorization": f"Bearer {cfg.token}"},
        json_body=payload,
    )
    if status != 201:
        stderr.write(f"API-Fehler ({status}): {body}\n")
        return 1
    _print_body(body, as_json=args.json, stdout=stdout)
    return 0


def _units_edit(args: argparse.Namespace, *, stdout: TextIO, stderr: TextIO) -> int:
    cfg = _load_config_or_error(stderr)
    if cfg is None:
        return 1
    payload: dict[str, object] = {}
    if args.title is not None:
        payload["title"] = args.title
    if args.description is not None:
        payload["summary"] = args.description
    if not payload:
        stderr.write("Mindestens --title oder --description ist erforderlich.\n")
        return 1
    status, body = _http_json(
        "PATCH",
        f"{cfg.base_url}/api/teaching/units/{args.unit_id}",
        headers={"Authorization": f"Bearer {cfg.token}"},
        json_body=payload,
    )
    if status != 200:
        stderr.write(f"API-Fehler ({status}): {body}\n")
        return 1
    _print_body(body, as_json=args.json, stdout=stdout)
    return 0


def _units_delete(args: argparse.Namespace, *, stdout: TextIO, stderr: TextIO) -> int:
    if not args.yes:
        stderr.write("Löschen erfordert --yes.\n")
        return 1
    cfg = _load_config_or_error(stderr)
    if cfg is None:
        return 1
    status, body = _http_json(
        "DELETE",
        f"{cfg.base_url}/api/teaching/units/{args.unit_id}",
        headers={"Authorization": f"Bearer {cfg.token}"},
    )
    if status != 204:
        stderr.write(f"API-Fehler ({status}): {body}\n")
        return 1
    stdout.write("Gelöscht.\n")
    return 0


def _sections(args: argparse.Namespace, *, stdout: TextIO, stderr: TextIO) -> int:
    base = f"/api/teaching/units/{args.unit_id}/sections"
    if args.command == "list":
        return _request_configured(method="GET", path=base, json_body=None, success={200}, stdout=stdout, stderr=stderr, as_json=args.json)
    if args.command == "create":
        return _request_configured(method="POST", path=base, json_body={"title": args.title}, success={201}, stdout=stdout, stderr=stderr)
    if args.command == "edit":
        return _request_configured(method="PATCH", path=f"{base}/{args.section_id}", json_body={"title": args.title}, success={200}, stdout=stdout, stderr=stderr)
    if args.command == "delete":
        if not args.yes:
            stderr.write("Löschen erfordert --yes.\n")
            return 1
        return _request_configured(method="DELETE", path=f"{base}/{args.section_id}", json_body=None, success={204}, stdout=stdout, stderr=stderr)
    if args.command == "reorder":
        return _request_configured(method="POST", path=f"{base}/reorder", json_body={"section_ids": args.ids}, success={200}, stdout=stdout, stderr=stderr)
    return 2


def _phases(args: argparse.Namespace, *, stdout: TextIO, stderr: TextIO) -> int:
    base = f"/api/teaching/units/{args.unit_id}/phases"
    if args.command == "list":
        return _request_configured(method="GET", path=base, json_body=None, success={200}, stdout=stdout, stderr=stderr, as_json=args.json)
    if args.command == "create":
        return _request_configured(method="POST", path=base, json_body={"title": args.title}, success={201}, stdout=stdout, stderr=stderr)
    if args.command == "edit":
        return _request_configured(method="PATCH", path=f"{base}/{args.phase_id}", json_body={"title": args.title}, success={200}, stdout=stdout, stderr=stderr)
    if args.command == "delete":
        if not args.yes:
            stderr.write("Löschen erfordert --yes.\n")
            return 1
        return _request_configured(method="DELETE", path=f"{base}/{args.phase_id}", json_body=None, success={204}, stdout=stdout, stderr=stderr)
    if args.command == "reorder":
        return _request_configured(method="POST", path=f"{base}/reorder", json_body={"phase_ids": args.ids}, success={200}, stdout=stdout, stderr=stderr)
    return 2


def _module_edges(args: argparse.Namespace, *, stdout: TextIO, stderr: TextIO) -> int:
    if args.command == "delete" and not args.yes:
        stderr.write("Löschen erfordert --yes.\n")
        return 1
    if args.command == "create":
        return _request_configured(
            method="POST",
            path=f"/api/teaching/units/{args.unit_id}/modules/edges",
            json_body={"from_module_id": args.from_module_id, "to_module_id": args.to_module_id},
            success={201},
            stdout=stdout,
            stderr=stderr,
        )
    if args.command == "delete":
        return _request_configured(
            method="DELETE",
            path=f"/api/teaching/units/{args.unit_id}/modules/{args.from_module_id}/edges/{args.to_module_id}",
            json_body=None,
            success={204},
            stdout=stdout,
            stderr=stderr,
        )
    return 2


def _modules(args: argparse.Namespace, *, stdout: TextIO, stderr: TextIO) -> int:
    base = f"/api/teaching/units/{args.unit_id}/modules"
    if args.command == "list":
        cfg = _load_config_or_error(stderr)
        if cfg is None:
            return 1
        status, body = _http_json(
            "GET",
            f"{cfg.base_url}{base}/graph",
            headers=_auth_headers(cfg),
        )
        if status != 200:
            stderr.write(f"API-Fehler ({status}): {body}\n")
            return 1
        if args.json:
            _print_body(body, as_json=True, stdout=stdout)
        else:
            _print_module_graph(body, stdout=stdout)
        return 0
    if args.command == "create":
        return _request_configured(
            method="POST",
            path=base,
            json_body={"phase_id": args.phase_id, "title": args.title, "module_kind": args.module_kind},
            success={201},
            stdout=stdout,
            stderr=stderr,
        )
    if args.command == "edit":
        payload: dict[str, object] = {}
        if args.title is not None:
            payload["title"] = args.title
        if args.required_prereq_count is not None:
            payload["required_prereq_count"] = args.required_prereq_count
        if not payload:
            stderr.write("Mindestens --title oder --required-prereq-count ist erforderlich.\n")
            return 1
        return _request_configured(
            method="PATCH",
            path=f"{base}/{args.module_id}",
            json_body=payload,
            success={200},
            stdout=stdout,
            stderr=stderr,
        )
    if args.command == "delete":
        if not args.yes:
            stderr.write("Löschen erfordert --yes.\n")
            return 1
        return _request_configured(
            method="DELETE",
            path=f"{base}/{args.module_id}",
            json_body=None,
            success={204},
            stdout=stdout,
            stderr=stderr,
        )
    if args.command == "reorder":
        return _request_configured(
            method="POST",
            path=f"/api/teaching/units/{args.unit_id}/phases/{args.phase_id}/modules/reorder",
            json_body={"module_ids": args.ids},
            success={200},
            stdout=stdout,
            stderr=stderr,
        )
    return 2


def _resolve_section_id(cfg: GustavCLIConfig, args: argparse.Namespace, *, stderr: TextIO) -> str | None:
    if args.section_id:
        return args.section_id
    status, body = _http_json(
        "GET",
        f"{cfg.base_url}/api/teaching/units/{args.unit_id}/modules/{args.module_id}/content-target",
        headers=_auth_headers(cfg),
    )
    if status != 200 or not isinstance(body, dict) or not body.get("section_id"):
        stderr.write(f"API-Fehler ({status}): {body}\n")
        return None
    return str(body["section_id"])


def _content_base(resource: str, args: argparse.Namespace, *, stderr: TextIO) -> tuple[GustavCLIConfig, str] | None:
    cfg = _load_config_or_error(stderr)
    if cfg is None:
        return None
    section_id = _resolve_section_id(cfg, args, stderr=stderr)
    if section_id is None:
        return None
    return cfg, f"/api/teaching/units/{args.unit_id}/sections/{section_id}/{resource}"


def _authoring_resource_base(
    resource: str,
    args: argparse.Namespace,
    *,
    module_direct_commands: set[str],
    stderr: TextIO,
) -> tuple[GustavCLIConfig, str] | None:
    cfg = _load_config_or_error(stderr)
    if cfg is None:
        return None
    if args.module_id and args.command in module_direct_commands:
        return cfg, f"/api/teaching/units/{args.unit_id}/modules/{args.module_id}/{resource}"
    section_id = _resolve_section_id(cfg, args, stderr=stderr)
    if section_id is None:
        return None
    return cfg, f"/api/teaching/units/{args.unit_id}/sections/{section_id}/{resource}"


def _request_with_config(
    cfg: GustavCLIConfig,
    *,
    method: str,
    path: str,
    json_body: object | None,
    success: set[int],
    stdout: TextIO,
    stderr: TextIO,
    as_json: bool = False,
) -> int:
    status, body = _http_json(
        method,
        f"{cfg.base_url}{path}",
        headers=_auth_headers(cfg),
        json_body=json_body,
    )
    if status not in success:
        stderr.write(f"API-Fehler ({status}): {body}\n")
        return 1
    if status == 204:
        stdout.write("null\n" if as_json else "Gelöscht.\n")
        return 0
    _print_body(body, as_json=as_json, stdout=stdout)
    return 0


def _materials(args: argparse.Namespace, *, stdout: TextIO, stderr: TextIO) -> int:
    if args.command == "download":
        output = Path(args.output)
        if output.exists() and not args.force:
            stderr.write("Zieldatei existiert bereits; Überschreiben erfordert --force.\n")
            return 1
    resolved = _authoring_resource_base(
        "materials",
        args,
        module_direct_commands={"create", "upload", "edit", "delete", "reorder"},
        stderr=stderr,
    )
    if resolved is None:
        return 1
    cfg, base = resolved
    if args.command == "list":
        return _request_with_config(cfg, method="GET", path=base, json_body=None, success={200}, stdout=stdout, stderr=stderr, as_json=args.json)
    if args.command == "create":
        return _request_with_config(
            cfg,
            method="POST",
            path=base,
            json_body={"title": args.title, "body_md": args.body_md},
            success={201},
            stdout=stdout,
            stderr=stderr,
        )
    if args.command == "upload":
        source = Path(args.file)
        if not source.is_file():
            stderr.write("Die angegebene Datei existiert nicht.\n")
            return 1
        content = source.read_bytes()
        if args.kind == "simulation" and args.alt_text is not None:
            stderr.write("--alt-text ist nur für Datei-Materialien zulässig.\n")
            return 1
        mime_type = (
            "text/html"
            if args.kind == "simulation" and args.mime_type is None
            else args.mime_type or mimetypes.guess_type(str(source))[0] or "application/octet-stream"
        )
        intent_payload: dict[str, object] = {
            "filename": source.name,
            "mime_type": mime_type,
            "size_bytes": len(content),
        }
        if args.kind == "simulation":
            intent_payload["kind"] = "simulation"
        status, intent = _http_json(
            "POST",
            f"{cfg.base_url}{base}/upload-intents",
            headers=_auth_headers(cfg),
            json_body=intent_payload,
        )
        if status != 200 or not isinstance(intent, dict):
            stderr.write(f"API-Fehler ({status}): {intent}\n")
            return 1
        upload_headers = {str(k): str(v) for k, v in dict(intent.get("headers") or {}).items()}
        upload_url = str(intent.get("url") or "")
        upload_status, upload_body = _http_bytes("PUT", upload_url, headers=upload_headers, data=content)
        if upload_status < 200 or upload_status >= 300:
            stderr.write(f"Upload-Fehler ({upload_status}): {_body_preview(upload_body.decode('utf-8', errors='replace'))}\n")
            return 1
        finalize_payload: dict[str, object] = {
            "intent_id": str(intent.get("intent_id") or ""),
            "title": args.title,
            "sha256": hashlib.sha256(content).hexdigest(),
        }
        if args.alt_text is not None:
            finalize_payload["alt_text"] = args.alt_text
        if args.kind == "simulation" and args.body_md is not None:
            finalize_payload["body_md"] = args.body_md
        return _request_with_config(
            cfg,
            method="POST",
            path=f"{base}/finalize",
            json_body=finalize_payload,
            success={200, 201},
            stdout=stdout,
            stderr=stderr,
            as_json=args.json,
        )
    if args.command == "edit":
        payload: dict[str, object | None] = {}
        if args.title is not None:
            payload["title"] = args.title
        if args.body_md is not None:
            payload["body_md"] = args.body_md
        if args.alt_text is not None:
            payload["alt_text"] = args.alt_text
        if not payload:
            stderr.write("Mindestens --title, --body-md oder --alt-text ist erforderlich.\n")
            return 1
        return _request_with_config(
            cfg,
            method="PATCH",
            path=f"{base}/{args.material_id}",
            json_body=payload,
            success={200},
            stdout=stdout,
            stderr=stderr,
        )
    if args.command == "delete":
        if not args.yes:
            stderr.write("Löschen erfordert --yes.\n")
            return 1
        return _request_with_config(
            cfg,
            method="DELETE",
            path=f"{base}/{args.material_id}",
            json_body=None,
            success={204},
            stdout=stdout,
            stderr=stderr,
        )
    if args.command == "reorder":
        return _request_with_config(
            cfg,
            method="POST",
            path=f"{base}/reorder",
            json_body={"material_ids": args.ids},
            success={200},
            stdout=stdout,
            stderr=stderr,
        )
    if args.command == "download":
        status, body = _http_json(
            "GET",
            f"{cfg.base_url}{base}/{args.material_id}/download-url?disposition=attachment",
            headers=_auth_headers(cfg),
        )
        if status != 200 or not isinstance(body, dict):
            stderr.write(f"API-Fehler ({status}): {body}\n")
            return 1
        download_status, content = _http_bytes("GET", str(body.get("url") or ""))
        if download_status < 200 or download_status >= 300:
            stderr.write(f"Download-Fehler ({download_status}): {_body_preview(content.decode('utf-8', errors='replace'))}\n")
            return 1
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(content)
        stdout.write(f"Gespeichert: {output}\n")
        return 0
    return 2


def _print_module_graph(body: object, *, stdout: TextIO) -> None:
    """Render the modular graph without losing phases or dependency edges."""

    if not isinstance(body, dict):
        stdout.write("Keine Phasen, Module oder Kanten.\n")
        return
    phases = [item for item in body.get("phases", []) if isinstance(item, dict)]
    modules = [item for item in body.get("modules", []) if isinstance(item, dict)]
    edges = [item for item in body.get("edges", []) if isinstance(item, dict)]
    if not phases and not modules and not edges:
        stdout.write("Keine Phasen, Module oder Kanten.\n")
        return
    for phase in sorted(phases, key=lambda item: (int(item.get("position") or 0), str(item.get("id") or ""))):
        stdout.write(
            f"PHASE\t{phase.get('position', '')}\t{phase.get('id', '')}\t{phase.get('title', '')}\n"
        )
    for module in sorted(
        modules,
        key=lambda item: (int(item.get("position") or 0), str(item.get("id") or "")),
    ):
        stdout.write(
            "MODULE\t"
            f"{module.get('position', '')}\t{module.get('id', '')}\t"
            f"{module.get('phase_id', '')}\t{module.get('module_kind', 'learning')}\t"
            f"{module.get('title', '')}\t"
            f"{module.get('required_prereq_count', 0)}\n"
        )
    for edge in sorted(
        edges,
        key=lambda item: (str(item.get("from_module_id") or ""), str(item.get("to_module_id") or "")),
    ):
        stdout.write(f"EDGE\t{edge.get('from_module_id', '')}\t{edge.get('to_module_id', '')}\n")


def _apply_task_kind_payload(
    payload: dict[str, object],
    kind: str | None,
    *,
    partial: bool,
    dialog_config: dict[str, object] | None = None,
) -> None:
    if kind is None:
        return
    if kind == "native":
        if partial:
            payload["h5p"] = None
        return
    if kind == "h5p":
        payload["h5p"] = {"content_id": None, "display_options": {}}
        return
    if kind == "dialog":
        if dialog_config is not None:
            payload["dialog"] = dialog_config
        return
    payload[kind] = {}


def _task_payload(
    args: argparse.Namespace,
    *,
    partial: bool,
    dialog_config: dict[str, object] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {}
    if getattr(args, "instruction_md", None) is not None:
        payload["instruction_md"] = args.instruction_md
    if getattr(args, "criteria", None) is not None:
        payload["criteria"] = args.criteria
    if getattr(args, "teacher_context_md", None) is not None:
        payload["teacher_context_md"] = args.teacher_context_md
    if getattr(args, "model_solution_md", None) is not None:
        payload["model_solution_md"] = args.model_solution_md
    if getattr(args, "due_at", None) is not None:
        payload["due_at"] = args.due_at
    if getattr(args, "max_attempts", None) is not None:
        payload["max_attempts"] = args.max_attempts
    if partial and getattr(args, "clear_criteria", False):
        payload["criteria"] = []
    if partial and getattr(args, "clear_teacher_context", False):
        payload["teacher_context_md"] = None
    if partial and getattr(args, "clear_model_solution", False):
        payload["model_solution_md"] = None
    if partial and getattr(args, "clear_due_at", False):
        payload["due_at"] = None
    if partial and getattr(args, "clear_max_attempts", False):
        payload["max_attempts"] = None
    _apply_task_kind_payload(
        payload,
        getattr(args, "kind", None),
        partial=partial,
        dialog_config=dialog_config,
    )
    if not partial and "instruction_md" not in payload:
        payload["instruction_md"] = args.instruction_md
    return payload


def _tasks(args: argparse.Namespace, *, stdout: TextIO, stderr: TextIO) -> int:
    dialog_path = getattr(args, "dialog_config", None)
    kind = getattr(args, "kind", None)
    if (kind == "dialog") != (dialog_path is not None):
        stderr.write("--kind dialog und --dialog-config müssen gemeinsam verwendet werden.\n")
        return 1
    dialog_config: dict[str, object] | None = None
    if dialog_path is not None:
        source = Path(dialog_path)
        if not source.is_file():
            stderr.write("Die angegebene Dialog-Konfiguration existiert nicht.\n")
            return 1
        try:
            raw_dialog = json.loads(source.read_text(encoding="utf-8"))
            dialog_config = normalize_dialog_config(raw_dialog)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
            stderr.write("Die Dialog-Konfiguration ist ungültig.\n")
            return 1
    resolved = _authoring_resource_base(
        "tasks",
        args,
        module_direct_commands={"create", "edit", "delete", "reorder"},
        stderr=stderr,
    )
    if resolved is None:
        return 1
    cfg, base = resolved
    if args.command == "list":
        return _request_with_config(cfg, method="GET", path=base, json_body=None, success={200}, stdout=stdout, stderr=stderr, as_json=args.json)
    if args.command == "create":
        return _request_with_config(
            cfg,
            method="POST",
            path=base,
            json_body=_task_payload(args, partial=False, dialog_config=dialog_config),
            success={201},
            stdout=stdout,
            stderr=stderr,
        )
    if args.command == "edit":
        payload = _task_payload(args, partial=True, dialog_config=dialog_config)
        if not payload:
            stderr.write("Mindestens ein Aufgabenfeld ist erforderlich.\n")
            return 1
        return _request_with_config(
            cfg,
            method="PATCH",
            path=f"{base}/{args.task_id}",
            json_body=payload,
            success={200},
            stdout=stdout,
            stderr=stderr,
        )
    if args.command == "delete":
        if not args.yes:
            stderr.write("Löschen erfordert --yes.\n")
            return 1
        return _request_with_config(
            cfg,
            method="DELETE",
            path=f"{base}/{args.task_id}",
            json_body=None,
            success={204},
            stdout=stdout,
            stderr=stderr,
        )
    if args.command == "reorder":
        return _request_with_config(
            cfg,
            method="POST",
            path=f"{base}/reorder",
            json_body={"task_ids": args.ids},
            success={200},
            stdout=stdout,
            stderr=stderr,
        )
    return 2


def _h5p(args: argparse.Namespace, *, stdout: TextIO, stderr: TextIO) -> int:
    if args.command == "export":
        output = Path(args.output)
        if output.exists() and not args.force:
            stderr.write("Zieldatei existiert bereits; Überschreiben erfordert --force.\n")
            return 1
    if args.command == "reset" and not args.yes:
        stderr.write("Zurücksetzen erfordert --yes.\n")
        return 1
    cfg = _load_config_or_error(stderr)
    if cfg is None:
        return 1
    if args.module_id and args.command in {"import", "reset"}:
        base = f"/api/teaching/units/{args.unit_id}/modules/{args.module_id}/tasks"
    else:
        section_id = _resolve_section_id(cfg, args, stderr=stderr)
        if section_id is None:
            return 1
        base = f"/api/teaching/units/{args.unit_id}/sections/{section_id}/tasks"
    h5p_base = f"{base}/{args.task_id}/h5p"
    if args.command == "import":
        source = Path(args.file)
        if not source.is_file():
            stderr.write("Die angegebene H5P-Datei existiert nicht.\n")
            return 1
        status, body = _http_multipart(
            "POST",
            f"{cfg.base_url}{h5p_base}/import",
            headers=_auth_headers(cfg),
            field_name="file",
            filename=source.name,
            content=source.read_bytes(),
            content_type="application/zip",
        )
        if status != 200:
            stderr.write(f"API-Fehler ({status}): {body}\n")
            return 1
        _print_body(body, as_json=args.json, stdout=stdout)
        return 0
    if args.command == "export":
        status, content = _http_bytes(
            "GET",
            f"{cfg.base_url}{h5p_base}/export",
            headers=_auth_headers(cfg),
        )
        if status != 200:
            stderr.write(f"API-Fehler ({status}): {_body_preview(content.decode('utf-8', errors='replace'))}\n")
            return 1
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(content)
        stdout.write(f"Gespeichert: {output}\n")
        return 0
    if args.command == "reset":
        return _request_with_config(
            cfg,
            method="POST",
            path=f"{h5p_base}/reset",
            json_body=None,
            success={200},
            stdout=stdout,
            stderr=stderr,
        )
    return 2


def main(
    argv: list[str] | None = None,
    *,
    stdin: TextIO = sys.stdin,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.group == "auth" and args.command == "configure":
        return _configure(args, stdin=stdin, stdout=stdout, stderr=stderr)
    if args.group == "auth" and args.command == "status":
        return _status(stdout=stdout, stderr=stderr)
    if args.group == "units" and args.command == "list":
        return _units_list(args, stdout=stdout, stderr=stderr)
    if args.group == "units" and args.command == "create":
        return _units_create(args, stdout=stdout, stderr=stderr)
    if args.group == "units" and args.command == "edit":
        return _units_edit(args, stdout=stdout, stderr=stderr)
    if args.group == "units" and args.command == "delete":
        return _units_delete(args, stdout=stdout, stderr=stderr)
    if args.group == "sections":
        return _sections(args, stdout=stdout, stderr=stderr)
    if args.group == "phases":
        return _phases(args, stdout=stdout, stderr=stderr)
    if args.group == "modules":
        return _modules(args, stdout=stdout, stderr=stderr)
    if args.group == "module-edges":
        return _module_edges(args, stdout=stdout, stderr=stderr)
    if args.group == "materials":
        return _materials(args, stdout=stdout, stderr=stderr)
    if args.group == "tasks":
        return _tasks(args, stdout=stdout, stderr=stderr)
    if args.group == "h5p":
        return _h5p(args, stdout=stdout, stderr=stderr)
    if args.group in {
        "courses",
        "course-deletion-jobs",
        "course-members",
        "course-modules",
        "course-sections",
        "students",
    }:
        return run_course_command(
            args,
            request=_request_configured,
            stdout=stdout,
            stderr=stderr,
        )
    parser.error("unknown command")
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
