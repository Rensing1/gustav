#!/usr/bin/env python3
"""
Fail-fast readiness probe for local E2E test dependencies.

Why:
    Our E2E tests call `https://app.localhost` (web) and `https://id.localhost`
    (Keycloak) via the local reverse proxy (Caddy). If any container is
    restarting (e.g. because `GUSTAV_ENV=prod` startup guards reject config),
    every E2E test can spend ~60s waiting before failing, which is frustrating.

    This script performs a single, short readiness check up front and prints
    actionable diagnostics if something is broken.

Behavior:
    - Polls a small set of endpoints until all return HTTP 200 or a timeout is
      reached.
    - Timeout is controlled via `E2E_READY_TIMEOUT_S` (default: 20).
    - Uses `KEYCLOAK_CA_BUNDLE` (default: `.tmp/caddy-root.crt`) for TLS verify
      when available; otherwise falls back to `verify=False` (local-only).
    - On failure, prints `docker compose ps` and recent logs for key services.

Security:
    - No secrets are printed.
    - TLS verification is enabled when a CA bundle is available (prod-like).
"""

from __future__ import annotations

import os
import subprocess
import time
import warnings
from dataclasses import dataclass
from pathlib import Path

import requests


@dataclass(frozen=True)
class Check:
    name: str
    url: str
    expected_status: int = 200


def _env(name: str, default: str) -> str:
    return (os.getenv(name) or default).strip()


def _pick_verify() -> bool | str:
    ca = _env("KEYCLOAK_CA_BUNDLE", ".tmp/caddy-root.crt")
    if ca and Path(ca).exists():
        return ca
    return False


def _run_diag(cmd: list[str]) -> None:
    try:
        proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    except Exception as exc:
        print(f"$ {' '.join(cmd)}\n<failed to run: {exc}>")
        return
    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    print(f"$ {' '.join(cmd)}")
    if out:
        print(out)
    if err:
        print(err)


def _checks() -> list[Check]:
    web_base = _env("WEB_BASE", "https://app.localhost").rstrip("/")
    kc_base = _env("KC_BASE", _env("KC_PUBLIC_BASE_URL", "https://id.localhost")).rstrip("/")
    realm = _env("KC_REALM", "gustav").strip()

    return [
        Check(name="web.health", url=f"{web_base}/health"),
        Check(name="keycloak.oidc", url=f"{kc_base}/realms/{realm}/.well-known/openid-configuration"),
        Check(name="h5p.healthz", url=f"{web_base}/h5p/healthz"),
    ]


def main() -> None:
    timeout_s = int(_env("E2E_READY_TIMEOUT_S", "20"))
    per_request_timeout_s = float(_env("E2E_READY_REQUEST_TIMEOUT_S", "3"))
    verify = _pick_verify()

    if verify is False:
        warnings.filterwarnings("ignore", message="Unverified HTTPS request")

    checks = _checks()
    deadline = time.monotonic() + timeout_s
    last_error: str | None = None

    while time.monotonic() < deadline:
        all_ok = True
        for chk in checks:
            try:
                r = requests.get(
                    chk.url,
                    timeout=per_request_timeout_s,
                    verify=verify,
                    allow_redirects=False,
                )
                if r.status_code != chk.expected_status:
                    all_ok = False
                    last_error = f"{chk.name}: GET {chk.url} expected={chk.expected_status} got={r.status_code}"
                    break
            except requests.RequestException as exc:
                all_ok = False
                last_error = f"{chk.name}: GET {chk.url} failed: {exc}"
                break

        if all_ok:
            print(f"E2E dependencies ready ({len(checks)} checks, verify={'on' if verify is not False else 'off'}).")
            return

        time.sleep(0.5)

    print("E2E dependencies not ready within timeout.")
    if last_error:
        print(f"Last error: {last_error}")
    print("Diagnostics (docker compose):")
    _run_diag(["docker", "compose", "ps"])
    _run_diag(["docker", "compose", "logs", "--tail=200", "web", "caddy", "keycloak", "h5p"])
    raise SystemExit(1)


if __name__ == "__main__":
    main()

