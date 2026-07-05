from pathlib import Path
import json
import re


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MAKEFILE = PROJECT_ROOT / "Makefile"
SCAN_SCRIPT = PROJECT_ROOT / "backend/tools/import_boundary_scan.py"
BASELINE = PROJECT_ROOT / "docs/harness/IMPORT_BOUNDARY_BASELINE.json"
INVENTORY = PROJECT_ROOT / "docs/harness/IMPORT_INVENTORY.md"
ARCHITECTURE_RULES = PROJECT_ROOT / "docs/harness/ARCHITECTURE_RULES.md"


def _target_body(target: str) -> str:
    text = MAKEFILE.read_text(encoding="utf-8")
    match = re.search(
        rf"(?ms)^\.PHONY: {re.escape(target)}\n{re.escape(target)}:\n(?P<body>.*?)(?=^\.PHONY: |\Z)",
        text,
    )
    assert match is not None, f"Makefile target {target!r} not found"
    return match.group("body")


def test_makefile_exposes_import_boundary_signal_target() -> None:
    """PR 6 needs a stable local entry point for import-debt visibility."""

    body = _target_body("test-import-boundaries")

    assert "python -m backend.tools.import_boundary_scan" in body
    assert "--baseline docs/harness/IMPORT_BOUNDARY_BASELINE.json" in body


def test_harness_signals_runs_import_boundary_scan_as_warning_signal() -> None:
    """Import debt should be visible before it is made hard."""

    body = _target_body("harness-signals")

    assert "import_boundary_scan" in body
    assert "test-import-boundaries" not in body


def test_verify_runs_import_boundary_gate() -> None:
    """PR 6 acceptance requires new import-boundary violations to be visible in verify."""

    body = _target_body("verify")

    assert "$(MAKE) test-import-boundaries" in body


def test_import_boundary_scanner_and_baseline_cover_required_categories() -> None:
    """Existing import debt must be counted in machine-readable categories."""

    assert SCAN_SCRIPT.exists(), "Missing import boundary scanner"
    assert BASELINE.exists(), "Missing import boundary baseline"

    script_text = SCAN_SCRIPT.read_text(encoding="utf-8")
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    categories = baseline.get("categories", {})

    for category in (
        "flat_routes_imports",
        "flat_components_imports",
        "backend_web_routes_imports",
        "sys_path_mutations",
    ):
        assert category in script_text
        assert category in categories
        assert isinstance(categories[category], int)


def test_import_inventory_documents_target_import_scheme() -> None:
    """The warning gate needs human-readable rules, not only numbers."""

    assert INVENTORY.exists(), "Missing import inventory document"
    assert ARCHITECTURE_RULES.exists(), "Missing architecture rules document"
    text = INVENTORY.read_text(encoding="utf-8") + "\n" + ARCHITECTURE_RULES.read_text(encoding="utf-8")

    for phrase in (
        "routes.*",
        "components",
        "backend.web.main:app",
        "main:app",
        "sys.path",
        "make test-import-boundaries",
    ):
        assert phrase in text
