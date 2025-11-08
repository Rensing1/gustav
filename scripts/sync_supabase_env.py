#!/usr/bin/env python3
"""
Sync selected Supabase credentials into .env.

Why:
    After `supabase db reset`, keys such as SERVICE_ROLE_KEY change.
    This helper keeps the local `.env` in sync so storage wiring continues to work.

Behavior:
    - Runs `supabase status -o json`.
    - Extracts SERVICE_ROLE_KEY and updates SUPABASE_SERVICE_ROLE_KEY in `.env`.
    - Creates a backup `.env.bak` before writing.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

ENV_PATH = Path(".env")
BACKUP_PATH = Path(".env.bak")


def _load_supabase_status() -> dict:
    try:
        proc = subprocess.run(
            ["supabase", "status", "-o", "json"],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise SystemExit("supabase CLI not found. Install it before running this script.") from exc
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"supabase status failed: {exc.stderr or exc.stdout}") from exc

    text = proc.stdout.strip()
    json_start = text.find("{")
    if json_start == -1:
        raise SystemExit("Unexpected supabase status output (no JSON payload found).")
    payload = text[json_start:]
    data = json.loads(payload)
    if not isinstance(data, dict):
        raise SystemExit("Unexpected supabase status JSON payload.")
    return data


def _update_env(env_path: Path, key: str, value: str) -> None:
    if not env_path.exists():
        raise SystemExit(f"{env_path} does not exist.")
    lines = env_path.read_text().splitlines()
    match_prefix = f"{key}="
    replaced = False
    for idx, line in enumerate(lines):
        if line.startswith(match_prefix):
            lines[idx] = f"{match_prefix}{value}"
            replaced = True
            break
    if not replaced:
        lines.append(f"{match_prefix}{value}")
    backup = env_path.with_suffix(".bak")
    shutil.copy2(env_path, backup)
    env_path.write_text("\n".join(lines) + "\n")


def main() -> None:
    data = _load_supabase_status()
    try:
        service_role = data["SERVICE_ROLE_KEY"]
    except KeyError as exc:
        raise SystemExit("SERVICE_ROLE_KEY not found in supabase status output.") from exc
    _update_env(ENV_PATH, "SUPABASE_SERVICE_ROLE_KEY", service_role)
    print(f"Updated SUPABASE_SERVICE_ROLE_KEY in {ENV_PATH} (backup saved to {BACKUP_PATH}).")


if __name__ == "__main__":
    main()
