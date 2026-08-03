from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _target_body(makefile: str, target: str) -> str:
    return makefile.split(f"{target}:", 1)[1].split(".PHONY:", 1)[0]


def test_makefile_exposes_a_mandatory_feature_acceptance_profile() -> None:
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")

    assert ".PHONY: test-feature-acceptance" in makefile
    acceptance_body = _target_body(makefile, "test-feature-acceptance")
    assert "tooling/check-playwright-browser.mjs" in acceptance_body
    assert "--grep @feature-acceptance" in acceptance_body

    assert ".PHONY: verify-feature" in makefile
    verify_feature_body = _target_body(makefile, "verify-feature")
    assert "$(MAKE) verify" in verify_feature_body
    assert "$(MAKE) test-feature-acceptance" in verify_feature_body
    assert verify_feature_body.index("$(MAKE) verify") < verify_feature_body.index("$(MAKE) test-feature-acceptance")

    full_prod_body = _target_body(makefile, "test-full-prod-like")
    assert "$(MAKE) verify-feature" in full_prod_body
    assert "$(MAKE) verify\n" not in full_prod_body

    help_body = _target_body(makefile, "help")
    assert "test-feature-acceptance" in help_body
    assert "verify-feature" in help_body


def test_feature_acceptance_has_an_authenticated_browser_journey() -> None:
    specs = sorted((REPO_ROOT / "frontend" / "e2e").glob("*.spec.ts"))
    acceptance_sources = [
        path.read_text(encoding="utf-8")
        for path in specs
        if "@feature-acceptance" in path.read_text(encoding="utf-8")
    ]

    assert acceptance_sources, "Expected at least one Playwright spec tagged with @feature-acceptance"
    assert any("ensureTeacherUser" in source and "login(" in source for source in acceptance_sources)


def test_agent_and_harness_docs_make_the_feature_gate_a_completion_rule() -> None:
    agents_path = REPO_ROOT / "AGENTS.md"
    agent_playbook = (REPO_ROOT / "docs" / "harness" / "AGENT_PLAYBOOK.md").read_text(encoding="utf-8")
    strategy = (REPO_ROOT / "docs" / "harness" / "TEST_STRATEGY.md").read_text(encoding="utf-8")
    quality_gates = (REPO_ROOT / "docs" / "harness" / "QUALITY_GATES.md").read_text(encoding="utf-8")

    for required_term in (
        "make verify-feature",
        "@feature-acceptance",
        "BDD-Szenarien",
        "authentifizierten Browser-Rundlauf",
    ):
        assert required_term in agent_playbook

    # The local instruction file is intentionally not versioned, but when present it
    # must carry the same completion rule as the public project playbook.
    if agents_path.exists():
        agents = agents_path.read_text(encoding="utf-8")
        assert "make verify-feature" in agents
        assert "@feature-acceptance" in agents
        assert "authentifizierten Browser-Rundlauf" in agents

    for document in (strategy, quality_gates):
        assert "make verify-feature" in document
        assert "@feature-acceptance" in document
        assert "nutzerseitig" in document
