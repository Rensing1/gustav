from __future__ import annotations

import argparse
import getpass
import json
import sys
from typing import Any, TextIO
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError

from .config import GustavCLIConfig, load_config, save_config


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
    for name in ("list", "create", "edit", "delete", "reorder"):
        material_cmd = materials_sub.add_parser(name)
        material_cmd.add_argument("--unit-id", required=True)
        target = material_cmd.add_mutually_exclusive_group(required=True)
        target.add_argument("--section-id")
        target.add_argument("--module-id")
        if name in {"edit", "delete"}:
            material_cmd.add_argument("material_id")
        if name == "create":
            material_cmd.add_argument("--title", required=True)
            material_cmd.add_argument("--body-md", required=True)
        if name == "edit":
            material_cmd.add_argument("--title")
            material_cmd.add_argument("--body-md")
            material_cmd.add_argument("--alt-text")
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
            task_cmd.add_argument("--criterion", action="append", dest="criteria")
            task_cmd.add_argument("--teacher-context-md")
            task_cmd.add_argument("--due-at")
            task_cmd.add_argument("--max-attempts", type=int)
        if name == "delete":
            task_cmd.add_argument("--yes", action="store_true")
        if name == "reorder":
            task_cmd.add_argument("--ids", nargs="+", required=True)
        if name == "list":
            task_cmd.add_argument("--json", action="store_true")
    return parser


def _configure(args: argparse.Namespace, *, stdin: TextIO, stdout: TextIO) -> int:
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
                label = item.get("title") or item.get("instruction_md") or item.get("label") or ""
                stdout.write(f"{item.get('id', '')}\t{label}\n")
        return
    if isinstance(body, dict):
        stdout.write(f"{body.get('id', '')}\t{body.get('title', '')}\n")


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
        stdout.write("Gelöscht.\n")
        return 0
    _print_body(body, as_json=as_json, stdout=stdout)
    return 0


def _units_create(args: argparse.Namespace, *, stdout: TextIO, stderr: TextIO) -> int:
    cfg = _load_config_or_error(stderr)
    if cfg is None:
        return 1
    payload: dict[str, object] = {"title": args.title}
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
        return _request_configured(
            method="GET",
            path=f"{base}/graph",
            json_body=None,
            success={200},
            stdout=stdout,
            stderr=stderr,
            as_json=args.json,
        )
    if args.command == "create":
        return _request_configured(
            method="POST",
            path=base,
            json_body={"phase_id": args.phase_id, "title": args.title},
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
        stdout.write("Gelöscht.\n")
        return 0
    _print_body(body, as_json=as_json, stdout=stdout)
    return 0


def _materials(args: argparse.Namespace, *, stdout: TextIO, stderr: TextIO) -> int:
    resolved = _content_base("materials", args, stderr=stderr)
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
    return 2


def _task_payload(args: argparse.Namespace, *, partial: bool) -> dict[str, object]:
    payload: dict[str, object] = {}
    if getattr(args, "instruction_md", None) is not None:
        payload["instruction_md"] = args.instruction_md
    if getattr(args, "criteria", None) is not None:
        payload["criteria"] = args.criteria
    if getattr(args, "teacher_context_md", None) is not None:
        payload["teacher_context_md"] = args.teacher_context_md
    if getattr(args, "due_at", None) is not None:
        payload["due_at"] = args.due_at
    if getattr(args, "max_attempts", None) is not None:
        payload["max_attempts"] = args.max_attempts
    if not partial and "instruction_md" not in payload:
        payload["instruction_md"] = args.instruction_md
    return payload


def _tasks(args: argparse.Namespace, *, stdout: TextIO, stderr: TextIO) -> int:
    resolved = _content_base("tasks", args, stderr=stderr)
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
            json_body=_task_payload(args, partial=False),
            success={201},
            stdout=stdout,
            stderr=stderr,
        )
    if args.command == "edit":
        payload = _task_payload(args, partial=True)
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
        return _configure(args, stdin=stdin, stdout=stdout)
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
    parser.error("unknown command")
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
