"""Contract tests for the SvelteKit entry and room guards.

Why:
    The new Browser-BFF must become the real product entry. These source-level
    tests lock in three behaviors:
    - `/` shows a public auth entry when no session exists.
    - `/` redirects authenticated users into the role-specific start target.
    - room routes reuse the layout bootstrap through a shared guard helper.
    - diagnostics gains a top-level server loader instead of a static orphan page.
"""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_root_route_is_public_but_redirects_authenticated_users() -> None:
    root_loader_path = REPO_ROOT / "frontend" / "src" / "routes" / "+page.server.ts"
    root_page_path = REPO_ROOT / "frontend" / "src" / "routes" / "+page.svelte"
    guard_path = REPO_ROOT / "frontend" / "src" / "lib" / "server" / "guards.ts"

    assert root_loader_path.is_file(), f"Missing root redirect loader: {root_loader_path}"
    assert root_page_path.is_file(), f"Missing root auth entry page: {root_page_path}"
    assert guard_path.is_file(), f"Missing shared frontend guard helper: {guard_path}"

    root_loader_src = root_loader_path.read_text(encoding="utf-8")
    root_page_src = root_page_path.read_text(encoding="utf-8")
    guard_src = guard_path.read_text(encoding="utf-8")

    assert "parent()" in root_loader_src
    assert "redirect(" in root_loader_src
    assert "bootstrap.start_target" in root_loader_src
    assert "if (bootstrap)" in root_loader_src
    assert "return {" in root_loader_src
    assert '"/api/app/session-bootstrap"' not in root_loader_src
    assert "readTypedJsonOrNull" not in root_loader_src

    for needle in (
        "Anmelden",
        "Registrieren",
        "Passwort vergessen",
        '"/auth/login"',
        '"/register"',
        '"/forgot-password"',
    ):
        assert needle in root_page_src, f"Expected public auth entry marker {needle!r} in {root_page_path}"

    assert "requireSessionBootstrap" in guard_src
    assert "requireSpaceBootstrap" in guard_src
    assert "requireParentSessionBootstrap" in guard_src
    assert "requireParentSpaceBootstrap" in guard_src
    assert '"/api/app/session-bootstrap"' in guard_src
    assert "/auth/continue?redirect=" in guard_src
    assert "redirect" in guard_src


def test_room_loaders_use_shared_space_guard() -> None:
    diagnostics_loader_path = REPO_ROOT / "frontend" / "src" / "routes" / "diagnostics" / "+page.server.ts"
    route_loader_paths = [
        REPO_ROOT / "frontend" / "src" / "routes" / "learning" / "+page.server.ts",
        REPO_ROOT / "frontend" / "src" / "routes" / "teaching" / "+page.server.ts",
        REPO_ROOT / "frontend" / "src" / "routes" / "diagnostics" / "+page.server.ts",
        REPO_ROOT / "frontend" / "src" / "routes" / "live" / "+page.server.ts",
        REPO_ROOT / "frontend" / "src" / "routes" / "learning" / "courses" / "[courseId]" / "+page.server.ts",
        REPO_ROOT / "frontend" / "src" / "routes" / "learning" / "courses" / "[courseId]" / "units" / "[unitId]" / "+page.server.ts",
        REPO_ROOT / "frontend" / "src" / "routes" / "teaching" / "courses" / "+page.server.ts",
        REPO_ROOT / "frontend" / "src" / "routes" / "teaching" / "courses" / "[courseId]" / "+page.server.ts",
        REPO_ROOT / "frontend" / "src" / "routes" / "teaching" / "courses" / "[courseId]" / "members" / "+page.server.ts",
        REPO_ROOT / "frontend" / "src" / "routes" / "teaching" / "units" / "+page.server.ts",
        REPO_ROOT / "frontend" / "src" / "routes" / "teaching" / "units" / "[unitId]" / "+page.server.ts",
        REPO_ROOT / "frontend" / "src" / "routes" / "diagnostics" / "courses" / "[courseId]" / "+page.server.ts",
        REPO_ROOT / "frontend" / "src" / "routes" / "diagnostics" / "learners" / "[studentSub]" / "+page.server.ts",
        REPO_ROOT / "frontend" / "src" / "routes" / "live" / "courses" / "[courseId]" / "+page.server.ts",
        REPO_ROOT / "frontend" / "src" / "routes" / "live" / "courses" / "[courseId]" / "units" / "[unitId]" / "+page.server.ts",
    ]

    assert diagnostics_loader_path.is_file(), f"Missing diagnostics room loader: {diagnostics_loader_path}"

    for path in route_loader_paths:
        src = path.read_text(encoding="utf-8")
        assert "parent" in src, f"Route loader must receive parent bootstrap: {path}"
        assert "requireParentSpaceBootstrap" in src, f"Route loader must use parent space guard: {path}"
