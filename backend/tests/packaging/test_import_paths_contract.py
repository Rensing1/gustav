"""Import path contract tests (F11).

Why:
    The test suite adds both the repo root and `backend/web` to `sys.path`
    (`backend/tests/conftest.py`). That makes the same module tree importable via
    two different package prefixes:

      - `routes.*` (when importing from the `backend/web` directory)
      - `backend.web.routes.*` (when importing from the repo root)

    Mixing both import styles creates duplicate module instances and was
    previously "papered over" with fragile `sys.modules` aliasing.

    In production, the Docker image runs `uvicorn main:app` from the copied
    `backend/web` sources. Therefore `routes.*` is the canonical import path for
    web routers.

Contract:
    - `backend/web/routes/teaching.py` must not perform `sys.modules` aliasing.
    - Call sites must not import the teaching router via `backend.web.routes.*`.
"""

from __future__ import annotations

from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def test_teaching_route_has_no_sys_modules_alias() -> None:
    src = (_repo_root() / "backend" / "web" / "routes" / "teaching.py").read_text(encoding="utf-8")
    assert "sys.modules.setdefault(\"routes.teaching\"" not in src
    assert "sys.modules.setdefault(\"backend.web.routes.teaching\"" not in src


def test_teaching_imports_use_routes_package_only() -> None:
    repo_root = _repo_root()
    for path in (
        repo_root / "backend" / "web" / "main.py",
        repo_root / "backend" / "web" / "routes" / "learning.py",
        repo_root / "backend" / "tests" / "conftest.py",
    ):
        src = path.read_text(encoding="utf-8")
        assert "backend.web.routes.teaching" not in src, f"Unexpected teaching import alias reference in {path}"
