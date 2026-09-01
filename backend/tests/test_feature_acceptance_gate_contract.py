from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _target_body(makefile: str, target: str) -> str:
    return makefile.split(f"{target}:", 1)[1].split(".PHONY:", 1)[0]


def test_makefile_exposes_a_mandatory_feature_acceptance_profile() -> None:
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")

    assert ".PHONY: test-feature-acceptance" in makefile
    acceptance_body = _target_body(makefile, "test-feature-acceptance")
    assert "backend.tools.feature_acceptance" in acceptance_body
    assert '--feature "$(FEATURE)"' in acceptance_body

    assert ".PHONY: test-feature-regression" in makefile
    regression_body = _target_body(makefile, "test-feature-regression")
    assert "backend.tools.feature_acceptance" in regression_body
    assert "--all" in regression_body

    assert ".PHONY: test-feature-detail" in makefile
    detail_body = _target_body(makefile, "test-feature-detail")
    assert "--profile detail" in detail_body
    assert '--feature "$(FEATURE)"' in detail_body

    assert ".PHONY: test-feature-details" in makefile
    details_body = _target_body(makefile, "test-feature-details")
    assert "--profile detail" in details_body
    assert "--all" in details_body

    assert ".PHONY: verify-feature" in makefile
    verify_feature_body = _target_body(makefile, "verify-feature")
    assert "backend.tools.feature_acceptance validate" in verify_feature_body
    assert "$(MAKE) verify" in verify_feature_body
    assert "$(MAKE) test-feature-acceptance" in verify_feature_body
    assert verify_feature_body.index("feature_acceptance validate") < verify_feature_body.index(
        "$(MAKE) verify"
    )
    assert verify_feature_body.index("$(MAKE) verify") < verify_feature_body.index(
        "$(MAKE) test-feature-acceptance"
    )

    full_prod_body = _target_body(makefile, "test-full-prod-like")
    assert "$(MAKE) verify" in full_prod_body
    assert "$(MAKE) test-feature-regression" in full_prod_body
    assert "$(MAKE) verify-feature" not in full_prod_body

    help_body = _target_body(makefile, "help")
    assert "test-feature-acceptance" in help_body
    assert "test-feature-regression" in help_body
    assert "test-feature-detail" in help_body
    assert "verify-feature" in help_body


def test_feature_acceptance_has_an_authenticated_browser_journey() -> None:
    specs = sorted((REPO_ROOT / "frontend" / "e2e").glob("*.spec.ts"))
    acceptance_sources = [
        path.read_text(encoding="utf-8")
        for path in specs
        if "@feature-acceptance" in path.read_text(encoding="utf-8")
    ]

    assert acceptance_sources, (
        "Expected at least one Playwright spec tagged with @feature-acceptance"
    )
    assert any(
        "ensureTeacherUser" in source and "login(" in source for source in acceptance_sources
    )


def test_feature_acceptance_specs_use_cleanup_and_avoid_visual_or_live_ai_contracts() -> None:
    specs = sorted((REPO_ROOT / "frontend" / "e2e").glob("*.spec.ts"))
    acceptance_specs = [
        path for path in specs if "@feature-acceptance" in path.read_text(encoding="utf-8")
    ]

    assert acceptance_specs
    for path in acceptance_specs:
        source = path.read_text(encoding="utf-8")
        assert 'from "./support/feature-test"' in source, path.name
        assert "toHaveScreenshot" not in source, path.name
        assert "countGermanSentences" not in source, path.name


def test_feature_gate_keeps_one_core_journey_per_spec_and_excludes_responsive_detail() -> None:
    specs = sorted((REPO_ROOT / "frontend" / "e2e").glob("*.spec.ts"))

    for path in specs:
        source = path.read_text(encoding="utf-8")
        assert source.count("@feature-acceptance") <= 1, path.name
        if "responsive" in path.stem:
            assert "@feature-acceptance" not in source, path.name


def test_demoted_browser_journeys_remain_explicitly_runnable_as_feature_details() -> None:
    expected = {
        "cli-authoring.spec.ts": "browser cookie flow persists H5P editor JSON",
        "course-archive.spec.ts": "permanently deletes",
        "learner-task-finalization.spec.ts": "uploaded file",
        "learner-task-responsive.spec.ts": "@feature-detail",
    }

    for name, journey in expected.items():
        source = (REPO_ROOT / "frontend" / "e2e" / name).read_text(encoding="utf-8")
        assert "@feature-detail" in source, name
        assert journey in source, name


def test_ai_acceptance_requests_feedback_through_the_browser_before_local_completion() -> None:
    navigation = (REPO_ROOT / "frontend" / "e2e" / "learner-navigation.spec.ts").read_text(
        encoding="utf-8"
    )
    practice = (REPO_ROOT / "frontend" / "e2e" / "practice-session.spec.ts").read_text(
        encoding="utf-8"
    )

    assert 'getByRole("button", { name: "Rückmeldung einholen" }).click()' in navigation
    assert "holdProviderWorker" in navigation
    assert "completeQueuedFeedbackDeterministically" in navigation
    assert navigation.index('name: "Rückmeldung einholen"') < navigation.index(
        "await completeQueuedFeedbackDeterministically"
    )

    assert "seedLearnerPracticeCourse" in practice
    assert "`Practice ${unique}`,\n      false" not in practice
    assert 'getByRole("button", { name: "Antwort prüfen" }).click()' in practice
    assert "holdProviderWorker" in practice
    assert "completeQueuedFeedbackDeterministically" in practice


def test_agent_and_harness_docs_make_the_feature_gate_a_completion_rule() -> None:
    agents_path = REPO_ROOT / "AGENTS.md"
    agent_playbook = (REPO_ROOT / "docs" / "harness" / "AGENT_PLAYBOOK.md").read_text(
        encoding="utf-8"
    )
    strategy = (REPO_ROOT / "docs" / "harness" / "TEST_STRATEGY.md").read_text(encoding="utf-8")
    quality_gates = (REPO_ROOT / "docs" / "harness" / "QUALITY_GATES.md").read_text(
        encoding="utf-8"
    )

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
