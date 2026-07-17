"""Contracts for maintained Node runtimes and auditable dependency trees."""

from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def _json(relative_path: str) -> dict:
    return json.loads((REPO_ROOT / relative_path).read_text(encoding="utf-8"))


def test_frontend_uses_the_maintained_markdown_editor_and_exact_security_pins() -> None:
    package = _json("frontend/package.json")
    dependencies = package["dependencies"]
    dev_dependencies = package["devDependencies"]

    assert "@toast-ui/editor" not in dependencies
    for name in (
        "@tiptap/core",
        "@tiptap/pm",
        "@tiptap/starter-kit",
        "@tiptap/extension-table",
        "@tiptap/markdown",
    ):
        assert dependencies[name] == "3.28.0"

    assert dependencies["@xyflow/svelte"] == "1.6.2"
    assert dependencies["isomorphic-dompurify"] == "3.19.0"
    assert dependencies["markdown-it"] == "14.3.0"
    assert dependencies["jose"] == "6.2.3"
    assert dev_dependencies["@sveltejs/adapter-node"] == "5.5.7"
    assert dev_dependencies["@sveltejs/kit"] == "2.70.0"
    assert dev_dependencies["svelte"] == "5.56.6"
    assert dev_dependencies["vite"] == "6.4.3"
    assert dev_dependencies["vitest"] == "4.1.10"
    assert dev_dependencies["postcss"] == "8.5.19"
    assert package["overrides"]["cookie"] == "0.7.2"
    assert package["engines"]["node"] == ">=22.13.0"


def test_h5p_uses_safe_compatible_versions_and_targeted_overrides() -> None:
    package = _json("h5p-service/package.json")

    assert package["engines"]["node"] == ">=22.13.0"
    assert package["dependencies"]["@lumieducation/h5p-express"] == "10.0.5"
    assert package["dependencies"]["express"] == "4.22.2"
    assert package["overrides"] == {
        "express": "4.22.2",
        "path-to-regexp": "0.1.13",
        "qs": "6.15.3",
        "underscore": "1.13.8",
    }


def test_containers_use_node_24_with_production_only_runtime_dependencies() -> None:
    frontend_dockerfile = (REPO_ROOT / "frontend/Dockerfile").read_text(encoding="utf-8")
    h5p_dockerfile = (REPO_ROOT / "h5p-service/Dockerfile").read_text(encoding="utf-8")

    assert frontend_dockerfile.count("node:24.18.0-alpine") == 4
    assert "RUN apk add --no-cache bash" in frontend_dockerfile
    assert "AS runtime-deps" in frontend_dockerfile
    assert "npm ci --omit=dev" in frontend_dockerfile
    assert "COPY --from=runtime-deps /app/node_modules ./node_modules" in frontend_dockerfile
    assert "COPY --from=build /app/node_modules ./node_modules" not in frontend_dockerfile
    assert "FROM node:24.18.0-alpine" in h5p_dockerfile


def test_build_and_online_audit_gates_are_explicit_and_narrow() -> None:
    frontend_package = _json("frontend/package.json")
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    flow_source = (REPO_ROOT / "frontend/src/lib/graph/teacher-unit-flow.ts").read_text(encoding="utf-8")
    layout_source = (REPO_ROOT / "frontend/src/routes/+layout.svelte").read_text(encoding="utf-8")

    assert frontend_package["scripts"]["build"] == "svelte-kit sync && bash tooling/build-with-warning-gate.sh"
    assert "node --test tooling/build-output-policy.test.mjs" in frontend_package["scripts"]["test"]
    vite_config = (REPO_ROOT / "frontend/vite.config.ts").read_text(encoding="utf-8")
    assert "buildWarningGate" in vite_config
    assert "handleBuildWarning" in vite_config
    assert "UNUSED_EXTERNAL_IMPORT" in (REPO_ROOT / "frontend/tooling/build-warning-gate.ts").read_text(encoding="utf-8")
    assert "npm audit --audit-level=low" in makefile
    assert "npm audit --omit=dev --audit-level=low" in makefile
    assert "$(MAKE) dependency-audit" not in makefile.split(".PHONY: verify", maxsplit=1)[1].split("# ---", maxsplit=1)[0]
    assert 'elkjs/lib/elk-api.js' in flow_source
    assert 'elkjs/lib/elk-worker.min.js?url' in flow_source
    assert "elk.bundled.js" not in flow_source
    assert '/latin-' in layout_source
