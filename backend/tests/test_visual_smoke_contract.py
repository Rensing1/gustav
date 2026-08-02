from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_frontend_visual_smoke_specs_include_approved_design_snapshots() -> None:
    e2e_dir = REPO_ROOT / "frontend" / "e2e"
    specs = sorted(e2e_dir.glob("*.spec.ts"))
    visual_specs = [path for path in specs if "@visual-smoke" in path.read_text(encoding="utf-8")]

    assert visual_specs, "Expected at least one Playwright spec tagged with @visual-smoke"

    design_spec = e2e_dir / "design-system.spec.ts"
    design_source = design_spec.read_text(encoding="utf-8")
    assert "@design-system" in design_source
    assert "toHaveScreenshot" in design_source
    assert "document.fonts.ready" in design_source
    assert 'animations: "disabled"' in design_source
    assert "toMatchSnapshot" not in design_source

    snapshot_dir = e2e_dir / "design-system.spec.ts-snapshots"
    expected_snapshots = {
        f"ui-lab-{theme}-{viewport}-chromium-linux.png"
        for theme in ("light", "dark")
        for viewport in ("desktop", "mobile")
    }
    assert {path.name for path in snapshot_dir.glob("*.png")} == expected_snapshots


def test_visual_smoke_support_helpers_cover_auth_seed_and_layout_sanity() -> None:
    support_dir = REPO_ROOT / "frontend" / "e2e" / "support"
    required_support_files = {
        "e2e-env.ts": ("loadLocalEnvDefaults", "webBase", "emailDomain"),
        "keycloak.ts": ("ensureTeacherUser", "ensureLearnerUser"),
        "auth.ts": ("login", "/api/me"),
        "api.ts": ("apiHeaders", "expectApiOk"),
        "seed-data.ts": ("seedTeacherVisualSmokeUnit", "seedLearnerVisualSmokeCourse", "seedH5pVisualSmokeUnit"),
        "layout-sanity.ts": ("expectVisiblePageShell", "expectNoViewportOverflow", "expectInteractiveSurface"),
    }

    for file_name, required_terms in required_support_files.items():
        source = (support_dir / file_name).read_text(encoding="utf-8")
        for required_term in required_terms:
            assert required_term in source


def test_visual_smoke_spec_uses_support_helpers_for_teacher_learner_and_h5p_surfaces() -> None:
    source = (REPO_ROOT / "frontend" / "e2e" / "visual-smoke.spec.ts").read_text(encoding="utf-8")

    for required_import in (
        "./support/auth",
        "./support/e2e-env",
        "./support/layout-sanity",
        "./support/seed-data",
    ):
        assert required_import in source

    for required_surface in (
        "@visual-smoke auth shell pages",
        "@visual-smoke teacher workspace",
        "@visual-smoke learner workspace",
        "@visual-smoke h5p workspace",
    ):
        assert required_surface in source

    assert "function expectVisiblePageShell" not in source


def test_visual_smoke_has_reproducible_browser_bootstrap_and_preflight() -> None:
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    preflight = REPO_ROOT / "frontend" / "tooling" / "check-playwright-browser.mjs"

    assert ".PHONY: playwright-bootstrap" in makefile
    assert "npx playwright install chromium" in makefile
    visual_body = makefile.split("test-visual-smoke:", 1)[1].split(".PHONY:", 1)[0]
    assert "tooling/check-playwright-browser.mjs" in visual_body
    assert preflight.exists()
    source = preflight.read_text(encoding="utf-8")
    assert "chromium.executablePath()" in source
    assert "make playwright-bootstrap" in source
