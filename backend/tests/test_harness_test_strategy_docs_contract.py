from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _read_doc(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def test_harness_test_strategy_documents_required_test_layers() -> None:
    """Keep the refactor harness honest about the purpose of each test layer."""

    text = _read_doc("docs/harness/TEST_STRATEGY.md")

    for required_heading in (
        "Domain- und Use-Case-Tests",
        "Adapter- und Contract-Tests",
        "OpenAPI- und API-Contract-Tests",
        "API-Integrationstests",
        "DB-, RLS- und Migrationstests",
        "Frontend-Tests",
        "H5P-Tests",
        "E2E-Smokes",
    ):
        assert required_heading in text


def test_harness_test_portfolio_has_actionable_decision_columns() -> None:
    """Ensure the inventory can drive concrete keep/merge/rewrite/retire decisions."""

    text = _read_doc("docs/harness/TEST_PORTFOLIO.md")

    for required_column in (
        "Bereich",
        "Beispielpfade",
        "Zweck",
        "Ebene",
        "Abhängigkeiten",
        "Marker",
        "Gate",
        "Risiko",
        "Entscheidung",
    ):
        assert required_column in text

    for decision in ("keep", "merge", "rewrite", "retire-later"):
        assert decision in text


def test_harness_quality_gates_define_test_profiles() -> None:
    """Document the intended local and CI test profiles before wiring gates."""

    text = _read_doc("docs/harness/QUALITY_GATES.md")

    for profile in (
        "fast",
        "backend-lint",
        "db-security",
        "frontend-h5p",
        "visual-smoke",
        "supply-chain",
        "full-prod-like",
    ):
        assert profile in text


def test_harness_quality_gates_explain_backend_lint_rollout() -> None:
    """C10 keeps the lint gate explicit and hard-wired into verify."""

    text = _read_doc("docs/harness/QUALITY_GATES.md")

    for required_term in (
        "make lint-backend",
        "Ruff",
        "Pyflakes",
        "Teil von `make verify`",
        "pyproject.toml",
    ):
        assert required_term in text
