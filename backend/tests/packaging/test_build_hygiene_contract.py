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

import subprocess
import sys
import zipfile
from pathlib import Path

import pytest


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def test_real_pip_rejects_a_modified_artifact_offline(tmp_path: Path) -> None:
    """Exercise hash enforcement without installing a package or using a registry."""
    wheel = tmp_path / "gustav_hash_probe-1.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("gustav_hash_probe.py", "VALUE = 'modified'\n")
        archive.writestr("gustav_hash_probe-1.0.dist-info/METADATA", "Metadata-Version: 2.1\nName: gustav-hash-probe\nVersion: 1.0\n")
        archive.writestr("gustav_hash_probe-1.0.dist-info/WHEEL", "Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n")
        archive.writestr("gustav_hash_probe-1.0.dist-info/RECORD", "")
    requirements = tmp_path / "requirements.lock"
    requirements.write_text("gustav-hash-probe==1.0 --hash=sha256:" + "0" * 64 + "\n")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--dry-run", "--ignore-installed",
         "--disable-pip-version-check", "--no-deps", "--no-index", "--find-links", str(tmp_path),
         "--require-hashes", "-r", str(requirements)],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode != 0
    assert "DO NOT MATCH THE HASHES" in result.stderr


@pytest.mark.parametrize("failed_command", ["pip", "apt-get"])
def test_python_installation_and_cleanup_failures_stop_the_build(failed_command):
    """Execute the real RUN expressions with harmless shell command doubles."""
    dockerfile = (_repo_root() / "Dockerfile").read_text().replace("\\\n", " ")
    commands = [line.removeprefix("RUN ") for line in dockerfile.splitlines() if line.startswith("RUN ") and ("pip install" in line or "purge" in line)]
    # Functions shadow the executable names; no installer or package manager runs.
    doubles = f"pip() {{ return {17 if failed_command == 'pip' else 0}; }}; apt-get() {{ return {17 if failed_command == 'apt-get' else 0}; }}; "
    result = subprocess.run(["bash", "-c", doubles + "\n".join(f"( {command} ) || exit $?" for command in commands)], check=False)
    assert result.returncode == 17


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


def test_frontend_lock_install_failure_is_not_replaced_by_an_unlocked_install():
    dockerfile = (_repo_root() / "frontend/Dockerfile").read_text()
    commands = [line.removeprefix("RUN ") for line in dockerfile.splitlines() if line.startswith("RUN npm ci")]
    assert commands
    doubles = 'npm() { if [ "$1" = ci ]; then return 17; else return 0; fi; }; '
    for command in commands:
        result = subprocess.run(["bash", "-c", doubles + command], check=False)
        assert result.returncode == 17


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
