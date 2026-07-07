from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_frontend_visual_smoke_specs_are_tagged_and_not_snapshot_based() -> None:
    e2e_dir = REPO_ROOT / "frontend" / "e2e"
    specs = sorted(e2e_dir.glob("*.spec.ts"))
    visual_specs = [path for path in specs if "@visual-smoke" in path.read_text(encoding="utf-8")]

    assert visual_specs, "Expected at least one Playwright spec tagged with @visual-smoke"

    combined = "\n".join(path.read_text(encoding="utf-8") for path in visual_specs)
    assert "toHaveScreenshot" not in combined
    assert "toMatchSnapshot" not in combined


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
