"""Contracts for FastAPI app composition."""

from __future__ import annotations

import importlib
import inspect
from pathlib import Path

from fastapi.routing import APIRoute


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MAIN_SOURCE = PROJECT_ROOT / "backend" / "web" / "main.py"


def test_main_app_delegates_shell_composition_to_dedicated_module() -> None:
    import backend.web.main as main
    from backend.web import app_composition

    source = MAIN_SOURCE.read_text(encoding="utf-8")

    assert hasattr(app_composition, "create_app_shell")
    assert hasattr(app_composition, "mount_static_files")
    assert hasattr(app_composition, "include_core_routers")
    assert hasattr(app_composition, "bootstrap_runtime_environment")
    assert hasattr(app_composition, "running_under_pytest")
    assert hasattr(main, "create_app")
    assert source.count("app = create_app()") == 1
    source_lines = [line.strip() for line in source.splitlines()]
    assert "app = create_app_shell()" not in source_lines
    assert "mount_static_files(app, static_dir)" not in source_lines
    assert main.app.title == "GUSTAV alpha-2"
    assert main.app.version == "0.0.2"
    assert any(getattr(route, "path", "") == "/static" for route in main.app.routes)


def test_main_app_keeps_core_router_and_local_routes_registered() -> None:
    import backend.web.main as main

    operations = {
        (route.path, method)
        for route in main.app.routes
        if isinstance(route, APIRoute)
        for method in route.methods
    }

    for expected in (
        ("/auth/login", "GET"),
        ("/api/app/session-bootstrap", "GET"),
        ("/api/learning/courses", "GET"),
        ("/api/teaching/courses", "GET"),
        ("/api/users/search", "GET"),
        ("/internal/health/openai", "GET"),
        ("/health", "GET"),
    ):
        assert expected in operations

    assert ("/", "GET") not in operations
    assert ("/about", "GET") not in operations


def test_main_delegates_runtime_bootstrap_to_app_composition() -> None:
    """Dotenv and startup guards are app-composition concerns, not route code."""

    source = MAIN_SOURCE.read_text(encoding="utf-8")

    assert "bootstrap_runtime_environment()" in source
    assert "from dotenv import load_dotenv" not in source
    assert "def _should_load_dotenv" not in source
    assert "def _running_under_pytest" not in source


def test_main_entrypoint_does_not_keep_removed_learning_ui_helpers() -> None:
    """Removed legacy Learning HTML routes must not leave dead helpers behind."""

    source = MAIN_SOURCE.read_text(encoding="utf-8")

    for retired_marker in (
        "_DUMMY_COURSES_STORE",
        "_DUMMY_UNITS_STORE",
        "_DUMMY_SECTIONS_STORE",
        "def _get_session_id",
        "def _build_task_submit_form_html",
        "def _server_side_prepare_submission_upload",
        "def _build_history_entry_from_record",
        "def _render_analysis_criteria_section",
        "def _render_submission_telemetry",
        "def _normalise_criterion_score",
        "def _render_history_entries_html",
        "def _render_analysis_in_progress_hint",
        "def _is_legacy_extracted_text_placeholder",
        "def _render_task_history_poll_element",
        "def _render_submission_text_container",
        "def _render_submission_result_container",
        "def _public_submission_failure_message",
        "def _render_submission_result_static_html",
        "def _render_submission_artifact_container",
        "def _strip_task_history_outer_wrapper",
    ):
        assert retired_marker not in source

    assert "import hashlib" not in source
    assert "import mimetypes" not in source
    assert "import asyncio" not in source
    assert "from backend.web.components.base import Component" not in source
    assert "from backend.web.components.pages import SciencePage" not in source


def test_main_delegates_health_page_to_dedicated_router() -> None:
    """Health routing is a basic-page concern; product shell pages are retired."""

    import backend.web.main as main

    basic_pages = importlib.import_module("backend.web.routes.basic_pages")

    source = MAIN_SOURCE.read_text(encoding="utf-8")
    wiring_source = (PROJECT_ROOT / "backend/web/main_router_wiring.py").read_text(encoding="utf-8")
    operations = {
        (route.path, method)
        for route in main.app.routes
        if isinstance(route, APIRoute)
        for method in route.methods
    }

    assert hasattr(basic_pages, "create_basic_pages_router")
    assert "create_basic_pages_router(" in wiring_source
    assert "create_basic_pages_router(" not in source
    assert "async def home(" not in source
    assert "async def health_check(" not in source
    assert "async def about_page(" not in source
    assert ("/", "GET") not in operations
    assert ("/health", "GET") in operations
    assert ("/about", "GET") not in operations


def test_html_layout_response_is_owned_by_dedicated_module() -> None:
    """HTMX-aware layout responses are shared web rendering infrastructure."""

    layout_response = importlib.import_module("backend.web.layout_response")
    main_source = MAIN_SOURCE.read_text(encoding="utf-8")
    legacy_source = (PROJECT_ROOT / "backend/web/legacy_retirement.py").read_text(encoding="utf-8")

    assert hasattr(layout_response, "render_layout_response")
    assert "render_layout_response" in main_source
    assert "render_layout_response" in legacy_source
    assert "def _layout_response" not in main_source
    assert "def _layout_response" not in legacy_source
    assert "from fastapi.responses import HTMLResponse" not in main_source


def test_main_delegates_router_wiring_to_dedicated_module() -> None:
    """Main should not import and assemble each router itself."""

    import backend.web.main as main

    router_wiring = importlib.import_module("backend.web.main_router_wiring")
    source = MAIN_SOURCE.read_text(encoding="utf-8")
    operations = {
        (route.path, method)
        for route in main.app.routes
        if isinstance(route, APIRoute)
        for method in route.methods
    }

    assert hasattr(router_wiring, "include_main_routers")
    assert "include_main_routers(" in source
    assert "include_core_routers(" not in source
    assert "from backend.web.routes.auth import auth_router" not in source
    assert "from backend.web.routes.app import app_router" not in source
    assert "from backend.web.routes.learning import learning_router" not in source
    assert "from backend.web.routes.teaching import teaching_router" not in source
    assert "from backend.web.routes.users import users_router" not in source
    assert "from backend.web.routes.operations import operations_router" not in source
    assert "from backend.web.routes.basic_pages import create_basic_pages_router" not in source
    assert "create_auth_bridge_router(" not in source
    for expected in (
        ("/auth/login", "GET"),
        ("/api/me", "GET"),
        ("/api/learning/courses", "GET"),
        ("/api/teaching/courses", "GET"),
        ("/health", "GET"),
    ):
        assert expected in operations


def test_main_delegates_auth_only_test_app_to_dedicated_module() -> None:
    """The lightweight auth test app should not be implemented in main.py."""

    import backend.web.main as main

    auth_only_app = importlib.import_module("backend.web.auth_only_app")
    source = MAIN_SOURCE.read_text(encoding="utf-8")
    module_source = (PROJECT_ROOT / "backend/web/auth_only_app.py").read_text(encoding="utf-8")

    assert hasattr(auth_only_app, "create_app_auth_only")
    assert callable(main.create_app_auth_only)
    assert "backend.web.auth_only_app" in source
    assert "def create_app_auth_only" not in source
    assert "import secrets" not in source
    assert "from fastapi.staticfiles import StaticFiles" not in source
    assert "backend.web.main" not in module_source


def test_main_delegates_auth_bridge_routes_to_dedicated_router() -> None:
    """Auth callback and /api/me should be routed outside the app entry module."""

    import backend.web.main as main

    auth_bridge = importlib.import_module("backend.web.auth_bridge")
    source = MAIN_SOURCE.read_text(encoding="utf-8")
    wiring_source = (PROJECT_ROOT / "backend/web/main_router_wiring.py").read_text(encoding="utf-8")
    operations = {
        (route.path, method)
        for route in main.app.routes
        if isinstance(route, APIRoute)
        for method in route.methods
    }

    assert hasattr(auth_bridge, "create_auth_bridge_router")
    assert "create_auth_bridge_router(" in wiring_source
    assert "create_auth_bridge_router(" not in source
    assert "async def auth_callback(" not in source
    assert "async def get_me(" not in source
    assert ("/auth/callback", "GET") in operations
    assert ("/api/me", "GET") in operations


def test_main_delegates_auth_middleware_to_dedicated_module() -> None:
    """Authentication middleware should be installed from a focused module."""

    import backend.web.main as main

    auth_middleware = importlib.import_module("backend.web.auth_middleware")
    source = MAIN_SOURCE.read_text(encoding="utf-8")
    wiring_source = (PROJECT_ROOT / "backend/web/main_middleware_wiring.py").read_text(encoding="utf-8")

    assert hasattr(auth_middleware, "AuthMiddlewareDependencies")
    assert hasattr(auth_middleware, "install_auth_middleware")
    assert hasattr(auth_middleware, "create_auth_context_resolver")
    assert hasattr(main, "AUTH_WIRING")
    assert callable(main.AUTH_WIRING.auth_context_from_request)
    assert "install_auth_middleware(" in wiring_source
    assert "install_auth_middleware(" not in source
    assert "async def auth_enforcement(" not in source
    for local_helper in (
        "def _has_valid_internal_bff_secret",
        "def _bearer_token_from_authorization_header",
        "def _bearer_auth_context_from_request",
        "def _cli_bearer_auth_context_from_token",
        "def _session_auth_context_from_request",
        "def _auth_context_from_request",
    ):
        assert local_helper not in source


def test_main_delegates_middleware_wiring_to_dedicated_module() -> None:
    """Main should not install auth and security middlewares directly."""

    import backend.web.main as main

    middleware_wiring = importlib.import_module("backend.web.main_middleware_wiring")
    source = MAIN_SOURCE.read_text(encoding="utf-8")

    assert hasattr(middleware_wiring, "install_main_middlewares")
    assert hasattr(main, "AUTH_WIRING")
    assert callable(main.AUTH_WIRING.auth_context_from_request)
    assert "install_main_middlewares(" in source
    assert "install_auth_middleware(" not in source
    assert "install_security_headers_middleware(" not in source
    assert "from backend.web.security.headers import install_security_headers_middleware" not in source


def test_main_delegates_storage_wiring_to_dedicated_module() -> None:
    """Startup storage adapter wiring is app composition, not entrypoint code."""

    storage_wiring = importlib.import_module("backend.web.main_storage_wiring")
    source = MAIN_SOURCE.read_text(encoding="utf-8")

    assert hasattr(storage_wiring, "initialize_main_storage")
    assert "initialize_main_storage()" in source
    assert "wire_supabase_adapter_if_configured" not in source
    assert "_wire_storage" not in source


def test_create_app_owns_runtime_auth_middleware_storage_and_router_composition() -> None:
    """The app factory should build the complete FastAPI shell for runtime export."""

    import backend.web.main as main

    source = MAIN_SOURCE.read_text(encoding="utf-8")
    source_lines = [line.strip() for line in source.splitlines()]
    create_app_source = inspect.getsource(main.create_app)

    for marker in (
        "auth_runtime.create_auth_runtime(",
        "initialize_main_storage()",
        "create_main_auth_wiring(",
        "install_main_middlewares(",
        "include_main_routers(",
    ):
        assert marker in create_app_source

    assert "RUNTIME = app.state.runtime" in source_lines
    assert "AUTH_WIRING = app.state.auth_wiring" in source_lines
    assert "RUNTIME = auth_runtime.create_auth_runtime(" not in source_lines
    assert "AUTH_WIRING = create_main_auth_wiring(" not in source_lines
    assert source.count("initialize_main_storage()") == 1
    assert main.app.state.runtime is main.RUNTIME
    assert main.app.state.auth_wiring is main.AUTH_WIRING


def test_main_delegates_auth_runtime_store_wiring_to_dedicated_module() -> None:
    """OIDC and session store construction should not live in the app entry module."""

    import backend.web.main as main

    auth_runtime = importlib.import_module("backend.web.auth_runtime")
    source = MAIN_SOURCE.read_text(encoding="utf-8")

    for expected in (
        "AuthSettings",
        "load_oidc_config",
        "create_session_store",
        "create_bff_session_store",
        "build_cli_token_store",
    ):
        assert hasattr(auth_runtime, expected)

    assert hasattr(main, "RUNTIME")
    assert hasattr(main.RUNTIME, "session_store")
    assert hasattr(main.RUNTIME, "bff_session_store")
    assert hasattr(main.RUNTIME, "cli_token_store")
    assert not hasattr(main, "_build_cli_token_store")
    assert not hasattr(main, "_is_public_path")
    assert not hasattr(main, "load_oidc_config")
    assert "from backend.web import auth_runtime" in source
    assert "class AuthSettings" not in source
    assert "def load_oidc_config" not in source
    assert "def _build_cli_token_store" not in source
    assert "from backend.identity_access.stores_db import DBSessionStore" not in source
    assert "from backend.identity_access.bff_sessions_db import DBBFFSessionStore" not in source


def test_main_exposes_auth_runtime_without_legacy_aliases() -> None:
    """The app entrypoint should expose one Runtime object, not service-locator aliases."""

    import backend.web.main as main

    auth_runtime = importlib.import_module("backend.web.auth_runtime")
    source = MAIN_SOURCE.read_text(encoding="utf-8")

    assert hasattr(auth_runtime, "AuthRuntime")
    assert hasattr(auth_runtime, "create_auth_runtime")
    assert hasattr(main, "RUNTIME")
    assert main.app.state.runtime is main.RUNTIME
    for alias in (
        "SETTINGS",
        "OIDC_CFG",
        "OIDC",
        "STATE_STORE",
        "SESSION_STORE",
        "BFF_SESSION_STORE",
        "CLI_TOKEN_STORE",
    ):
        assert not hasattr(main, alias)
    assert "RUNTIME = app.state.runtime" in source
    assert "RUNTIME = auth_runtime.create_auth_runtime(" not in source
    assert "OIDCClient(" not in source
    assert "StateStore()" not in source


def test_main_delegates_private_auth_wiring_to_dedicated_module() -> None:
    """Main should not keep private auth dependency objects as local aliases."""

    import backend.web.main as main

    auth_wiring = importlib.import_module("backend.web.main_auth_wiring")
    source = MAIN_SOURCE.read_text(encoding="utf-8")

    assert hasattr(auth_wiring, "MainAuthWiring")
    assert hasattr(auth_wiring, "create_main_auth_wiring")
    assert hasattr(main, "AUTH_WIRING")
    assert not hasattr(main, "_auth_middleware_deps")
    assert not hasattr(main, "_roles_for_cli_sub")
    assert not hasattr(main, "_auth_context_from_request")
    assert "AUTH_WIRING = app.state.auth_wiring" in source
    assert "AUTH_WIRING = create_main_auth_wiring(" not in source
    assert "AuthMiddlewareDependencies(" not in source
    assert "create_auth_context_resolver(" not in source
