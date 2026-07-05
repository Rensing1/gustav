"""Import path contract tests.

Why:
    PR 8 makes the package-oriented runtime entry point authoritative. The web
    adapter should import itself through `backend.web.*`, because flat imports
    such as `main`, `routes.*` and `components` create duplicate module names
    between tests, Docker, and production-like startup.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


WEB_INTERNAL_ROOTS = {
    "auth_utils",
    "components",
    "config",
    "evidence_rendering",
    "material_file_access",
    "models",
    "routes",
    "storage_wiring",
}


def _is_flat_web_module(name: str | None) -> bool:
    if not name:
        return False
    root = name.split(".", 1)[0]
    return root in WEB_INTERNAL_ROOTS


def _flat_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    findings: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _is_flat_web_module(alias.name):
                    findings.append(f"{path.relative_to(_repo_root())}:{node.lineno}: import {alias.name}")
        elif isinstance(node, ast.ImportFrom) and _is_flat_web_module(node.module):
            findings.append(f"{path.relative_to(_repo_root())}:{node.lineno}: from {node.module} import ...")
    return findings


def test_dockerfile_uses_package_oriented_web_entrypoint() -> None:
    dockerfile = (_repo_root() / "Dockerfile").read_text(encoding="utf-8")

    assert 'CMD ["uvicorn", "backend.web.main:app"' in dockerfile
    assert 'CMD ["uvicorn", "main:app"' not in dockerfile
    assert "COPY backend ./backend" in dockerfile
    assert "COPY backend/web/ ." not in dockerfile
    assert "COPY backend/identity_access ./identity_access" not in dockerfile
    assert "COPY backend/teaching ./teaching" not in dockerfile
    assert "ENV PYTHONPATH=/app\n" in dockerfile
    assert "ENV PYTHONPATH=/app:/app/backend" not in dockerfile


def test_compose_mounts_backend_once_without_package_duplicates() -> None:
    compose = (_repo_root() / "docker-compose.yml").read_text(encoding="utf-8")

    assert "- ./backend:/app/backend:z" in compose
    assert "/app/identity_access" not in compose
    assert "/app/teaching" not in compose
    assert "- ./backend/web:/app:z" not in compose


def test_web_adapter_uses_package_imports_for_internal_modules() -> None:
    web_root = _repo_root() / "backend" / "web"
    offenders: list[str] = []
    for path in sorted(web_root.rglob("*.py")):
        if "backend/web/backend" in path.as_posix():
            continue
        offenders.extend(_flat_imports(path))

    assert offenders == []


def test_runtime_backend_code_uses_backend_namespace_for_bounded_contexts() -> None:
    backend_root = _repo_root() / "backend"
    offenders: list[str] = []
    forbidden_roots = {"identity_access", "teaching"}
    for path in sorted(backend_root.rglob("*.py")):
        relative = path.relative_to(_repo_root())
        if relative.parts[:2] == ("backend", "tests"):
            continue
        if relative.parts[:3] == ("backend", "web", "backend"):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".", 1)[0] in forbidden_roots:
                        offenders.append(f"{relative}:{node.lineno}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                if node.module.split(".", 1)[0] in forbidden_roots:
                    offenders.append(f"{relative}:{node.lineno}: from {node.module} import ...")

    assert offenders == []


def test_main_module_does_not_publish_flat_legacy_alias() -> None:
    src = (_repo_root() / "backend" / "web" / "main.py").read_text(encoding="utf-8")

    assert 'setdefault("main"' not in src
    assert '__name__ == "main"' not in src


def test_web_routes_do_not_probe_flat_main_alias() -> None:
    """Runtime route modules should only coordinate through `backend.web.main`."""

    for relative_path in (
        "backend/web/routes/learning.py",
        "backend/web/routes/teaching.py",
    ):
        source = (_repo_root() / relative_path).read_text(encoding="utf-8")

        assert '"main", "backend.web.main"' not in source
        assert '"backend.web.main", "main"' not in source
        assert 'import_module("main")' not in source


def test_harness_does_not_require_legacy_route_aliases() -> None:
    """No legacy route aliases should be required after explicit package imports."""

    import sys

    from backend.tests.import_paths import canonicalize_legacy_route_aliases

    package_module = importlib.import_module("backend.web.routes.learning")
    sys.modules.pop("routes.learning", None)

    canonicalize_legacy_route_aliases()

    assert "routes.learning" not in sys.modules
    assert importlib.import_module("backend.web.routes.learning") is package_module


def test_bounded_context_modules_do_not_publish_legacy_top_level_aliases() -> None:
    """Bounded contexts should be imported through the production `backend.*` namespace."""

    for relative_path in (
        "backend/identity_access/__init__.py",
        "backend/identity_access/cli_tokens.py",
        "backend/identity_access/directory.py",
        "backend/identity_access/oidc.py",
        "backend/identity_access/stores.py",
        "backend/identity_access/tokens.py",
        "backend/teaching/__init__.py",
        "backend/teaching/repo_db.py",
        "backend/teaching/storage.py",
        "backend/teaching/storage_supabase.py",
        "backend/teaching/services/__init__.py",
        "backend/teaching/services/live_student_overview.py",
        "backend/teaching/services/materials.py",
        "backend/teaching/services/tasks.py",
    ):
        source = (_repo_root() / relative_path).read_text(encoding="utf-8")

        assert "sys.modules.setdefault" not in source
        assert "__name__ ==" not in source
