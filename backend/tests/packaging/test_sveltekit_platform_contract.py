"""Contract tests for the SvelteKit platform foundation.

Why:
    M0 introduces a dedicated `frontend/` application as the primary web
    platform. These source-level tests lock the repo into that direction before
    the larger UI migration continues.
"""

from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_frontend_contains_sveltekit_basics() -> None:
    package_path = REPO_ROOT / "frontend" / "package.json"
    app_html_path = REPO_ROOT / "frontend" / "src" / "app.html"
    hooks_server_path = REPO_ROOT / "frontend" / "src" / "hooks.server.ts"
    layout_server_path = REPO_ROOT / "frontend" / "src" / "routes" / "+layout.server.ts"
    dockerfile_path = REPO_ROOT / "frontend" / "Dockerfile"
    dockerignore_path = REPO_ROOT / "frontend" / ".dockerignore"
    vite_config_path = REPO_ROOT / "frontend" / "vite.config.ts"

    assert package_path.is_file(), f"Missing frontend package manifest: {package_path}"
    assert app_html_path.is_file(), f"Missing SvelteKit app shell: {app_html_path}"
    assert hooks_server_path.is_file(), f"Missing SvelteKit server hook: {hooks_server_path}"
    assert layout_server_path.is_file(), f"Missing root layout server loader: {layout_server_path}"
    assert dockerfile_path.is_file(), f"Missing frontend container image definition: {dockerfile_path}"
    assert dockerignore_path.is_file(), f"Missing frontend .dockerignore: {dockerignore_path}"
    assert vite_config_path.is_file(), f"Missing frontend Vite config: {vite_config_path}"

    package_data = json.loads(package_path.read_text(encoding="utf-8"))
    deps = {
        **package_data.get("dependencies", {}),
        **package_data.get("devDependencies", {}),
    }
    scripts = package_data.get("scripts", {})

    assert package_data.get("private") is True
    assert "@sveltejs/kit" in deps
    assert "@sveltejs/adapter-node" in deps
    assert "svelte" in deps
    assert "dev" in scripts
    assert "build" in scripts
    assert "check" in scripts
    assert "jose" in deps
    assert "svelte-kit sync" in scripts["build"]

    app_html = app_html_path.read_text(encoding="utf-8")
    assert "%sveltekit.head%" in app_html
    assert "%sveltekit.body%" in app_html

    hooks_server_src = hooks_server_path.read_text(encoding="utf-8")
    assert "assertSecureFrontendSessionConfig" in hooks_server_src

    layout_server_src = layout_server_path.read_text(encoding="utf-8")
    assert "/api/app/session-bootstrap" in layout_server_src

    dockerfile_src = dockerfile_path.read_text(encoding="utf-8")
    assert "npm ci" in dockerfile_src
    assert 'CMD ["node", "build"]' in dockerfile_src

    dockerignore_src = dockerignore_path.read_text(encoding="utf-8")
    assert "node_modules" in dockerignore_src
    assert "build" in dockerignore_src

    vite_config_src = vite_config_path.read_text(encoding="utf-8")
    assert "rollupOptions" in vite_config_src
    assert '/h5p/webcomponents/' in vite_config_src


def test_sveltekit_assets_are_root_relative_for_auth_recovery() -> None:
    """SvelteKit must not emit nested relative asset paths on protected routes."""
    svelte_config_path = REPO_ROOT / "frontend" / "svelte.config.js"
    svelte_config_src = svelte_config_path.read_text(encoding="utf-8")

    assert "paths:" in svelte_config_src
    assert "relative: false" in svelte_config_src


def test_compose_and_caddy_route_app_to_frontend_and_api_to_fastapi() -> None:
    compose_path = REPO_ROOT / "docker-compose.yml"
    caddyfile_path = REPO_ROOT / "reverse-proxy" / "Caddyfile"
    caddy_dockerfile_path = REPO_ROOT / "reverse-proxy" / "Dockerfile"

    compose_src = compose_path.read_text(encoding="utf-8")
    caddy_src = caddyfile_path.read_text(encoding="utf-8")
    caddy_dockerfile_src = caddy_dockerfile_path.read_text(encoding="utf-8")

    assert "\n  frontend:\n" in compose_src
    assert "build:\n      context: ./frontend" in compose_src
    assert "container_name: gustav-frontend" in compose_src
    assert "- frontend" in compose_src, "Caddy should depend on the frontend service"
    assert "\n  caddy:\n" in compose_src
    assert "build:\n      context: ./reverse-proxy" in compose_src
    assert "KC_BASE_URL=http://keycloak:8080" in compose_src
    assert "KC_PUBLIC_BASE_URL=${KC_PUBLIC_BASE_URL:-https://id.localhost}" in compose_src
    assert "KC_CLIENT_ID=${KC_CLIENT_ID:-gustav-web}" in compose_src
    assert "KC_REALM=${KC_REALM:-gustav}" in compose_src
    assert "FRONTEND_SESSION_SECRET=${FRONTEND_SESSION_SECRET}" in compose_src
    assert "BFF_INTERNAL_SHARED_SECRET=${BFF_INTERNAL_SHARED_SECRET}" in compose_src

    assert "@api_path path /api/* /internal/*" in caddy_src
    assert "handle @api_path" in caddy_src
    assert "reverse_proxy gustav-alpha2:8000" in caddy_src
    assert "reverse_proxy gustav-frontend:3000" in caddy_src
    assert "FROM caddy:2-alpine" in caddy_dockerfile_src
    assert "COPY Caddyfile /etc/caddy/Caddyfile" in caddy_dockerfile_src
