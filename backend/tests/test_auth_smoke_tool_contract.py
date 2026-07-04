"""Contracts for standalone auth smoke tooling."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_run_auth_smoke_async_uses_package_imports() -> None:
    """The standalone auth smoke script should run from the repository root."""

    result = subprocess.run(
        [sys.executable, "backend/tests/run_auth_smoke_async.py"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "SMOKE: OK" in result.stdout
