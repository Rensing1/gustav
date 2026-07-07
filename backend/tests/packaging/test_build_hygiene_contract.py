"""Build/CI hygiene contract tests.

Why:
    - Docker build contexts should stay small and avoid pulling in local build
      artefacts like `node_modules/`, virtualenvs, caches or runtime data.
    - The H5P sidecar is a separate Node project. Its unit tests should be
      runnable via `make` and included in `make verify` so regressions don't
      slip through when only Python tests are run.

Note:
    These are source-level checks. They don't run Docker builds.
"""

from __future__ import annotations

from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def test_root_dockerignore_exists_and_excludes_common_artifacts() -> None:
    repo_root = _repo_root()
    dockerignore_path = repo_root / ".dockerignore"
    assert dockerignore_path.is_file(), "Missing root .dockerignore (Docker build context is '.')"

    content = dockerignore_path.read_text(encoding="utf-8")
    # Minimum set from the plan (F6).
    for needle in [
        "node_modules",
        ".tmp",
        "tmp",
        ".venv",
        ".pytest_cache",
        "supabase/storage",
        "backend/tests/",
        "backend/tests_e2e/",
        "backend/tools/",
    ]:
        assert needle in content, f"Expected `{needle}` to be excluded in {dockerignore_path}"


def test_h5p_service_dockerignore_exists_and_excludes_node_modules() -> None:
    repo_root = _repo_root()
    dockerignore_path = repo_root / "h5p-service" / ".dockerignore"
    assert dockerignore_path.is_file(), "Missing h5p-service/.dockerignore (Docker build context is './h5p-service')"

    content = dockerignore_path.read_text(encoding="utf-8")
    assert "node_modules" in content


def test_make_verify_runs_h5p_node_tests() -> None:
    repo_root = _repo_root()
    makefile_path = repo_root / "Makefile"
    assert makefile_path.is_file(), f"Missing Makefile: {makefile_path}"

    src = makefile_path.read_text(encoding="utf-8")

    assert "test-h5p:" in src, "Missing `test-h5p` Makefile target"
    assert "npm test" in src, "`test-h5p` should execute Node tests (npm test)"
    assert "cd h5p-service" in src, "`test-h5p` should run in the h5p-service directory"

    # `verify` is our CI-like umbrella target.
    assert "$(MAKE) test-h5p" in src, "`make verify` should include `make test-h5p`"
