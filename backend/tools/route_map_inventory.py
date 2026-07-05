"""Generate and check the route-by-route harness route map."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import sys

import yaml

from backend.tools.openapi_contract_check import (
    Operation,
    classify_surface,
    openapi_operations,
    runtime_operations,
)


DOC_START = "<!-- route-map:generated:start -->"
DOC_END = "<!-- route-map:generated:end -->"


@dataclass(frozen=True)
class RouteRecord:
    operation: Operation
    surface: str
    role: str
    data_access: str
    response_model: str
    existing_tests: str
    risk: str
    legacy_status: str
    decision: str
    target_layer: str


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_spec(spec_path: Path) -> dict:
    return yaml.safe_load(spec_path.read_text(encoding="utf-8"))


def _operation_spec(spec: dict, op: Operation) -> dict:
    path_item = spec.get("paths", {}).get(op.path, {})
    return path_item.get(op.method.lower(), {}) if isinstance(path_item, dict) else {}


def _response_model(spec: dict, op: Operation) -> str:
    operation = _operation_spec(spec, op)
    responses = operation.get("responses", {}) if isinstance(operation, dict) else {}
    ok = responses.get("200") or responses.get("201") or responses.get("204")
    if not ok:
        if classify_surface(op.path) == "active legacy UI":
            return "HTML/HTMX"
        return "unspecified"
    if "content" not in ok:
        return "empty/redirect"
    content = ok.get("content", {})
    json_content = content.get("application/json")
    if isinstance(json_content, dict):
        schema = json_content.get("schema", {})
        if "$ref" in schema:
            return schema["$ref"].rsplit("/", 1)[-1]
        if schema.get("type"):
            return str(schema["type"])
        return "json"
    if "text/html" in content:
        return "HTML"
    return ", ".join(sorted(content)) or "response"


def _role(path: str) -> str:
    if path.startswith("/auth/"):
        return "public/authenticated"
    if path in {"/health"} or path.startswith("/internal/health/"):
        return "ops"
    if path.startswith("/h5p/"):
        if path == "/h5p/healthz":
            return "public"
        if path == "/h5p/auth/me":
            return "authenticated principal bridge"
        if path in {"/h5p/editor", "/h5p/player"}:
            return "admin"
        if path == "/h5p/player/review":
            return "teacher/admin"
        if "/editor" in path or "/libraries" in path or "/contents" in path:
            return "teacher"
        if "/player" in path or "/finishedData" in path:
            return "student/teacher"
        return "service"
    if "/users/" in path:
        return "teacher/admin"
    if path.startswith("/api/app/") or path.startswith("/backend-internal/"):
        return "authenticated BFF"
    if path.startswith("/api/learning") or path.startswith("/learning"):
        return "student"
    if (
        path.startswith("/api/teaching")
        or path.startswith("/api/live")
        or path.startswith("/api/diagnostics")
        or path.startswith("/teaching")
        or path.startswith("/courses")
        or path.startswith("/units")
    ):
        return "teacher"
    return "authenticated"


def _data_access(path: str) -> str:
    if path.startswith("/auth/") or path.startswith("/api/app/") or path.startswith("/backend-internal/"):
        return "identity/session"
    if path.startswith("/h5p/"):
        if path == "/h5p/healthz":
            return "service status"
        if path == "/h5p/auth/me":
            return "web /api/me principal bridge"
        if path == "/h5p/player/review":
            return "H5P storage + review token"
        if path in {"/h5p/ajax", "/h5p/finishedData"}:
            return "H5P storage + learning forwarding"
        return "H5P storage/service"
    if path == "/health" or path.startswith("/internal/health/"):
        return "service status"
    if "upload" in path or "file" in path or "materials" in path:
        return "teaching/learning repo + storage"
    if "submissions" in path or path.startswith("/api/learning"):
        return "learning repo"
    if path.startswith("/api/teaching") or path.startswith("/api/live") or path.startswith("/api/diagnostics"):
        return "teaching repo"
    if path.startswith(("/courses", "/units", "/teaching")):
        return "teaching repo"
    if path.startswith("/learning"):
        return "learning repo"
    return "none"


def _tests(path: str) -> str:
    if path in {"/", "/about"}:
        return "backend/tests/test_navigation_roles_ui.py, backend/tests/test_app_composition_contract.py"
    if path == "/api/me":
        return "backend/tests/test_api_me_with_db_session_store.py, backend/tests/test_auth_contract.py, backend/tests/test_auth_middleware.py"
    if path.startswith("/h5p/"):
        return "backend/tests/test_h5p_*, h5p-service/test/*.mjs"
    if path.startswith("/auth/"):
        return "backend/tests/test_auth_*"
    if path.startswith("/api/app/") or path.startswith("/backend-internal/"):
        return "backend/tests/test_app_*, test_session_*"
    if path.startswith("/api/users/"):
        return "backend/tests/test_users_*, test_openapi_*"
    if path.startswith("/api/learning"):
        return "backend/tests/test_learning_*, test_openapi_learning_*"
    if path.startswith("/api/teaching") or path.startswith("/api/live") or path.startswith("/api/diagnostics"):
        return "backend/tests/test_teaching_*, test_openapi_teaching_*"
    if path == "/health" or path.startswith("/internal/health/"):
        return "backend/tests/test_*health*"
    return "characterization pending"


def _risk(op: Operation) -> str:
    path = op.path
    if op.method in {"POST", "PUT", "PATCH", "DELETE"}:
        return "high"
    if any(term in path for term in ("submissions", "upload", "members", "users", "auth", "session", "live")):
        return "high"
    if classify_surface(path) in {"active legacy UI", "BFF/internal"}:
        return "medium"
    if path == "/health" or path.startswith("/internal/health/"):
        return "low"
    return "medium"


def _legacy_status(surface: str) -> str:
    if surface == "active legacy UI":
        return "active legacy UI"
    if surface == "retired legacy UI":
        return "retired legacy UI"
    return "active"


def _decision(surface: str) -> str:
    if surface == "active legacy UI":
        return "retain until strangled"
    if surface == "retired legacy UI":
        return "remove/410 with tests"
    return "retain"


def _target_layer(surface: str) -> str:
    return {
        "public API": "OpenAPI + use case adapter",
        "BFF/internal": "SvelteKit BFF/view model",
        "H5P service": "H5P sidecar",
        "auth bridge": "identity adapter",
        "health/ops": "ops adapter",
        "active legacy UI": "SvelteKit or removal",
        "retired legacy UI": "removed route",
    }[surface]


def _is_retired_legacy_path(path: str) -> bool:
    """Return whether a registered legacy UI route is already a 410/redirect surface."""

    if path == "/learning" or path.startswith("/learning/courses/"):
        return True
    if path == "/courses" or path.startswith("/courses/"):
        return True
    if path == "/units" or path.startswith("/units/"):
        return True
    if path in {"/teaching/live", "/teaching/live/units", "/teaching/live/open"}:
        return True
    if path.startswith("/teaching/courses/") and "/live" in path:
        return True
    return False


def _record_legacy_status(path: str, surface: str) -> str:
    if surface == "active legacy UI" and _is_retired_legacy_path(path):
        return "retired but still registered"
    return _legacy_status(surface)


def _record_decision(path: str, surface: str) -> str:
    if surface == "active legacy UI" and _is_retired_legacy_path(path):
        return "remove after characterization"
    return _decision(surface)


def _record_target_layer(path: str, surface: str) -> str:
    if surface == "active legacy UI" and _is_retired_legacy_path(path):
        return "removed route"
    return _target_layer(surface)


def build_records(spec_path: Path) -> list[RouteRecord]:
    spec = _load_spec(spec_path)
    operations = sorted(openapi_operations(spec_path) | runtime_operations())
    records: list[RouteRecord] = []
    for op in operations:
        surface = classify_surface(op.path)
        records.append(
            RouteRecord(
                operation=op,
                surface=surface,
                role=_role(op.path),
                data_access=_data_access(op.path),
                response_model=_response_model(spec, op),
                existing_tests=_tests(op.path),
                risk=_risk(op),
                legacy_status=_record_legacy_status(op.path, surface),
                decision=_record_decision(op.path, surface),
                target_layer=_record_target_layer(op.path, surface),
            )
        )
    return records


def _escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def render_markdown(spec_path: Path) -> str:
    records = build_records(spec_path)
    lines = [
        "# Route Map",
        "",
        "Status: Active",
        "Owner: Produktverantwortlicher",
        "Local checks: `make test-route-map`, `make test-api-contract-baseline`",
        "CI status: `make verify` führt `make test-route-map` als hartes Gate aus; `make harness-minimum` prüft den Contract-Test.",
        "Related plans: `docs/plan/2026-05-02-harness-engineering-refactor-plan.md`, `docs/plan/2026-07-02-route-surface-map.md`",
        "Review cadence: nach jedem Route-Surface- oder API-Vertrags-Refactor",
        "",
        "## Zweck",
        "Diese Route Map klassifiziert die technischen Oberflächen, damit OpenAPI-Lücken, BFF-Flächen, H5P-Service-Routen, Auth-Brücken, Health/Ops-Endpunkte und Legacy-UI-Routen nicht miteinander verwechselt werden.",
        "",
        "## Gate-Regel",
        "`make test-route-map` prüft, dass die generierte Route-für-Route-Inventur synchron mit Runtime-App und `api/openapi.yml` bleibt. Undokumentierte `/api/*`-Routen bleiben zusätzlich durch `make test-api-contract-baseline` verboten.",
        "",
        DOC_START,
        "",
        "| Route/Endpoint | Surface | Role | Data Access | Response Model | Existing Tests | Risk | Legacy Status | Decision | Target Layer |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for record in records:
        op = record.operation
        lines.append(
            "| "
            + " | ".join(
                _escape(value)
                for value in (
                    f"{op.method} {op.path}",
                    record.surface,
                    record.role,
                    record.data_access,
                    record.response_model,
                    record.existing_tests,
                    record.risk,
                    record.legacy_status,
                    record.decision,
                    record.target_layer,
                )
            )
            + " |"
        )
    lines.extend(
        [
            "",
            DOC_END,
            "",
            "## Abschlussstand",
            "- FastAPI registriert keine aktiven Legacy-Produkt-HTML-Seiten mehr.",
            "- Bereits entfernte Legacy-Produktpfade bleiben durch Characterization-Tests als 410- oder Redirect-Verhalten geschützt.",
            "- `make test-route-map` hält Runtime-App und generierte Route Map synchron.",
        ]
    )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, default=_repo_root() / "api" / "openapi.yml")
    parser.add_argument("--check", type=Path)
    parser.add_argument("--write", type=Path)
    args = parser.parse_args(argv)

    rendered = render_markdown(args.spec)
    if args.write:
        args.write.write_text(rendered, encoding="utf-8")
    if args.check:
        current = args.check.read_text(encoding="utf-8")
        if current != rendered:
            print(f"Route map is stale: regenerate with `python -m backend.tools.route_map_inventory --write {args.check}`", file=sys.stderr)
            return 1
        print("route-map-inventory-ok")
        return 0
    if not args.write:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
