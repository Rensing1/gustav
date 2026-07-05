"""Build and smoke-test the web Docker image without Compose bind mounts."""

from __future__ import annotations

import argparse
import socket
import subprocess
import sys
import time
import urllib.request
from uuid import uuid4


REQUIRED_IMPORTS = (
    "backend.web.main",
    "backend.learning",
    "backend.vision",
    "backend.storage",
    "backend.scratch",
    "backend.makecode",
    "backend.filius",
)

FORBIDDEN_TOP_LEVEL_PATHS = (
    "/app/identity_access",
    "/app/teaching",
)


def _run(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    printable = " ".join(args)
    print(f"$ {printable}")
    return subprocess.run(args, check=check, text=True)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _check_imports(image_tag: str) -> None:
    code = (
        "import importlib; "
        f"mods={REQUIRED_IMPORTS!r}; "
        "[importlib.import_module(name) for name in mods]; "
        "print('imports-ok')"
    )
    _run(["docker", "run", "--rm", "--entrypoint", "python", image_tag, "-c", code])


def _check_no_duplicate_package_roots(image_tag: str) -> None:
    code = (
        "from pathlib import Path; "
        f"forbidden={FORBIDDEN_TOP_LEVEL_PATHS!r}; "
        "existing=[path for path in forbidden if Path(path).exists()]; "
        "assert not existing, f'duplicate package roots: {existing}'; "
        "print('package-roots-ok')"
    )
    _run(["docker", "run", "--rm", "--entrypoint", "python", image_tag, "-c", code])


def _wait_for_health(port: int, *, timeout_seconds: float) -> None:
    deadline = time.monotonic() + timeout_seconds
    url = f"http://127.0.0.1:{port}/health"
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.0) as response:
                if 200 <= response.status < 300:
                    print("health-ok")
                    return
        except Exception as exc:  # pragma: no cover - diagnostic path
            last_error = exc
        time.sleep(0.5)
    raise RuntimeError(f"Image healthcheck failed for {url}: {last_error}")


def _check_health(image_tag: str, *, timeout_seconds: float) -> None:
    name = f"gustav-image-smoke-{uuid4().hex[:12]}"
    port = _free_port()
    env = [
        "-e",
        "GUSTAV_ENV=dev",
        "-e",
        "SESSIONS_BACKEND=memory",
        "-e",
        "AUTO_CREATE_STORAGE_BUCKETS=false",
    ]
    _run(["docker", "run", "-d", "--rm", "--name", name, "-p", f"127.0.0.1:{port}:8000", *env, image_tag])
    try:
        _wait_for_health(port, timeout_seconds=timeout_seconds)
    finally:
        _run(["docker", "rm", "-f", name], check=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", default=f"gustav-alpha2:image-smoke-{uuid4().hex[:8]}")
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    args = parser.parse_args(argv)

    _run(["docker", "build", "-t", args.tag, "."])
    _check_imports(args.tag)
    _check_no_duplicate_package_roots(args.tag)
    _check_health(args.tag, timeout_seconds=args.timeout_seconds)
    print("docker-image-smoke-ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
