#!/usr/bin/env python3
"""
Sync `.env` for a production-like local setup (dev=prod).

This script is intentionally opinionated for solo-dev workflows:
  - Forces `GUSTAV_ENV=prod` locally so the startup security guard runs.
  - Ensures required prod-like toggles are set to safe values.
  - Syncs dynamic secrets/values from local infrastructure:
      - Caddy local root CA (for TLS trust inside containers)
      - Supabase SERVICE_ROLE_KEY (changes after `supabase db reset`)
      - Keycloak confidential admin client secret (client_credentials)

It only updates a small, well-defined set of keys and creates `.env.bak`
before writing. Secrets are never printed.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = REPO_ROOT / ".env"


def _update_env(key: str, value: str) -> None:
    if not ENV_PATH.exists():
        raise SystemExit(f"{ENV_PATH} not found. Create it (e.g., `cp .env.example .env`) first.")
    lines = ENV_PATH.read_text().splitlines()
    prefix = f"{key}="
    replaced = False
    for i, line in enumerate(lines):
        if line.startswith(prefix):
            lines[i] = f"{prefix}{value}"
            replaced = True
            break
    if not replaced:
        lines.append(f"{prefix}{value}")
    shutil.copy2(ENV_PATH, ENV_PATH.with_suffix(".bak"))
    ENV_PATH.write_text("\n".join(lines) + "\n")


def _run(cmd: list[str]) -> None:
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"Command failed: {' '.join(cmd)} (exit={exc.returncode})") from exc


def main() -> None:
    # 1) Force prod-like startup behavior (dev=prod)
    _update_env("GUSTAV_ENV", "prod")

    # 2) Base URLs (reverse proxy)
    _update_env("WEB_BASE", "https://app.localhost")
    _update_env("REDIRECT_URI", "https://app.localhost/auth/callback")

    # Keycloak: browser-facing + server-side base should be HTTPS in prod.
    _update_env("KC_PUBLIC_BASE_URL", "https://id.localhost")
    _update_env("KC_BASE", "https://id.localhost")  # legacy scripts/tests
    _update_env("KC_BASE_URL", "https://id.localhost")

    # 3) Prod-like safety toggles (startup guard expects these in prod)
    _update_env("SESSIONS_BACKEND", "db")
    _update_env("AUTO_CREATE_STORAGE_BUCKETS", "false")
    _update_env("REQUIRE_STORAGE_VERIFY", "true")
    _update_env("ENABLE_DEV_UPLOAD_STUB", "false")
    _update_env("ENABLE_STORAGE_UPLOAD_PROXY", "false")

    # 4) Dynamic infrastructure sync (order matters)
    _run(["python3", "scripts/sync_caddy_ca.py"])
    # Use the host path for host-side tooling; docker-compose maps this into the container.
    _update_env("KEYCLOAK_CA_BUNDLE", ".tmp/caddy-root.crt")

    _run(["python3", "scripts/sync_supabase_env.py"])
    _run(["python3", "scripts/sync_keycloak_env.py"])

    print("Synced .env for prod-like local runs (secrets not printed).")


if __name__ == "__main__":
    main()

