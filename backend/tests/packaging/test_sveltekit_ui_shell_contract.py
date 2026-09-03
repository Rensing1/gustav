"""Contract tests for the Alpha-3 SvelteKit UI shell.

Why:
    The UI guide now fixes a shared `Top-Bar + Workspace + Sheet`
    shell, calmer workspace primitives and breadcrumb-ready header zones.
    These source-level tests keep the code aligned with that shell contract
    before broader UI finetuning continues.
"""

from __future__ import annotations

from pathlib import Path
import re


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_frontend_contains_shared_ui_shell_stylesheet() -> None:
    style_path = REPO_ROOT / "frontend" / "src" / "lib" / "styles" / "app.css"
    primitive_path = REPO_ROOT / "frontend" / "src" / "lib" / "styles" / "ui-primitives.css"
    token_path = REPO_ROOT / "frontend" / "src" / "lib" / "styles" / "theme-tokens.css"

    assert style_path.is_file(), f"Missing shared app stylesheet: {style_path}"

    src = style_path.read_text(encoding="utf-8")
    primitive_src = primitive_path.read_text(encoding="utf-8")
    token_src = token_path.read_text(encoding="utf-8")

    for needle in (
        ".app-shell",
        ".app-topbar",
        ".app-topbar-inner",
        ".brand-lockup",
        ".brand-logo",
        ".space-nav",
        ".account-menu",
        ".account-trigger",
        ".account-trigger__initial",
        ".workspace-topbar",
        ".workspace-breadcrumbs",
        ".workspace-section",
        ".workspace-grid",
        ".workspace-list",
        ".sheet-panel",
    ):
        assert needle in src, f"Expected shared UI shell token/class {needle!r} in {style_path}"

    for needle in (
        ".workspace-shell",
        ".workspace-inner",
        ".workspace-body",
        ".workspace-inner--compact",
        ".workspace-inner--wide",
        ".workspace-inner--canvas",
    ):
        assert needle in primitive_src, (
            f"Expected structural workspace primitive {needle!r} in {primitive_path}"
        )

    assert ".workspace-shell" not in src
    assert ".workspace-inner" not in src
    assert ".workspace-body" not in src

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
    ):
        assert needle in token_src, f"Expected global design token {needle!r} in {token_path}"


def test_root_layout_uses_current_shell_primitives() -> None:
    layout_path = REPO_ROOT / "frontend" / "src" / "routes" / "+layout.svelte"

    src = layout_path.read_text(encoding="utf-8")

    for needle in (
        'import "$lib/styles/index.css";',
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
    assert 'label: "Live"' in src, "Teacher navigation should expose the live room directly"
    assert 'label: "Diagnostik"' not in src, "Unreleased diagnostics must not appear in primary navigation"
    assert 'label: "Lehrenden-Welt"' not in src, "Teacher home should no longer be a primary teacher tab"


def test_learner_unit_workspace_styles_are_split_from_app_shell() -> None:
    entrypoint_path = REPO_ROOT / "frontend" / "src" / "lib" / "styles" / "index.css"
    app_style_path = REPO_ROOT / "frontend" / "src" / "lib" / "styles" / "app.css"
    learner_style_path = REPO_ROOT / "frontend" / "src" / "lib" / "styles" / "learning-unit.css"

    entrypoint_src = entrypoint_path.read_text(encoding="utf-8")
    app_src = app_style_path.read_text(encoding="utf-8")

    assert '@import "./learning-unit.css";' in entrypoint_src
    assert learner_style_path.is_file(), f"Missing learner-unit stylesheet: {learner_style_path}"
    assert ".learning-unit-space" not in app_src
    assert ".learning-task-workspace" not in app_src
    assert ".learning-submission-workspace" not in app_src


def test_teacher_workspace_styles_are_split_from_app_shell() -> None:
    entrypoint_path = REPO_ROOT / "frontend" / "src" / "lib" / "styles" / "index.css"
    app_style_path = REPO_ROOT / "frontend" / "src" / "lib" / "styles" / "app.css"
    teacher_style_path = REPO_ROOT / "frontend" / "src" / "lib" / "styles" / "teaching-workspace.css"

    entrypoint_src = entrypoint_path.read_text(encoding="utf-8")
    app_src = app_style_path.read_text(encoding="utf-8")

    assert '@import "./teaching-workspace.css";' in entrypoint_src
    assert teacher_style_path.is_file(), f"Missing teacher workspace stylesheet: {teacher_style_path}"
    assert ".teacher-flow-unit-node" not in app_src
    assert ".workspace-node-editor" not in app_src
    assert ".workspace-unit-commandbar-popover" not in app_src


def test_design_system_styles_are_split_into_ordered_responsibility_bundles() -> None:
    """The layout must load one ordered, iPadOS-15.3-compatible entrypoint."""

    layout_path = REPO_ROOT / "frontend" / "src" / "routes" / "+layout.svelte"
    styles_dir = REPO_ROOT / "frontend" / "src" / "lib" / "styles"
    layout_src = layout_path.read_text(encoding="utf-8")
    entrypoint_path = styles_dir / "index.css"

    assert 'import "$lib/styles/index.css";' in layout_src
    for old_import in (
        'import "$lib/styles/theme-tokens.css";',
        'import "$lib/styles/typography.css";',
        'import "$lib/styles/app.css";',
        'import "$lib/styles/ui-primitives.css";',
        'import "$lib/styles/learning-unit.css";',
        'import "$lib/styles/teaching-workspace.css";',
        'import "$lib/styles/auth-theme.css";',
    ):
        assert old_import not in layout_src

    assert entrypoint_path.is_file(), f"Missing design-system entrypoint: {entrypoint_path}"
    entrypoint_src = entrypoint_path.read_text(encoding="utf-8")
    expected_lines = [
        '@import "./theme-tokens.css";',
        '@import "./app.css";',
        '@import "./typography.css";',
        '@import "./ui-primitives.css";',
        '@import "./learning-unit.css";',
        '@import "./practice.css";',
        '@import "./teaching-workspace.css";',
        '@import "./auth-theme.css";',
        '@import "./overrides.css";',
    ]
    positions = [entrypoint_src.index(line) for line in expected_lines]
    assert positions == sorted(positions)
    assert "@layer" not in entrypoint_src
    assert 'import "$lib/styles/design-system.css";' not in layout_src

    token_css = (styles_dir / "theme-tokens.css").read_text(encoding="utf-8")
    typography_css = (styles_dir / "typography.css").read_text(encoding="utf-8")
    primitive_css = (styles_dir / "ui-primitives.css").read_text(encoding="utf-8")
    facade_css = (styles_dir / "design-system.css").read_text(encoding="utf-8")

    assert ":root" in token_css
    assert '[data-theme="dark"]' in token_css
    assert "h1," in typography_css
    assert ".workspace-heading h1" in typography_css
    assert ".workspace-topbar-action" in primitive_css
    assert ".workspace-outline" in primitive_css
    assert ".learning-unit-content-shell" not in primitive_css
    assert ".teacher-flow-unit-node" not in primitive_css
    assert "Compatibility note" in facade_css
    assert len(facade_css.splitlines()) < 40


def test_app_html_loads_approved_product_fonts() -> None:
    package_path = REPO_ROOT / "frontend" / "package.json"
    layout_path = REPO_ROOT / "frontend" / "src" / "routes" / "+layout.svelte"
    package_src = package_path.read_text(encoding="utf-8")
    layout_src = layout_path.read_text(encoding="utf-8")

    assert "@fontsource/inter" in package_src
    assert "@fontsource/space-grotesk" in package_src
    assert '@fontsource/inter' in layout_src
    assert '@fontsource/space-grotesk' in layout_src
    typography_src = (
        REPO_ROOT / "frontend" / "src" / "lib" / "styles" / "typography.css"
    ).read_text(encoding="utf-8")
    assert "font-family: var(--font-reading);" in typography_src
    assert "font-family: var(--font-display);" in typography_src


def test_global_design_tokens_have_one_owner() -> None:
    """Global product tokens may only be declared by theme-tokens.css.

    Component-scoped custom properties remain valid. The test deliberately
    inspects only global `:root` and theme blocks so feature styles can keep
    local variables without becoming another product-theme source.
    """

    styles_dir = REPO_ROOT / "frontend" / "src" / "lib" / "styles"
    token_path = styles_dir / "theme-tokens.css"
    global_token = re.compile(r"--(?:color|font|space|radius)-[a-z0-9-]+\s*:")
    css_block = re.compile(r"(?P<selectors>[^{}]+)\{(?P<body>[^{}]*)\}", re.DOTALL)
    offenders: list[str] = []

    for style_path in sorted(styles_dir.glob("*.css")):
        if style_path == token_path:
            continue
        source = style_path.read_text(encoding="utf-8")
        for match in css_block.finditer(source):
            selectors = match.group("selectors")
            if ":root" not in selectors and '[data-theme="' not in selectors:
                continue
            for declaration in global_token.findall(match.group("body")):
                offenders.append(f"{style_path.name}: {declaration.rstrip(':')}")

    assert offenders == [], "Global design tokens must live in theme-tokens.css:\n" + "\n".join(offenders)


def test_theme_tokens_keep_the_approved_contrast_contract() -> None:
    token_path = REPO_ROOT / "frontend" / "src" / "lib" / "styles" / "theme-tokens.css"
    src = token_path.read_text(encoding="utf-8")

    for declaration in (
        "--color-bg-base: #f9f9f9;",
        "--color-bg-surface: #ffffff;",
        "--color-text: #1a1c1c;",
        "--color-link: #b41f00;",
        "--color-accent: #ff512f;",
        "--color-border: #1b1b1b;",
        "--color-shadow: 4px 4px 0 0 rgba(27, 27, 27, 0.98);",
        '--font-display: "Space Grotesk", "Manrope", "Inter", sans-serif;',
        '--font-reading: "Inter", "Work Sans", "Nunito", sans-serif;',
        "--radius-s: 0;",
        "--radius-m: 0;",
    ):
        assert declaration in src


def test_topbar_theme_and_account_controls_share_one_chrome_rule() -> None:
    """Adjacent top-bar controls must not drift into different visual chrome."""

    style_path = REPO_ROOT / "frontend" / "src" / "lib" / "styles" / "overrides.css"
    src = style_path.read_text(encoding="utf-8")

    shared_selector = ".app-topbar-tools :is(.theme-toggle, .account-trigger)"
    assert shared_selector in src
    shared_rule = re.search(rf"{re.escape(shared_selector)}\s*\{{(?P<body>[^}}]+)\}}", src)
    assert shared_rule is not None
    body = shared_rule.group("body")
    for declaration in (
        "border-radius: 0;",
        "border: 1px solid var(--color-border);",
        "background: var(--color-bg-surface);",
        "box-shadow:",
    ):
        assert declaration in body


def test_frontend_styles_do_not_reintroduce_the_retired_soft_palette() -> None:
    """The warm paper and teal palette must not return through local CSS."""

    styles_dir = REPO_ROOT / "frontend" / "src" / "lib" / "styles"
    retired_values = (
        "#f6f0e7",
        "#fffaf3",
        "#2a6571",
        "#214f59",
        "#92b19a",
        "#a4c4ae",
        "#c1d8c4",
        "#262c2f",
        "#323a3f",
        "rgba(255, 253, 249, 0.96)",
        "rgba(42, 101, 113, 0.08)",
    )
    offenders: list[str] = []

    for style_path in sorted(styles_dir.glob("*.css")):
        source = style_path.read_text(encoding="utf-8").lower()
        for value in retired_values:
            if value in source:
                offenders.append(f"{style_path.name}: {value}")

    assert offenders == [], "Retired soft-design colors found:\n" + "\n".join(offenders)


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
        elif path.parts[-4:] == ("teaching", "courses", "[courseId]", "+page.svelte"):
            assert "teacher-course-workspace__section" in src, f"Expected flat course workspace sections in {path}"
            assert 'class="workspace-section"' not in src, f"Course detail should avoid card-like workspace sections in {path}"
        elif path.parts[-2:] == ("learning", "+page.svelte"):
            assert "workspace-page learning-home" in src, f"Expected learner home list shell in {path}"
            assert "QuietList" in src, f"Expected learner home to render the shared quiet list in {path}"
        else:
            assert "workspace-section" in src, f"Expected shared workspace section in {path}"
        assert 'class="panel"' not in src, f"Legacy panel styling should be removed in {path}"

    teaching_page_src = (
        REPO_ROOT / "frontend" / "src" / "routes" / "teaching" / "+page.svelte"
    ).read_text(encoding="utf-8")
    assert "PageActionHead" in teaching_page_src
    assert "QuietList" in teaching_page_src
    assert "TeacherLiveLauncher" in teaching_page_src
    assert "workspace-list" not in teaching_page_src
    assert "workspace-section--hero" not in teaching_page_src

    teaching_courses_src = (
        REPO_ROOT / "frontend" / "src" / "routes" / "teaching" / "courses" / "+page.svelte"
    ).read_text(encoding="utf-8")
    assert "workspace-course-catalog__row" in teaching_courses_src
    assert "PageActionHead" in teaching_courses_src
    assert "workspace-list" not in teaching_courses_src
    assert "workspace-toolbar" not in teaching_courses_src
    assert "Kurskontext mit Einheiten" not in teaching_courses_src
    assert 'class="workspace-section"' not in teaching_courses_src
    assert "metadata(course)" in teaching_courses_src
    assert "workspace-link-card--course" not in teaching_courses_src

    style_src = (REPO_ROOT / "frontend" / "src" / "lib" / "styles" / "teaching-workspace.css").read_text(
        encoding="utf-8"
    )
    assert ".workspace-course-catalog__row" in style_src
    assert ".teacher-catalog {" in style_src
    assert "grid-template-columns: var(--teacher-catalog-columns);" in style_src
    assert ".workspace-course-catalog {" in style_src
    assert ".workspace-course-catalog__scopes" in style_src
    assert "min-height: 4.75rem;" in style_src
    assert "gap: var(--space-4);" in style_src

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
    assert "headerAction" not in teaching_courses_loader
    assert 'pageTitle: "Kurse"' in teaching_courses_loader
    assert "hidePageHeading" in teaching_courses_loader


def test_teaching_courses_page_supports_create_action() -> None:
    page_server_path = (
        REPO_ROOT / "frontend" / "src" / "routes" / "teaching" / "courses" / "+page.server.ts"
    )
    src = page_server_path.read_text(encoding="utf-8")

    assert "export const actions" in src
    assert "/api/teaching/views/courses?" in src
    assert '"/api/teaching/courses"' in src
    assert 'method: "POST"' in src
    assert "includeSameOrigin: true" in src
    assert "school_year_start: schoolYearStart" in src
    assert '"/api/teaching/courses/archive-batch"' in src
