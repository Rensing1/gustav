"""Run explicit online dependency audits without short-circuiting ecosystems."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[2]


def run_audits(*, run: Callable = subprocess.run) -> int:
    """Audit public package metadata; return failure if any audit fails.

    This opt-in network command sends package names and versions to advisory
    services. It never upgrades packages or suppresses findings. A missing tool
    is a failure, but remaining ecosystems still run and retain their output.
    """
    commands = (
        ("frontend", ["npm", "audit", "--audit-level=low"], ROOT / "frontend"),
        ("h5p", ["npm", "audit", "--omit=dev", "--audit-level=low"], ROOT / "h5p-service"),
        ("python", [sys.executable, "-m", "pip_audit", "-r", "backend/requirements-harness.lock"], ROOT),
    )
    failed = False
    for label, command, cwd in commands:
        print(f"Dependency audit: {label}", flush=True)
        try:
            result = run(command, cwd=cwd, check=False)
            failed = result.returncode != 0 or failed
        except OSError:
            print(f"Dependency audit unavailable: {label}", file=sys.stderr)
            failed = True
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(run_audits())
