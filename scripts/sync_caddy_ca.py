#!/usr/bin/env python3
"""
Sync the local Caddy root CA certificate to the workspace.

Why:
    In local dev we use Caddy to terminate TLS for `https://app.localhost` and
    `https://id.localhost`. Containers and host-side tooling (scripts/tests)
    need to trust this local CA when they talk to these endpoints with TLS
    verification enabled (prod-like setup).

Behavior:
    - Copies `root.crt` from the running `gustav-caddy` container to
      `.tmp/caddy-root.crt` in the repo.
    - Ensures the file is world-readable (0644) so non-root containers can
      use it as a CA bundle (e.g. the `web` container runs as user `app`).
    - Does not print certificate contents.

Notes:
    - This is a local-dev helper. In production you would use a real,
      publicly trusted certificate chain.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = REPO_ROOT / ".tmp" / "caddy-root.crt"
CADDY_CONTAINER = "gustav-caddy"
CADDY_CERT_PATH = "/data/caddy/pki/authorities/local/root.crt"


def main() -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    try:
        subprocess.run(
            ["docker", "cp", f"{CADDY_CONTAINER}:{CADDY_CERT_PATH}", str(OUT_PATH)],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or exc.stdout or "").strip()
        raise SystemExit(
            "Failed to copy Caddy root CA certificate.\n"
            f"- container: {CADDY_CONTAINER}\n"
            f"- path: {CADDY_CERT_PATH}\n"
            f"- hint: start services via `docker compose up -d caddy`\n"
            f"- details: {stderr}"
        ) from exc

    # The CA is not a secret. We want containers running as non-root users to
    # be able to read it for TLS verification.
    OUT_PATH.chmod(0o644)

    print(f"Synced Caddy root CA to {OUT_PATH} (not printing certificate contents).")


if __name__ == "__main__":
    main()
