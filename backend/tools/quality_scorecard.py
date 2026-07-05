"Generate a monthly quality scorecard for the harness plan."

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORT_PATH = REPO_ROOT / "docs" / "harness" / "QUALITY_SCORECARD.md"
DEFAULT_HISTORY_PATH = REPO_ROOT / "docs" / "harness" / "QUALITY_SCORECARD_HISTORY.json"
SKILLS_PATH = REPO_ROOT / "docs" / "harness" / "SKILLS.md"
TECH_DEBT_PATH = REPO_ROOT / "docs" / "harness" / "TECH_DEBT.md"
OPENAPI_SPEC = REPO_ROOT / "api" / "openapi.yml"
ROUTE_MAP_DOC = REPO_ROOT / "docs" / "harness" / "ROUTE_MAP.md"


DEFAULT_HOTSPOTS = [
    "backend/web/main.py",
    "backend/web/routes/app.py",
    "backend/web/routes/learning.py",
    "backend/web/routes/teaching.py",
    "backend/learning/repo_db.py",
    "backend/teaching/repo_db.py",
    "h5p-service/server.mjs",
    "frontend/src/routes/learning/courses/[courseId]/units/[unitId]/+page.svelte",
    "frontend/src/routes/teaching/units/[unitId]/+page.svelte",
    "frontend/src/lib/styles/app.css",
    "frontend/src/lib/styles/design-system.css",
]


@dataclass(frozen=True)
class CheckResult:
    name: str
    command: list[str]
    ok: bool | None
    exit_code: int | None
    output: str


def _venv_python() -> str:
    venv_python = REPO_ROOT / ".venv" / "bin" / "python"
    return str(venv_python) if venv_python.exists() else sys.executable


def _venv_pytest() -> str:
    venv_pytest = REPO_ROOT / ".venv" / "bin" / "pytest"
    return str(venv_pytest) if venv_pytest.exists() else _venv_python()


def _run_command(command: list[str], timeout_seconds: int) -> CheckResult:
    name = command[0]
    try:
        completed = subprocess.run(
            command,
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout_seconds,
        )
    except FileNotFoundError:
        return CheckResult(
            name=name,
            command=command,
            ok=False,
            exit_code=None,
            output="command-not-found",
        )
    except Exception as error:  # pragma: no cover - defensive path
        return CheckResult(
            name=name,
            command=command,
            ok=False,
            exit_code=None,
            output=f"error:{error}",
        )

    output = (completed.stdout or "") + ("\n" + completed.stderr if completed.stderr else "")
    return CheckResult(
        name=name,
        command=command,
        ok=completed.returncode == 0,
        exit_code=completed.returncode,
        output=output.strip(),
    )


def _run_json_command(command: list[str], timeout_seconds: int) -> tuple[dict[str, Any] | None, CheckResult]:
    result = _run_command(command, timeout_seconds)
    if not result.ok or not result.output:
        return None, result

    output = result.output.strip()
    if "{" not in output:
        return None, result

    try:
        json_text = output[output.index("{") :]
        return json.JSONDecoder().raw_decode(json_text)[0], result
    except json.JSONDecodeError:
        return None, result


def _line_count(path: Path) -> int:
    return sum(1 for _ in path.read_text(encoding="utf-8", errors="replace").splitlines())


def _parse_markdown_table(path: Path, key_header: str) -> list[dict[str, str]]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    headers: list[str] = []
    rows: list[dict[str, str]] = []
    reading_rows = False

    for raw in lines:
        if raw.startswith(f"| {key_header} |"):
            headers = [cell.strip() for cell in raw.strip("| ").split(" | ")]
            reading_rows = True
            continue

        if not reading_rows:
            continue

        if raw.startswith("| ---"):
            continue

        if not raw.startswith("|"):
            break

        cells = [cell.strip() for cell in raw.strip("| ").split(" | ")]
        if len(cells) < len(headers):
            continue

        row: dict[str, str] = {header: cells[i] for i, header in enumerate(headers)}
        rows.append(row)

    return rows


def _parse_tech_debt() -> list[dict[str, str]]:
    rows = _parse_markdown_table(TECH_DEBT_PATH, "ID")
    return [
        {
            "id": row.get("ID", ""),
            "bereich": row.get("Bereich", ""),
            "risiko": row.get("Risiko", ""),
            "grund": row.get("Grund", ""),
            "owner": row.get("Owner", ""),
            "review_date": row.get("Review date", ""),
            "exit_criterion": row.get("Exit criterion", ""),
        }
        for row in rows
        if row.get("ID")
    ]


def _parse_skills() -> list[dict[str, str]]:
    return [
        row
        for row in _parse_markdown_table(SKILLS_PATH, "Skill")
        if row.get("Skill") and row.get("Activation status")
    ]


def _status_text(result: CheckResult | None) -> str:
    if result is None or result.ok is None:
        return "not run"
    if result.ok:
        return "pass"
    if "timeout" in result.output:
        return "timeout"
    return "fail"


def _collect_hotspots(history: list[dict[str, Any]]) -> list[tuple[str, int, int | None]]:
    latest_by_path: dict[str, int] = {}
    if history:
        latest = sorted(history, key=lambda item: item.get("month", ""), reverse=True)[0]
        for item in latest.get("hotspots", []):
            path = item.get("path")
            loc = item.get("loc")
            if isinstance(path, str) and isinstance(loc, int):
                latest_by_path[path] = loc

    rows: list[tuple[str, int, int | None]] = []
    for rel_path in DEFAULT_HOTSPOTS:
        file_path = REPO_ROOT / rel_path
        if not file_path.exists():
            rows.append((rel_path, 0, None))
            continue

        current = _line_count(file_path)
        previous = latest_by_path.get(rel_path)
        delta = None if previous is None else current - previous
        rows.append((rel_path, current, delta))

    return rows


def _emit_report(
    report_path: Path,
    month: str,
    hotspot_rows: list[tuple[str, int, int | None]],
    checks: dict[str, CheckResult],
    openapi_summary: dict[str, Any] | None,
    tech_debt_rows: list[dict[str, str]],
    skill_rows: list[dict[str, str]],
) -> None:
    generated = datetime.now().strftime("%Y-%m-%d")
    lines = [
        "# Quality Scorecard",
        "",
        "Status: Draft",
        "Owner: Produktverantwortlicher",
        "Related plan: `docs/plan/2026-05-02-harness-engineering-refactor-plan.md`",
        "Review cadence: monatlich",
        "",
        f"## Snapshot {month} (generated {generated})",
        "",
        "### Hotspot LOC trend",
        "| File | LOC | Delta vs previous month |",
        "| --- | ---: | ---: |",
    ]

    for file_path, current, delta in sorted(hotspot_rows):
        lines.append(f"| {file_path} | {current} | { 'n/a' if delta is None else f'{delta:+d}' } |")

    lines.extend(
        [
            "",
            "### Security status",
            f"- Security quick checks: {_status_text(checks.get('security'))} ({' '.join(checks['security'].command)})",
            "",
            "### Contract diff status",
            f"- OpenAPI contract baseline: {_status_text(checks.get('openapi'))} ({' '.join(checks['openapi'].command)})",
            f"- Route map inventory: {_status_text(checks.get('route-map'))} ({' '.join(checks['route-map'].command)})",
            "",
            "### Docker image parity",
            f"- Web image smoke check: {_status_text(checks.get('docker-image-smoke'))} ({' '.join(checks['docker-image-smoke'].command)})",
            "",
        ]
    )

    if openapi_summary:
        lines.append(f"- OpenAPI operations: {openapi_summary.get('openapi_operations', 'n/a')}")
        lines.append(f"- Runtime operations: {openapi_summary.get('runtime_operations', 'n/a')}")

    lines.extend(
        [
            "",
            "### Open TECH_DEBT",
            f"- Outstanding entries: {len(tech_debt_rows)}",
        ]
    )
    if tech_debt_rows:
        lines.extend(
            [
                "| ID | Bereich | Risiko | Exit criterion |",
                "| --- | --- | --- | --- |",
            ]
        )
        for row in tech_debt_rows:
            lines.append(
                f"| {row.get('id', '-')} | {row.get('bereich', '-')} | {row.get('risiko', '-')} | {row.get('exit_criterion', '-')} |"
            )

    active = [row for row in skill_rows if row.get("Activation status") == "active"]
    manual_eval = sum(1 for row in active if "manual" in row.get("Eval status", ""))

    lines.extend(
        [
            "",
            "### Skill inventory and eval status",
            f"- Active skills: {len(active)}",
            f"- Active skills with manual-forward eval status: {manual_eval}",
            "| Skill | Eval status | Activation status |",
            "| --- | --- | --- |",
        ]
    )
    for row in active:
        lines.append(f"| {row.get('Skill', '-')} | {row.get('Eval status', '-')} | {row.get('Activation status', '-')} |")

    report_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _load_history(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = data.get("entries", [])
    return entries if isinstance(entries, list) else []


def _save_history(path: Path, entries: list[dict[str, Any]]) -> None:
    path.write_text(json.dumps({"entries": entries}, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _build_entry(
    month: str,
    hotspot_rows: list[tuple[str, int, int | None]],
    checks: dict[str, CheckResult],
    openapi_summary: dict[str, Any] | None,
    tech_debt_rows: list[dict[str, str]],
    skill_rows: list[dict[str, str]],
) -> dict[str, Any]:
    checks_payload = {}
    for key, result in checks.items():
        checks_payload[key] = {
            "ok": result.ok,
            "exit_code": result.exit_code,
            "command": " ".join(result.command),
        }

    return {
        "month": month,
        "generated": datetime.now().isoformat(timespec="seconds"),
        "hotspots": [
            {"path": path, "loc": loc, "delta_from_previous": delta}
            for path, loc, delta in hotspot_rows
        ],
        "checks": checks_payload,
        "openapi_summary": openapi_summary,
        "tech_debt": {
            "count": len(tech_debt_rows),
            "entries": tech_debt_rows,
        },
        "skills": {
            "active": [row for row in skill_rows if row.get("Activation status") == "active"],
        },
    }


def _upsert_entry(entries: list[dict[str, Any]], new_entry: dict[str, Any]) -> list[dict[str, Any]]:
    filtered = [entry for entry in entries if entry.get("month") != new_entry["month"]]
    filtered.append(new_entry)
    return sorted(filtered, key=lambda entry: str(entry.get("month", "")))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--month", default=datetime.now().strftime("%Y-%m"), help="Snapshot key YYYY-MM")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH, help="Output report path")
    parser.add_argument("--history", type=Path, default=DEFAULT_HISTORY_PATH, help="History JSON path")
    parser.add_argument("--run-docker-check", action="store_true", help="Run the docker image smoke check")
    parser.add_argument("--skip-gates", action="store_true", help="Skip command checks")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()

    checks: dict[str, CheckResult] = {}
    openapi_summary: dict[str, Any] | None = None

    python_exec = _venv_python()
    pytest_exec = _venv_pytest()

    if args.skip_gates:
        checks = {
            "security": CheckResult("security", ["pytest", "security-checks"], None, None, "not run"),
            "openapi": CheckResult("openapi", ["openapi-contract-check"], None, None, "not run"),
            "route-map": CheckResult("route-map", ["route-map-check"], None, None, "not run"),
            "docker-image-smoke": CheckResult("docker-image-smoke", ["docker-image-smoke"], None, None, "not run"),
        }
    else:
        checks = {
            "security": _run_command(
                [
                    pytest_exec,
                    "-q",
                    "backend/tests/test_config_security.py",
                    "backend/tests/test_privacy_logging_contract.py",
                    "backend/tests/test_csrf_tokens_contract.py",
                ],
                timeout_seconds=180,
            ),
            "openapi": _run_command(
                [
                    python_exec,
                    "-m",
                    "backend.tools.openapi_contract_check",
                    "--spec",
                    str(OPENAPI_SPEC),
                ],
                timeout_seconds=180,
            ),
            "route-map": _run_command(
                [
                    python_exec,
                    "-m",
                    "backend.tools.route_map_inventory",
                    "--check",
                    str(ROUTE_MAP_DOC),
                ],
                timeout_seconds=180,
            ),
            "docker-image-smoke": CheckResult(
                "docker-image-smoke",
                [python_exec, "-m", "backend.tools.docker_image_smoke"],
                None,
                None,
                "not run",
            ),
        }
        if args.run_docker_check:
            checks["docker-image-smoke"] = _run_command(
                [python_exec, "-m", "backend.tools.docker_image_smoke"],
                timeout_seconds=600,
            )

        openapi_summary, _ = _run_json_command(
            [
                python_exec,
                "-m",
                "backend.tools.openapi_contract_check",
                "--spec",
                str(OPENAPI_SPEC),
                "--summary",
            ],
            timeout_seconds=180,
        )

    history = _load_history(args.history)
    hotspot_rows = _collect_hotspots(history)
    tech_debt_rows = _parse_tech_debt()
    skill_rows = _parse_skills()

    entry = _build_entry(args.month, hotspot_rows, checks, openapi_summary, tech_debt_rows, skill_rows)
    history = _upsert_entry(history, entry)
    _save_history(args.history, history)
    _emit_report(args.report, args.month, hotspot_rows, checks, openapi_summary, tech_debt_rows, skill_rows)

    print(f"wrote {args.report}")
    print(f"updated {args.history}")

    return 0 if all(check.ok is not False for check in checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
