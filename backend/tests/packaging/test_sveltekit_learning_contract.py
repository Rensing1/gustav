"""Contract tests for the SvelteKit learner space after retiring FastAPI SSR."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_learning_sveltekit_routes_exist() -> None:
    course_loader = REPO_ROOT / "frontend" / "src" / "routes" / "learning" / "courses" / "[courseId]" / "+page.server.ts"
    course_page = REPO_ROOT / "frontend" / "src" / "routes" / "learning" / "courses" / "[courseId]" / "+page.svelte"
    unit_loader = REPO_ROOT / "frontend" / "src" / "routes" / "learning" / "courses" / "[courseId]" / "units" / "[unitId]" / "+page.server.ts"
    unit_page = REPO_ROOT / "frontend" / "src" / "routes" / "learning" / "courses" / "[courseId]" / "units" / "[unitId]" / "+page.svelte"
    h5p_component = REPO_ROOT / "frontend" / "src" / "lib" / "components" / "H5PTaskPlayer.svelte"
    h5p_bridge = REPO_ROOT / "frontend" / "src" / "routes" / "bff" / "h5p" / "submissions" / "+server.ts"

    for path in (course_loader, course_page, unit_loader, unit_page, h5p_component, h5p_bridge):
        assert path.is_file(), f"Missing learner-space artifact: {path}"

    loader_src = unit_loader.read_text(encoding="utf-8")
    page_src = unit_page.read_text(encoding="utf-8")
    component_src = h5p_component.read_text(encoding="utf-8")

    assert "/api/learning/courses/" in loader_src
    assert "/upload-intents" in loader_src
    assert "/submissions" in loader_src
    assert "H5PTaskPlayer" in page_src
    assert "/h5p/player/model" in component_src
    assert "/bff/h5p/submissions" in component_src
    assert "@vite-ignore" in component_src


def test_h5p_service_knows_frontend_bff_cookie_bridge() -> None:
    compose_path = REPO_ROOT / "docker-compose.yml"
    env_example_path = REPO_ROOT / ".env.example"
    h5p_server_path = REPO_ROOT / "h5p-service" / "server.mjs"

    compose_src = compose_path.read_text(encoding="utf-8")
    env_src = env_example_path.read_text(encoding="utf-8")
    server_src = h5p_server_path.read_text(encoding="utf-8")

    assert "GUSTAV_FRONTEND_INTERNAL_BASE" in compose_src
    assert "FRONTEND_SESSION_COOKIE_NAME" in compose_src
    assert "gustav_bff_session" in env_src
    assert "gustavFrontendInternalBase" in server_src
    assert "frontendSessionCookieName" in server_src
    assert "/internal/h5p/me" in server_src
