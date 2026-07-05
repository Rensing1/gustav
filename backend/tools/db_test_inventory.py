"""Generate and check the DB/RLS test inventory.

The inventory is a review aid for the harness refactor. It identifies tests
that appear to touch the real database, RLS policies, migrations, or Supabase
configuration before `db_read` and `db_write` markers become hard policy.
"""

from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
from pathlib import Path
import re
import sys


DB_TEST_INVENTORY_OK = "db-test-inventory-ok"

DB_MARKERS = ("db_read", "db_write")
OPT_IN_MARKERS = (
    "supabase_integration",
    "e2e",
    "integration",
    "scratch_db_required",
    "legacy_migration",
)
KNOWN_MARKERS = DB_MARKERS + OPT_IN_MARKERS
DB_ENV_NAMES = (
    "RLS_TEST_DSN",
    "RLS_TEST_SERVICE_DSN",
    "SERVICE_ROLE_DSN",
    "SESSION_TEST_DSN",
    "DATABASE_URL",
    "SUPABASE_DB_URL",
    "LEARNING_WORKER_DB_URL",
)
SUPABASE_ENV_NAMES = (
    "SUPABASE_URL",
    "SUPABASE_PUBLIC_URL",
    "SUPABASE_SERVICE_ROLE_KEY",
    "SUPABASE_STORAGE_BUCKET",
)


@dataclass(frozen=True)
class DbTestRecord:
    path: str
    classification: str
    markers: tuple[str, ...]
    marker_status: str
    signals: tuple[str, ...]
    recommended_action: str


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _iter_python_tests(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.py") if "__pycache__" not in path.parts)


def _attribute_chain(node: ast.AST) -> list[str]:
    parts: list[str] = []
    current: ast.AST | None = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
    return list(reversed(parts))


def _string_constant(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _call_string_values(node: ast.Call) -> set[str]:
    values = {_string_constant(arg) for arg in node.args}
    for keyword in node.keywords:
        values.add(_string_constant(keyword.value))
    return {value for value in values if value}


def _subscript_string_value(node: ast.Subscript) -> str | None:
    return _string_constant(node.slice)


def _is_env_read_call(chain: list[str]) -> bool:
    return chain in (["os", "getenv"], ["os", "environ", "get"], ["getenv"])


def _is_env_subscript(node: ast.Subscript) -> bool:
    return _attribute_chain(node.value) == ["os", "environ"]


def _identifier_text(tree: ast.AST) -> str:
    identifiers: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            identifiers.append(node.name)
        elif isinstance(node, ast.Name):
            identifiers.append(node.id)
        elif isinstance(node, ast.Attribute):
            identifiers.append(node.attr)
    return " ".join(identifiers).lower()


def _find_markers(tree: ast.AST) -> tuple[str, ...]:
    markers: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute):
            continue
        chain = _attribute_chain(node)
        if len(chain) >= 3 and chain[:2] == ["pytest", "mark"] and chain[2] in KNOWN_MARKERS:
            markers.append(chain[2])
    return tuple(sorted(set(markers)))


def _find_signals(path: Path, tree: ast.AST) -> tuple[str, ...]:
    lower_path = path.as_posix().lower()
    identifiers = _identifier_text(tree)
    signals: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [alias.name for alias in getattr(node, "names", [])]
            module = getattr(node, "module", None)
            if module == "psycopg" or any(name == "psycopg" for name in names):
                signals.add("psycopg-import")
        elif isinstance(node, ast.Call):
            chain = _attribute_chain(node.func)
            if chain and chain[-1] == "connect" and "psycopg" in chain:
                signals.add("psycopg-connect")
            values = _call_string_values(node)
            if chain == ["pytest", "importorskip"] and "psycopg" in values:
                signals.add("psycopg-required")
            if chain and chain[-1] in {"require_db_or_skip", "_require_db_or_skip"}:
                signals.add("requires-db")
            if _is_env_read_call(chain):
                for env_name in DB_ENV_NAMES:
                    if env_name in values:
                        signals.add(f"env:{env_name}")
                for env_name in SUPABASE_ENV_NAMES:
                    if env_name in values:
                        signals.add(f"env:{env_name}")
            if any("supabase/migrations" in value.lower() or "migrations/" in value.lower() for value in values):
                signals.add("migration")
        elif isinstance(node, ast.Subscript) and _is_env_subscript(node):
            value = _subscript_string_value(node)
            if value in DB_ENV_NAMES:
                signals.add(f"env:{value}")
            if value in SUPABASE_ENV_NAMES:
                signals.add(f"env:{value}")

    if re.search(r"(^|[^a-z0-9])rls([^a-z0-9]|$)", lower_path) or re.search(
        r"(^|[^a-z0-9])rls([^a-z0-9]|$)", identifiers
    ):
        signals.add("rls")
    if "/migration/" in lower_path:
        signals.add("migration")
    if "supabase" in lower_path or "supabase" in identifiers:
        signals.add("supabase")

    return tuple(sorted(signals))


def _classification(signals: tuple[str, ...]) -> str:
    if "psycopg-connect" in signals:
        return "real-db"
    if any(signal.startswith("env:") and signal.removeprefix("env:") in DB_ENV_NAMES for signal in signals):
        return "real-db"
    if "requires-db" in signals:
        return "real-db"
    if "migration" in signals:
        return "migration-static"
    if "supabase" in signals or any(signal.startswith("env:SUPABASE_") for signal in signals):
        return "storage-or-config"
    return "unit-or-contract"


def _marker_status(classification: str, markers: tuple[str, ...]) -> str:
    has_db_marker = any(marker in DB_MARKERS for marker in markers)
    has_opt_in_marker = any(marker in OPT_IN_MARKERS for marker in markers)
    if classification == "real-db":
        if has_db_marker:
            return "marked-db"
        if has_opt_in_marker:
            return "covered-by-opt-in-marker"
        return "missing-db-marker"
    return "no-db-marker-needed"


def _recommended_action(classification: str, marker_status: str) -> str:
    if marker_status == "missing-db-marker":
        return "Review for db_read/db_write before marker hardening"
    if marker_status == "marked-db":
        return "Keep marker and isolation visible"
    if marker_status == "covered-by-opt-in-marker":
        return "Keep existing opt-in gate"
    if classification == "migration-static":
        return "Keep static migration contract unless it opens a DB connection"
    if classification == "storage-or-config":
        return "Keep service-free unless it reaches the real DB"
    return "No DB inventory action"


def _record_for(path: Path, repo_root: Path, text: str) -> DbTestRecord | None:
    tree = ast.parse(text, filename=str(path))
    signals = _find_signals(path, tree)
    classification = _classification(signals)
    if classification == "unit-or-contract":
        return None

    markers = _find_markers(tree)
    marker_status = _marker_status(classification, markers)
    return DbTestRecord(
        path=path.relative_to(repo_root).as_posix(),
        classification=classification,
        markers=markers,
        marker_status=marker_status,
        signals=signals,
        recommended_action=_recommended_action(classification, marker_status),
    )


def scan_tests(root: Path, *, repo_root: Path | None = None) -> list[DbTestRecord]:
    """Return DB-relevant test inventory records below `root`.

    `repo_root` controls how paths are rendered. The scanner is intentionally
    heuristic because it is a review aid, not the final marker gate.
    """

    resolved_root = root.resolve()
    resolved_repo_root = repo_root.resolve() if repo_root else _repo_root()
    records: list[DbTestRecord] = []
    for path in _iter_python_tests(resolved_root):
        text = path.read_text(encoding="utf-8", errors="replace")
        record = _record_for(path, resolved_repo_root, text)
        if record:
            records.append(record)
    return records


def _escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def _join(values: tuple[str, ...]) -> str:
    return ", ".join(values) if values else "-"


def render_markdown(root: Path | None = None) -> str:
    tests_root = root or (_repo_root() / "backend" / "tests")
    records = scan_tests(tests_root, repo_root=_repo_root())
    missing = sum(1 for record in records if record.marker_status == "missing-db-marker")
    marked = sum(1 for record in records if record.marker_status == "marked-db")
    opt_in = sum(1 for record in records if record.marker_status == "covered-by-opt-in-marker")
    storage_or_config = sum(1 for record in records if record.classification == "storage-or-config")
    migration_static = sum(1 for record in records if record.classification == "migration-static")

    lines = [
        "# DB Test Inventory",
        "",
        "Status: Draft",
        "Owner: Produktverantwortlicher",
        "Local checks: `make test-db-inventory`",
        "CI status: `make verify` führt `make test-db-inventory` als Synchronitätscheck aus.",
        "Related plans: `docs/plan/2026-05-02-harness-engineering-refactor-plan.md`",
        "Review cadence: vor dem Scharfstellen von `db_read`/`db_write` und nach größeren DB/RLS-Teständerungen",
        "",
        "## Zweck",
        "Dieses Inventar macht DB-, RLS-, Migrations- und Supabase-nahe Tests sichtbar, bevor `db_read` und `db_write` als harte Marker-Regel eingesetzt werden. Es verändert keine Tests und ersetzt keine Sicherheitsprüfung.",
        "",
        "## Zusammenfassung",
        f"- Inventarisierte Dateien: {len(records)}",
        f"- Echte DB/RLS-Kandidaten ohne `db_read`/`db_write`: {missing}",
        f"- Echte DB/RLS-Kandidaten mit `db_read`/`db_write`: {marked}",
        f"- Echte DB/RLS-Kandidaten mit bestehendem Opt-in-Marker: {opt_in}",
        f"- Supabase-Storage-/Konfigurationsverträge ohne echte DB-Verbindung: {storage_or_config}",
        f"- Statische Migrationstests ohne echte DB-Verbindung: {migration_static}",
        "",
        "## Marker-Regel",
        "`missing-db-marker` ist in diesem Schritt ein Review-Signal, kein harter Fehler. Vor einer späteren Verschärfung muss jede betroffene Datei entweder `db_read`/`db_write` bekommen oder bewusst als servicefreier Contract-Test klassifiziert werden.",
        "",
        "| Test file | Classification | Markers | Marker status | Signals | Recommended action |",
        "| --- | --- | --- | --- | --- | --- |",
    ]

    for record in records:
        lines.append(
            "| "
            + " | ".join(
                _escape(value)
                for value in (
                    record.path,
                    record.classification,
                    _join(record.markers),
                    record.marker_status,
                    _join(record.signals),
                    record.recommended_action,
                )
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Offene Arbeit",
            "- `missing-db-marker`-Dateien in kleine Review-Batches aufteilen.",
            "- Danach entscheiden, ob `db_read` und `db_write` harte Marker oder ersetzbare Übergangsmarker sind.",
            "- Tests mit globalen DB-Mutationen getrennt von isolierten DB-Lese-/Schreibtests behandeln.",
        ]
    )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=_repo_root() / "backend" / "tests")
    parser.add_argument("--check", type=Path)
    parser.add_argument("--write", type=Path)
    args = parser.parse_args(argv)

    rendered = render_markdown(args.root)
    if args.write:
        args.write.write_text(rendered, encoding="utf-8")
    if args.check:
        current = args.check.read_text(encoding="utf-8")
        if current != rendered:
            print(
                f"DB test inventory is stale: regenerate with `python -m backend.tools.db_test_inventory --write {args.check}`",
                file=sys.stderr,
            )
            return 1
        print(DB_TEST_INVENTORY_OK)
        return 0
    if not args.write:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
