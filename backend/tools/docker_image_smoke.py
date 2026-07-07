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

FORBIDDEN_RUNTIME_PATHS = (
    "/app/backend/tests",
    "/app/backend/tests_e2e",
    "/app/backend/tools",
)

PROD_LIKE_ENV = (
    "GUSTAV_ENABLE_DOTENV=false",
    "GUSTAV_ENV=prod",
    "SESSIONS_BACKEND=db",
    "CLI_TOKENS_BACKEND=db",
    "SUPABASE_SERVICE_ROLE_KEY=REAL_NON_DUMMY",
    "KC_ADMIN_CLIENT_SECRET=REAL_ADMIN_SECRET",
    "BFF_INTERNAL_SHARED_SECRET=real-bff-secret",
    "H5P_REVIEW_TOKEN_SECRET=real-h5p-review-secret",
    "H5P_INTERNAL_SHARED_SECRET=real-h5p-internal-secret",
    "APP_CSRF_TOKEN_SECRET=real-csrf-secret",
    "REQUIRE_STORAGE_VERIFY=true",
    "ENABLE_DEV_UPLOAD_STUB=false",
    "ENABLE_STORAGE_UPLOAD_PROXY=false",
    "AUTO_CREATE_STORAGE_BUCKETS=false",
    "KC_BASE_URL=http://keycloak:8080",
    "KC_PUBLIC_BASE_URL=https://id.example.com",
    "DATABASE_URL=postgresql://gustav_app_login:secret@db.example.com:5432/postgres?sslmode=require",
    "TEACHING_DATABASE_URL=postgresql://gustav_app_login:secret@db.example.com:5432/postgres?sslmode=require",
    "LEARNING_DATABASE_URL=postgresql://gustav_app_login:secret@db.example.com:5432/postgres?sslmode=require",
    "SESSION_DATABASE_URL=postgresql://gustav_session_login:secret@db.example.com:5432/postgres?sslmode=require",
)


def _run(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    printable = " ".join(args)
    print(f"$ {printable}")
    return subprocess.run(args, check=check, text=True)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _env_args() -> list[str]:
    args: list[str] = []
    for assignment in PROD_LIKE_ENV:
        args.extend(["-e", assignment])
    return args


def _check_imports(image_tag: str) -> None:
    code = (
        "import importlib; "
        f"mods={REQUIRED_IMPORTS!r}; "
        "[importlib.import_module(name) for name in mods]; "
        "print('imports-ok')"
    )
    _run(["docker", "run", "--rm", "--entrypoint", "python", *_env_args(), image_tag, "-c", code])


def _check_image_paths(image_tag: str) -> None:
    code = (
        "from pathlib import Path; "
        f"forbidden={(FORBIDDEN_TOP_LEVEL_PATHS + FORBIDDEN_RUNTIME_PATHS)!r}; "
        "existing=[path for path in forbidden if Path(path).exists()]; "
        "assert not existing, f'forbidden runtime paths: {existing}'; "
        "print('runtime-paths-ok')"
    )
    _run(["docker", "run", "--rm", "--entrypoint", "python", image_tag, "-c", code])


def _check_runtime_dependencies(image_tag: str) -> None:
    code = (
        "import importlib.util; "
        "assert importlib.util.find_spec('ruff') is None, 'ruff must not be installed in runtime image'; "
        "print('runtime-deps-ok')"
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
    _run(
        [
            "docker",
            "run",
            "-d",
            "--rm",
            "--name",
            name,
            "-p",
            f"127.0.0.1:{port}:8000",
            *_env_args(),
            image_tag,
        ]
    )
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
    _check_image_paths(args.tag)
    _check_runtime_dependencies(args.tag)
    _check_health(args.tag, timeout_seconds=args.timeout_seconds)
    print("docker-image-smoke-ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
