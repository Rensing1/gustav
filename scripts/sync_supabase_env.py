#!/usr/bin/env python3
"""
Sync Supabase env and verify local health for E2E tests.

Why:
    After `supabase start` / `db reset`, the Service Role key changes and the
    API URL may differ. Tests that PUT/GET directly against Supabase Storage
    require a correct `SUPABASE_URL` and a valid `SUPABASE_SERVICE_ROLE_KEY`.

Behavior:
    - Runs `supabase status -o json` (fail-fast on errors).
    - Extracts API URL and SERVICE_ROLE_KEY and updates both variables in `.env`.
    - Verifies that REST and Storage services are reported as running; exits non‑zero otherwise.
    - Creates a backup `.env.bak` before writing.

Security:
    This script is for local dev/test only and never prints secret values. It
    only checks for presence and updates `.env` on disk.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Tuple

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


def _extract_core_fields(data: dict) -> Tuple[str | None, str | None, bool]:
    """Extract API URL, Service Role key and service health flag.

    - Tries multiple shapes, as Supabase CLI JSON can differ by version.
    - Returns (api_url, service_role_key, services_ok)
    """
    def _deep_get(d: Any, *keys: str) -> Any:
        if not isinstance(d, dict):
            return None
        # direct hits
        for k in keys:
            if k in d:
                return d[k]
        # case-insensitive direct hits
        lowered = {str(k).lower(): v for k, v in d.items()}
        for k in keys:
            v = lowered.get(str(k).lower())
            if v is not None:
                return v
        return None

    # URL candidates
    url = None
    url = url or _deep_get(data, "API_URL", "api_url")
    api_section = _deep_get(data, "api")
    if isinstance(api_section, dict) and not url:
        url = _deep_get(api_section, "url", "URL")

    # Service role key candidates
    key = None
    key = key or _deep_get(data, "SERVICE_ROLE_KEY", "service_role_key")

    # Services health (best-effort)
    services_ok = True
    services = _deep_get(data, "services")
    if isinstance(services, dict):
        def _is_running(name: str) -> bool:
            sec = _deep_get(services, name)
            if isinstance(sec, dict):
                status = _deep_get(sec, "status")
                return str(status or "").lower() == "running"
            return True  # if unknown, don't fail just on shape
        # Require both rest and storage to report running when present
        ok_rest = _is_running("rest")
        ok_storage = _is_running("storage")
        services_ok = ok_rest and ok_storage

    return str(url) if url else None, str(key) if key else None, bool(services_ok)


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
    api_url, service_role, services_ok = _extract_core_fields(data)

    if not service_role or str(service_role).upper() == "DUMMY_DO_NOT_USE":
        raise SystemExit("Supabase Service Role key is missing or a dummy placeholder.")
    if not api_url:
        raise SystemExit("Supabase API URL not found in status output.")
    if not services_ok:
        raise SystemExit("Supabase services not healthy (rest/storage not running).")

    # Update both URL and service role key in .env
    _update_env(ENV_PATH, "SUPABASE_URL", str(api_url))
    _update_env(ENV_PATH, "SUPABASE_SERVICE_ROLE_KEY", str(service_role))
    # Avoid printing secrets
    print(f"Synced SUPABASE_URL and service role key in {ENV_PATH} (backup saved to {BACKUP_PATH}).")


if __name__ == "__main__":
    main()
