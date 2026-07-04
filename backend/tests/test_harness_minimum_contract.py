from pathlib import Path
import re


REPO_ROOT = Path(__file__).resolve().parents[2]

REQUIRED_HARNESS_DOCS = (
    "docs/harness/INDEX.md",
    "docs/harness/AI_HARNESS.md",
    "docs/harness/AGENT_PLAYBOOK.md",
    "docs/harness/AUTONOMY_MATRIX.md",
    "docs/harness/ARCHITECTURE_RULES.md",
    "docs/harness/QUALITY_GATES.md",
    "docs/harness/TEST_STRATEGY.md",
    "docs/harness/SECURITY_BASELINE.md",
    "docs/harness/TEST_PORTFOLIO.md",
    "docs/harness/IMPORT_INVENTORY.md",
    "docs/harness/API_CONTRACTS.md",
    "docs/harness/ROUTE_MAP.md",
    "docs/harness/HOTSPOTS.md",
    "docs/harness/TECH_DEBT.md",
    "docs/harness/SKILLS.md",
    "docs/harness/SKILL_EVALS.md",
)

REQUIRED_PLAN_MEMORY_DOCS = (
    "docs/plan/INDEX.md",
    "docs/plan/MILESTONES.md",
    "docs/plan/DECISIONS.md",
    "docs/plan/2026-07-02-harness-minimum-implementation.md",
)

INITIAL_PROJECT_SKILLS = (
    "gustav-plan-status",
    "gustav-harness-gardener",
    "gustav-pr-review",
    "gustav-pr-fix",
    "gustav-api-contract",
    "gustav-security-review",
    "gustav-route-map",
)

REQUIRED_SKILL_SECTIONS = (
    "## Purpose",
    "## Trigger",
    "## Allowed Actions",
    "## Prohibited Actions",
    "## Stop and Escalation Criteria",
    "## Verification",
    "## Eval Status",
    "## Review Date",
    "## Risk and Tool Access Notes",
)


def _read(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def _markdown_section(text: str, heading: str) -> str:
    pattern = rf"(?ms)^## {re.escape(heading)}\n(?P<body>.*?)(?=^## |\Z)"
    match = re.search(pattern, text)
    assert match is not None, f"Missing section: {heading}"
    return match.group("body")


def _make_target_body(makefile: str, target: str) -> str:
    pattern = rf"(?ms)^\.PHONY: {re.escape(target)}\n{re.escape(target)}:\n(?P<body>.*?)(?=^\.PHONY: |\Z)"
    match = re.search(pattern, makefile)
    assert match is not None, f"Missing Makefile target: {target}"
    return match.group("body")


def test_harness_minimum_documents_exist_and_have_contract_header() -> None:
    """PR 1 must create a findable harness map, not only isolated notes."""

    for relative_path in REQUIRED_HARNESS_DOCS:
        path = REPO_ROOT / relative_path
        assert path.exists(), f"Missing harness document: {relative_path}"
        text = path.read_text(encoding="utf-8")

        for required_label in (
            "Status:",
            "Owner:",
            "Local checks:",
            "CI status:",
            "Related plans:",
            "Review cadence:",
        ):
            assert required_label in text, f"{relative_path} misses {required_label}"


def test_plan_memory_documents_exist() -> None:
    """Agents need a small searchable planning memory before refactor work grows."""

    for relative_path in REQUIRED_PLAN_MEMORY_DOCS:
        assert (REPO_ROOT / relative_path).exists(), f"Missing plan memory document: {relative_path}"


def test_initial_project_skill_sources_exist_with_governance_sections() -> None:
    """Repo-governed skills must be reviewable before they are treated as active."""

    for skill_name in INITIAL_PROJECT_SKILLS:
        relative_path = f"docs/harness/skills/{skill_name}/SKILL.md"
        path = REPO_ROOT / relative_path
        assert path.exists(), f"Missing repo-governed skill source: {relative_path}"
        text = path.read_text(encoding="utf-8")

        assert f"name: {skill_name}" in text
        for required_section in REQUIRED_SKILL_SECTIONS:
            assert required_section in text, f"{relative_path} misses {required_section}"


def test_skills_inventory_lists_sources_and_forward_evals_for_active_skills() -> None:
    """An active skill needs an inventory entry and manual forward-test evidence."""

    inventory = _read("docs/harness/SKILLS.md")
    evals = _read("docs/harness/SKILL_EVALS.md")

    for skill_name in INITIAL_PROJECT_SKILLS:
        source_path = f"docs/harness/skills/{skill_name}/SKILL.md"
        assert skill_name in inventory
        assert source_path in inventory
        inventory_line = next(line for line in inventory.splitlines() if f"| {skill_name} |" in line)
        assert "active" in inventory_line

        assert skill_name in evals
        eval_section = _markdown_section(evals, skill_name)
        for required_term in (
            "Scenario prompt",
            "Pressure condition",
            "Expected artifact",
            "Observed result",
            "Known gaps",
            "Reviewer",
            "Activation decision",
            "Next review date",
        ):
            assert required_term in eval_section, f"{skill_name} eval misses {required_term}"


def test_skill_governance_does_not_make_personal_skill_paths_authoritative() -> None:
    """Official GUSTAV behavior must be traceable to repository files."""

    governance_text = _read("docs/harness/SKILLS.md")
    skill_texts = [
        (REPO_ROOT / f"docs/harness/skills/{skill_name}/SKILL.md").read_text(encoding="utf-8")
        for skill_name in INITIAL_PROJECT_SKILLS
    ]
    combined = "\n".join([governance_text, *skill_texts])

    for forbidden_authority in (
        "~/.codex/skills",
        "/home/<user>/.codex",
        ".claude",
        "plugins/cache",
    ):
        assert forbidden_authority not in combined


def test_makefile_exposes_harness_minimum_and_signal_targets() -> None:
    """Local and CI checks need stable Make entry points."""

    makefile = _read("Makefile")
    for target in (
        "harness-minimum",
        "harness-signals",
        "test-fast",
        "test-db-security",
        "test-frontend-h5p",
        "test-full-prod-like",
    ):
        assert f".PHONY: {target}" in makefile
        assert f"{target}:" in makefile

    assert "backend/tests/test_harness_minimum_contract.py" in makefile
    assert "backend/tests/test_public_repo_safety_contract.py" in makefile
    assert "backend/tests/test_openapi_security_headers.py" in makefile
    assert "npm run check" in makefile
    assert "npm test" in makefile
    assert "docker compose config" in makefile


def test_harness_make_targets_are_safe_for_make_dry_run() -> None:
    """Harness targets should not run recursive make during `make -n` previews."""

    makefile = _read("Makefile")
    for target in ("harness-minimum", "harness-signals"):
        body = _make_target_body(makefile, target)
        assert "$(MAKE)" not in body


def test_harness_minimum_runs_makefile_target_contracts() -> None:
    """CI must catch accidental edits to the named harness gate composition."""

    makefile = _read("Makefile")
    body = _make_target_body(makefile, "harness-minimum")

    assert "backend/tests/test_makefile_targets.py" in body
    assert "backend/tests/test_docker_image_smoke_contract.py" in body
    assert "backend/tests/packaging/test_import_paths_contract.py" in body
    assert "backend/tests/packaging/test_test_import_paths_contract.py" in body
    assert "backend/tests/test_import_boundary_gate_contract.py" in body
    assert "backend/tests/test_openapi_route_surface_baseline.py" in body
    assert "backend/tests/test_architecture_boundary_gate_contract.py" in body
    assert "backend/tests/test_route_map_inventory_contract.py" in body
    assert "backend/tests/test_web_security_guards_contract.py" in body
    assert "backend/tests/test_auth_flow_contract.py" in body
    assert "backend/tests/test_auth_smoke_tool_contract.py" in body
    assert "backend/tests/test_runtime_auth_helpers_contract.py" in body
    assert "backend/tests/test_auth_claims_contract.py" in body
    assert "backend/tests/test_auth_session_contract.py" in body
    assert "backend/tests/test_csrf_tokens_contract.py" in body
    assert "backend/tests/test_internal_api_client_contract.py" in body
    assert "backend/tests/test_ssr_helpers_contract.py" in body
    assert "backend/tests/test_storage_local_hash_contract.py" in body
    assert "backend/tests/test_cli_authoring_contract.py" in body
    assert "backend/tests/test_security_headers_policy_contract.py" in body
    assert "backend/tests/test_runtime_config_contract.py" in body
    assert "backend/tests/test_app_composition_contract.py" in body
    assert "backend/tests/test_legacy_retirement_contract.py" in body
    assert "backend/tests/test_legacy_html_exit_wave1_contract.py" in body
    assert "backend/tests/test_teaching_live_h5p_matrix_cell_rendering.py" in body


def test_ci_runs_same_harness_minimum_entry_point_as_local_development() -> None:
    """PR-1 CI must not invent a separate path from local verification."""

    workflow_path = REPO_ROOT / ".github/workflows/harness-minimum.yml"
    assert workflow_path.exists(), "Missing harness minimum workflow"
    workflow = workflow_path.read_text(encoding="utf-8")

    assert "make harness-minimum" in workflow
    assert "backend/web/requirements.txt" in workflow
    assert "python-version: \"3.11\"" in workflow
    assert "cp .env.example .env" in workflow

    gitignore = _read(".gitignore")
    assert ".env" in gitignore
