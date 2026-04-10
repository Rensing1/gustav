"""Contract tests for the Alpha-3 SvelteKit UI shell.

Why:
    The UI guide now fixes a shared `Top-Bar + Workspace + Sheet`
    shell, calmer workspace primitives and breadcrumb-ready header zones.
    These source-level tests keep the code aligned with that shell contract
    before broader UI finetuning continues.
"""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_frontend_contains_shared_ui_shell_stylesheet() -> None:
    style_path = REPO_ROOT / "frontend" / "src" / "lib" / "styles" / "app.css"

    assert style_path.is_file(), f"Missing shared app stylesheet: {style_path}"

    src = style_path.read_text(encoding="utf-8")

    for needle in (
        "--color-bg-base",
        "--color-bg-surface",
        "--color-link",
        "--color-link-hover",
        "--color-accent",
        "--color-text",
        "--space-4",
        "--radius-m",
        '[data-theme="dark"]',
        ".app-shell",
        ".app-topbar",
        ".app-topbar-inner",
        ".brand-lockup",
        ".brand-logo",
        ".space-nav",
        ".account-menu",
        ".account-trigger",
        ".account-trigger__initial",
        ".workspace-shell",
        ".workspace-topbar",
        ".workspace-breadcrumbs",
        ".workspace-section",
        ".workspace-grid",
        ".workspace-list",
        ".sheet-panel",
    ):
        assert needle in src, f"Expected shared UI shell token/class {needle!r} in {style_path}"


def test_root_layout_uses_alpha3_shell_primitives() -> None:
    layout_path = REPO_ROOT / "frontend" / "src" / "routes" / "+layout.svelte"

    src = layout_path.read_text(encoding="utf-8")

    for needle in (
        'import "$lib/styles/app.css";',
        'class="app-shell"',
        'class="app-topbar"',
        'class="app-topbar-inner"',
        'class="brand-lockup"',
        'class="workspace-shell"',
        'class="workspace-header"',
            'class="workspace-topbar"',
            'className="workspace-breadcrumbs"',
            'class="space-nav"',
            'aria-label="Hauptnavigation"',
            'src="/gustav-logo.png"',
            'class="account-menu"',
            "data.theme",
        "page.data.breadcrumbs",
        "page.data.pageTitle",
        "page.data.headerAction",
        "page.data.hidePageHeading",
        'class="workspace-topbar-action"',
    ):
        assert needle in src, f"Expected Alpha-3 shell primitive {needle!r} in {layout_path}"

    assert "status-chip" not in src, "The calmer shell should not keep top-right status pills"
    assert "rail-note" not in src, "The rail should avoid decorative product meta"
    assert "nav-meta" not in src, "Primary navigation should be label-first and almost text-free"
    assert "nav-short" not in src, "Primary navigation should not render separate abbreviation labels"
    assert "identity-card" not in src, "Account chrome should move into a compact menu"
    assert 'href="/auth/logout"' in src, "Logout should remain available from the account menu"
    assert "bind:this={accountMenu}" in src, "Account menu should expose its details element"
    assert "closeAccountMenuOnWindowClick" in src, "Account menu should close on outside clicks"
    assert "teacherNavItems" in src, "Teacher navigation should be derived separately from learner navigation"
    assert 'label: "Kurse"' in src, "Teacher navigation should expose courses directly"
    assert 'label: "Lerneinheiten"' in src, "Teacher navigation should expose units directly"
    assert 'label: "Lehrenden-Welt"' not in src, "Teacher home should no longer be a primary teacher tab"


def test_app_html_loads_nunito_font() -> None:
    package_path = REPO_ROOT / "frontend" / "package.json"
    layout_path = REPO_ROOT / "frontend" / "src" / "routes" / "+layout.svelte"
    package_src = package_path.read_text(encoding="utf-8")
    layout_src = layout_path.read_text(encoding="utf-8")

    assert "@fontsource/nunito" in package_src
    assert '@fontsource/nunito' in layout_src
    assert "font-family: var(--font-ui);" in (
        REPO_ROOT / "frontend" / "src" / "lib" / "styles" / "app.css"
    ).read_text(encoding="utf-8")


def test_room_pages_use_shared_workspace_primitives() -> None:
    page_paths = [
        REPO_ROOT / "frontend" / "src" / "routes" / "learning" / "+page.svelte",
        REPO_ROOT / "frontend" / "src" / "routes" / "teaching" / "+page.svelte",
        REPO_ROOT / "frontend" / "src" / "routes" / "diagnostics" / "+page.svelte",
        REPO_ROOT / "frontend" / "src" / "routes" / "live" / "+page.svelte",
        REPO_ROOT / "frontend" / "src" / "routes" / "teaching" / "courses" / "+page.svelte",
        REPO_ROOT
        / "frontend"
        / "src"
        / "routes"
        / "teaching"
        / "courses"
        / "[courseId]"
        / "+page.svelte",
        REPO_ROOT
        / "frontend"
        / "src"
        / "routes"
        / "teaching"
        / "courses"
        / "[courseId]"
        / "members"
        / "+page.svelte",
    ]

    for path in page_paths:
        src = path.read_text(encoding="utf-8")
        if path.parts[-3:] == ("teaching", "courses", "+page.svelte"):
            assert "workspace-section" not in src, f"Course index should now avoid an outer workspace section in {path}"
        elif path.parts[-2:] == ("learning", "+page.svelte"):
            assert "workspace-page learning-home" in src, f"Expected learner home list shell in {path}"
            assert "QuietList" in src, f"Expected learner home to render the shared quiet list in {path}"
        else:
            assert "workspace-section" in src, f"Expected shared workspace section in {path}"
        assert 'class="panel"' not in src, f"Legacy panel styling should be removed in {path}"

    teaching_page_src = (
        REPO_ROOT / "frontend" / "src" / "routes" / "teaching" / "+page.svelte"
    ).read_text(encoding="utf-8")
    assert "workspace-list" in teaching_page_src
    assert "workspace-section--hero" not in teaching_page_src

    teaching_courses_src = (
        REPO_ROOT / "frontend" / "src" / "routes" / "teaching" / "courses" / "+page.svelte"
    ).read_text(encoding="utf-8")
    assert "workspace-grid" in teaching_courses_src
    assert "workspace-metrics" in teaching_courses_src
    assert "workspace-list" not in teaching_courses_src
    assert "workspace-toolbar" not in teaching_courses_src
    assert "Kurskontext mit Einheiten" not in teaching_courses_src
    assert 'class="workspace-section"' not in teaching_courses_src
    assert "courseMeta(course)" in teaching_courses_src
    assert "workspace-link-card--course" in teaching_courses_src

    style_src = (REPO_ROOT / "frontend" / "src" / "lib" / "styles" / "app.css").read_text(
        encoding="utf-8"
    )
    assert ".workspace-grid--courses" in style_src
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in style_src
    assert ".workspace-link-card--course" in style_src
    assert "min-height: 5.8rem;" in style_src
    assert "gap: 0.28rem;" in style_src

    root_page_src = (REPO_ROOT / "frontend" / "src" / "routes" / "+page.svelte").read_text(
        encoding="utf-8"
    )
    assert "AuthFrame" in root_page_src
    assert "workspace-section" not in root_page_src


def test_teaching_course_routes_define_breadcrumb_data() -> None:
    page_server_paths = [
        REPO_ROOT
        / "frontend"
        / "src"
        / "routes"
        / "teaching"
        / "courses"
        / "[courseId]"
        / "+page.server.ts",
        REPO_ROOT
        / "frontend"
        / "src"
        / "routes"
        / "teaching"
        / "courses"
        / "[courseId]"
        / "members"
        / "+page.server.ts",
        REPO_ROOT
        / "frontend"
        / "src"
        / "routes"
        / "teaching"
        / "units"
        / "+page.server.ts",
        REPO_ROOT
        / "frontend"
        / "src"
        / "routes"
        / "teaching"
        / "units"
        / "[unitId]"
        / "+page.server.ts",
        REPO_ROOT
        / "frontend"
        / "src"
        / "routes"
        / "live"
        / "courses"
        / "[courseId]"
        / "+page.server.ts",
        REPO_ROOT
        / "frontend"
        / "src"
        / "routes"
        / "live"
        / "courses"
        / "[courseId]"
        / "units"
        / "[unitId]"
        / "+page.server.ts",
    ]

    for path in page_server_paths:
        src = path.read_text(encoding="utf-8")
        assert "breadcrumbs" in src, f"Expected breadcrumb data contract in {path}"
        assert "pageTitle" in src, f"Expected explicit page title in {path}"

    teaching_courses_loader = (
        REPO_ROOT / "frontend" / "src" / "routes" / "teaching" / "courses" / "+page.server.ts"
    ).read_text(encoding="utf-8")
    assert "pageTitle" in teaching_courses_loader
    assert "breadcrumbs" in teaching_courses_loader
    assert "headerAction" in teaching_courses_loader
    assert "hidePageHeading" in teaching_courses_loader


def test_teaching_courses_page_supports_create_action() -> None:
    page_server_path = (
        REPO_ROOT / "frontend" / "src" / "routes" / "teaching" / "courses" / "+page.server.ts"
    )
    src = page_server_path.read_text(encoding="utf-8")

    assert "export const actions" in src
    assert '"/api/teaching/views/courses?limit=25&offset=0"' in src
    assert '"/api/teaching/courses"' in src
    assert 'method: "POST"' in src
    assert "includeSameOrigin: true" in src
