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
    h5p_runtime_loader = REPO_ROOT / "frontend" / "src" / "lib" / "runtime" / "h5p-webcomponents.ts"
    task_card = REPO_ROOT / "frontend" / "src" / "lib" / "components" / "learning-unit" / "LearningTaskCard.svelte"
    h5p_bridge = REPO_ROOT / "frontend" / "src" / "routes" / "bff" / "h5p" / "submissions" / "+server.ts"

    for path in (course_loader, course_page, unit_loader, unit_page, h5p_component, h5p_runtime_loader, task_card, h5p_bridge):
        assert path.is_file(), f"Missing learner-space artifact: {path}"

    loader_src = unit_loader.read_text(encoding="utf-8")
    page_src = unit_page.read_text(encoding="utf-8")
    component_src = h5p_component.read_text(encoding="utf-8")
    runtime_loader_src = h5p_runtime_loader.read_text(encoding="utf-8")
    task_card_src = task_card.read_text(encoding="utf-8")

    assert "/api/learning/courses/" in loader_src
    assert "/upload-intents" in loader_src
    assert "/submissions" in loader_src
    assert "LearningUnitContentWorkspace" in page_src
    assert "H5PTaskPlayer" in task_card_src
    assert "/h5p/player/model" in component_src
    assert "/bff/h5p/submissions" in component_src
    assert "loadH5PWebcomponentsModule" in component_src
    assert "/h5p/webcomponents/index.js" in runtime_loader_src
    assert "@vite-ignore" in runtime_loader_src
    assert "Deine Sitzung ist abgelaufen." in component_src


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


def test_teacher_h5p_editor_static_entry_is_shipped_with_frontend() -> None:
    component_path = REPO_ROOT / "frontend" / "src" / "lib" / "components" / "TeacherH5PTaskEditor.svelte"
    runtime_loader_path = REPO_ROOT / "frontend" / "src" / "lib" / "runtime" / "h5p-task-editor.ts"
    frontend_static_path = REPO_ROOT / "frontend" / "static" / "js" / "h5p_task_editor.js"
    backend_source_path = REPO_ROOT / "backend" / "web" / "static" / "js" / "h5p_task_editor.js"

    component_src = component_path.read_text(encoding="utf-8")
    runtime_loader_src = runtime_loader_path.read_text(encoding="utf-8")
    frontend_static_src = frontend_static_path.read_text(encoding="utf-8")
    backend_source_src = backend_source_path.read_text(encoding="utf-8")

    assert "loadH5PTaskEditorModule" in component_src
    assert '/static/js/h5p_task_editor.js' not in component_src
    assert '/js/h5p_task_editor.js' in runtime_loader_src
    assert "@vite-ignore" in runtime_loader_src
    assert "Content-ID" not in component_src
    assert 'data-role="h5p-import"' in component_src
    assert 'data-role="h5p-reset"' in component_src
    assert "data-task-h5p-base-url" in component_src
    assert "Deine Sitzung ist abgelaufen." in component_src
    assert "/h5p/editor/model" not in frontend_static_src
    assert "/h5p/contents/" not in frontend_static_src
    assert "/h5p/contents" not in frontend_static_src
    assert "/api/teaching/units/" in frontend_static_src
    assert frontend_static_src == backend_source_src


def test_learning_h5p_task_uses_native_task_body_without_special_support_section() -> None:
    task_card_path = REPO_ROOT / "frontend" / "src" / "lib" / "components" / "learning-unit" / "LearningTaskCard.svelte"
    task_card_src = task_card_path.read_text(encoding="utf-8")

    assert "Interaktive Aufgabe" not in task_card_src
    assert "learning-work-item__support" not in task_card_src
    assert "task.kind === \"h5p\"" in task_card_src
    assert "H5PTaskPlayer" in task_card_src
